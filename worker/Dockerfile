FROM python:3.10-slim

LABEL maintainer="backend-team" \
      description="Uptime Monitor Worker"

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY uptime_worker.py .
COPY db_utils.py .
COPY init_db.sql .

ENV DB_HOST=postgres \
    DB_PORT=5432 \
    DB_NAME=uptime_db \
    DB_USER=uptime_user \
    DB_PASSWORD=secure_password \
    URLS=https://google.com,https://github.com \
    CHECK_INTERVAL_SECONDS=60 \
    REQUEST_TIMEOUT=5

CMD ["python", "uptime_worker.py"]
