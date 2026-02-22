FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl espeak-ng \
  && rm -rf /var/lib/apt/lists/*

# Upgrade pip helps dependency resolution
RUN pip install --no-cache-dir --upgrade pip

# Install app deps
RUN pip install --no-cache-dir fastapi uvicorn

# Install piper deps explicitly (fixes your error)
RUN pip install --no-cache-dir pathvalidate

# Install Piper TTS
RUN pip install --no-cache-dir piper-tts

COPY rootfs/ /rootfs/
WORKDIR /rootfs
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
