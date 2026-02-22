import os
import subprocess
import tempfile
from fastapi import FastAPI
from fastapi.responses import FileResponse
from urllib.parse import unquote

app = FastAPI()

VOICE = os.getenv("VOICE", "en_US-ryan-medium")
LENGTH = os.getenv("LENGTH_SCALE", "1.1")
NOISE = os.getenv("NOISE_SCALE", "0.45")
CADENCE = os.getenv("CADENCE", "0.8")

# TARS-ish filter
FFMPEG_AF = (
    "highpass=f=170,lowpass=f=3200,"
    "acompressor=threshold=-18dB:ratio=4:attack=10:release=80:makeup=6,"
    "acrusher=bits=12:mix=0.12"
)

@app.get("/tts")
def tts(text: str):
    # Decode URL encoding
    text = unquote(text)

    with tempfile.TemporaryDirectory() as d:
        raw = os.path.join(d, "raw.wav")
        out = os.path.join(d, "tars.wav")

        # Generate with piper (CLI)
        # piper-tts provides `piper` CLI in many installs
        cmd_piper = [
            "piper",
            "--model", VOICE,
            "--output_file", raw
        ]

        p = subprocess.Popen(cmd_piper, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        _, err = p.communicate(text)
        if p.returncode != 0:
            return {"error": "piper_failed", "details": err[-800:]}

        # Filter with ffmpeg
        cmd_ff = ["ffmpeg", "-y", "-i", raw, "-af", FFMPEG_AF, out]
        r = subprocess.run(cmd_ff, capture_output=True, text=True)
        if r.returncode != 0:
            return {"error": "ffmpeg_failed", "details": r.stderr[-800:]}

        return FileResponse(out, media_type="audio/wav", filename="tars.wav")