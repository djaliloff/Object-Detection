FROM python:3.11-slim

# Créer un répertoire de cache persistant
RUN mkdir -p /root/.cache/pip && chmod 755 /root/.cache/pip

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Utiliser le cache pip et augmenter le timeout
RUN pip install --cache-dir /root/.cache/pip --timeout 600 --retries 3 -r requirements.txt

COPY . .

EXPOSE 8000
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
