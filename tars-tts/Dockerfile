FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libgomp1 \
    libstdc++6 \
    libgcc-s1 \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir \
    fastapi uvicorn \
    pathvalidate \
    "onnxruntime==1.17.3" \
    "piper-tts==1.4.1"

WORKDIR /app
COPY rootfs/ /app

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
