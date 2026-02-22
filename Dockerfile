FROM python:3.11-alpine

RUN apk add --no-cache ffmpeg curl

# Install a small web server
RUN pip install --no-cache-dir fastapi uvicorn

# Install piper (Python wrapper + binaries are tricky; simplest is to bundle a piper binary)
# For now we’ll use the piper-tts package; on some arches you may need a different install.
RUN pip install --no-cache-dir piper-tts

COPY rootfs/ /rootfs/
WORKDIR /rootfs

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]