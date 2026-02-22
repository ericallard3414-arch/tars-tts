import os
import json
import subprocess
import tempfile
from urllib.parse import unquote

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response

app = FastAPI()

OPTIONS_PATH = "/data/options.json"
VOICES_DIR = "/data/voices"
os.makedirs(VOICES_DIR, exist_ok=True)

FFMPEG_AF = (
    "highpass=f=170,lowpass=f=3200,"
    "acompressor=threshold=-18dB:ratio=4:attack=10:release=80:makeup=6,"
    "acrusher=bits=12:mix=0.12"
)

def load_options() -> dict:
    try:
        with open(OPTIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def ensure_voice(voice: str) -> str:
    model_path = os.path.join(VOICES_DIR, f"{voice}.onnx")
    json_path = os.path.join(VOICES_DIR, f"{voice}.onnx.json")

    if os.path.exists(model_path) and os.path.exists(json_path):
        return model_path

    cmd = ["python", "-m", "piper.download_voices", "--download-dir", VOICES_DIR, voice]
    r = subprocess.run(cmd, capture_output=True, text=True)

    if r.returncode != 0:
        raise RuntimeError(f"voice_download_failed: {r.stderr[-2000:]}")

    if not (os.path.exists(model_path) and os.path.exists(json_path)):
        raise RuntimeError("voice_download_failed: files not found after download")

    return model_path

@app.get("/tts")
def tts(text: str, voice: str | None = None):
    try:
        text = unquote(text)
        opts = load_options()

        v = voice or opts.get("voice") or "en_US-ryan-medium"
        model_path = ensure_voice(v)

        # Optional knobs (safe defaults)
        length_scale = float(opts.get("length_scale", 1.0))
        noise_scale = float(opts.get("noise_scale", 0.667))

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as rawf:
            raw_path = rawf.name
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as outf:
            out_path = outf.name

        try:
            # Piper -> raw.wav
            cmd_piper = [
                "piper",
                "--model", model_path,
                "--output_file", raw_path,
                "--length_scale", str(length_scale),
                "--noise_scale", str(noise_scale),
            ]
            p = subprocess.Popen(
                cmd_piper,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            _, err = p.communicate(text)

            if p.returncode != 0 or not os.path.exists(raw_path) or os.path.getsize(raw_path) < 1000:
                return JSONResponse(
                    {"error": "piper_failed", "details": (err or "")[-2000:], "voice": v},
                    status_code=500,
                )

            # FFmpeg filter -> tars.wav
            cmd_ff = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", raw_path, "-af", FFMPEG_AF, out_path]
            r = subprocess.run(cmd_ff, capture_output=True, text=True)

            if r.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) < 1000:
                return JSONResponse(
                    {"error": "ffmpeg_failed", "details": (r.stderr or "")[-2000:]},
                    status_code=500,
                )

            # Return bytes (no temp-dir lifetime issues)
            with open(out_path, "rb") as f:
                audio_bytes = f.read()

            return Response(content=audio_bytes, media_type="audio/wav")

        finally:
            # Cleanup temp files
            for pth in (raw_path, out_path):
                try:
                    if pth and os.path.exists(pth):
                        os.remove(pth)
                except Exception:
                    pass

    except Exception as e:
        return JSONResponse({"error": "server_failed", "details": str(e)}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": "server_failed", "details": str(e)}, status_code=500)


