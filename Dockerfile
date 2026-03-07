FROM python:3.11-slim

WORKDIR /app

# System deps (postgresql-client needed for pg_dump backups)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev postgresql-client && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

CMD ["python", "-m", "bot.main"]
