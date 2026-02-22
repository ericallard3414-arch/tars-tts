import os
import json
import subprocess
import tempfile
from urllib.parse import unquote

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

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

    cmd = ["python", "-m", "piper.download_voices", "--output-dir", VOICES_DIR, "--voice", voice]
    r = subprocess.run(cmd, capture_output=True, text=True)

    if r.returncode != 0:
        raise RuntimeError(f"voice_download_failed: {r.stderr[-1200:]}")

    if not (os.path.exists(model_path) and os.path.exists(json_path)):
        raise RuntimeError("voice_download_failed: files not found after download")

    return model_path


@app.get("/tts")
def tts(text: str, voice: str | None = None):
    try:
        text = unquote(text)
        opts = load_options()

        # Use query voice first, then add-on option, then fallback
        v = voice or opts.get("voice") or "en_US-ryan-medium"

        model_path = ensure_voice(v)

        with tempfile.TemporaryDirectory() as d:
            raw = os.path.join(d, "raw.wav")
            out = os.path.join(d, "tars.wav")

            cmd_piper = ["piper", "--model", model_path, "--output_file", raw]
            p = subprocess.Popen(cmd_piper, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            _, err = p.communicate(text)

            if p.returncode != 0:
                return JSONResponse({"error": "piper_failed", "details": err[-1600:]}, status_code=500)

            cmd_ff = ["ffmpeg", "-y", "-i", raw, "-af", FFMPEG_AF, out]
            r = subprocess.run(cmd_ff, capture_output=True, text=True)

            if r.returncode != 0:
                return JSONResponse({"error": "ffmpeg_failed", "details": r.stderr[-1600:]}, status_code=500)

            return FileResponse(out, media_type="audio/wav", filename="tars.wav")

    except Exception as e:
        return JSONResponse({"error": "server_failed", "details": str(e)}, status_code=500)
