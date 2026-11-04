# SANKOFA backend on Hugging Face Spaces (Docker SDK).
# The Space only holds this Dockerfile and README.md: the code and data are cloned
# from the `backend` branch of https://github.com/KOBA2008/sankofa at build time.
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ffmpeg libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user

# Busts the Docker cache whenever the backend branch gets a new commit
ADD https://api.github.com/repos/KOBA2008/sankofa/git/refs/heads/backend /tmp/backend-ref.json
RUN git clone --depth 1 --branch backend https://github.com/KOBA2008/sankofa.git /app \
 && chown -R user /app
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

USER user
ENV HOME=/home/user \
    PYTHONUNBUFFERED=1 \
    DAILY_PAID_CALL_LIMIT=300
WORKDIR /app/backend
EXPOSE 7860
# The public-domain soundtrack is fetched in the background at start-up
CMD ["sh", "-c", "python build_music.py > /tmp/music.log 2>&1 & exec uvicorn sankofa.api:app --host 0.0.0.0 --port 7860"]
