FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir setuptools && pip install --no-cache-dir -r requirements.txt

COPY . .

# Production entry point: using Gunicorn with Uvicorn workers
CMD ["gunicorn", "-c", "gunicorn_conf.py", "main:app"]
