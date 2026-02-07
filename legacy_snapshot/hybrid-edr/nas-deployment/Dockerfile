FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y \
    gcc procps net-tools && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY utils/ /app/utils/
COPY collectors/ /app/collectors/
COPY config/ /app/config/
COPY edr_collector_nas.py /app/

RUN mkdir -p /app/data /app/logs

CMD ["python", "-u", "edr_collector_nas.py"]
