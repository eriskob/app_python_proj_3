FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y netcat-openbsd && rm -rf /var/lib/apt/lists/*

COPY ./src/requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

COPY ./src /app

RUN chmod +x /app/app.sh /app/celery.sh

EXPOSE 8000