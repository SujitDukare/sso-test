FROM python:3.11-slim

WORKDIR /app

# Install system deps for snowflake-connector-python
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ libssl-dev libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
