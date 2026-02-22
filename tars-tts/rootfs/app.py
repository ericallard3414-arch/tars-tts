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


# -------------------------
# Utility
# -------------------------

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

    cmd = [
        "python",
        "-m",
        "piper.download_voices",
        "--download-dir",
        VOICES_DIR,
        voice,
    ]

    r = subprocess.run(cmd, capture_output=True, text=True)

    if r.returncode != 0:
        raise RuntimeError(f"voice_download_failed: {r.stderr[-2000:]}")

    if not (os.path.exists(model_path) and os.path.exists(json_path)):
        raise RuntimeError("voice_download_failed: files not found after download")

    return model_path


# -------------------------
# TTS Endpoint
# -------------------------

@app.get("/tts")
def tts(text: str, voice: str | None = None):
    try:
        text = unquote(text)
        opts = load_options()

        v = voice or opts.get("voice") or "en_US-ryan-medium"
        model_path = ensure_voice(v)

        length_scale = float(opts.get("length_scale", 1.0))
        noise_scale = float(opts.get("noise_scale", 0.667))

        # ---- AUDIO SHAPING CONTROLS ----
        grit = float(opts.get("grit", 0.04))
        lowpass = int(opts.get("lowpass", 3000))
        pitch = float(opts.get("pitch", 0.92))  # 0.92 subtle, 0.90 deeper

        # Optional: clamp to sane ranges
        if pitch < 0.85:
            pitch = 0.85
        if pitch > 1.05:
            pitch = 1.05
        if grit < 0.0:
            grit = 0.0
        if grit > 0.10:
            grit = 0.10
        if lowpass < 2000:
            lowpass = 2000
        if lowpass > 5000:
            lowpass = 5000

        ffmpeg_af = (
            f"asetrate=44100*{pitch},atempo=1/{pitch},"
            "highpass=f=180,"
            f"lowpass=f={lowpass},"
            "acompressor=threshold=-21dB:ratio=3.2:attack=6:release=85:makeup=5,"
            f"acrusher=bits=15:mix={grit}"
        )

        raw_path = None
        out_path = None

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as rawf:
            raw_path = rawf.name

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as outf:
            out_path = outf.name

        try:
            # Piper generation
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

            # FFmpeg shaping
            cmd_ff = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel", "error",
                "-i", raw_path,
                "-af", ffmpeg_af,
                out_path,
            ]

            r = subprocess.run(cmd_ff, capture_output=True, text=True)

            if r.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) < 1000:
                return JSONResponse(
                    {"error": "ffmpeg_failed", "details": (r.stderr or "")[-2000:], "af": ffmpeg_af},
                    status_code=500,
                )

            with open(out_path, "rb") as f:
                audio_bytes = f.read()

            return Response(content=audio_bytes, media_type="audio/wav")

        finally:
            for pth in (raw_path, out_path):
                try:
                    if pth and os.path.exists(pth):
                        os.remove(pth)
                except Exception:
                    pass

    except Exception as e:
        return JSONResponse({"error": "server_failed", "details": str(e)}, status_code=500)




