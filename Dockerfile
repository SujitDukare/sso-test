FROM python:3.11.9-slim-bookworm

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ libssl-dev libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --system --uid 10001 --no-create-home appuser && \
    chown -R appuser:appuser /app
USER 10001
ENV HOME=/tmp \
    PYTHONUNBUFFERED=1 \
    PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 180 --access-logfile - app:app"]
