FROM python:3.11-slim

# System deps:
# - ffmpeg for your TARS filter
# - espeak-ng required by piper phonemizer on many setups
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Python deps
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir fastapi uvicorn piper-tts==1.4.1

WORKDIR /app
COPY rootfs/ /app

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
