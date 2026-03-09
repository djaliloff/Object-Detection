# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Utiliser le cache BuildKit pour pip - évite les re-téléchargements
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 600 --retries 3 -r requirements.txt

COPY . .

CMD ["python", "inference.py"]
