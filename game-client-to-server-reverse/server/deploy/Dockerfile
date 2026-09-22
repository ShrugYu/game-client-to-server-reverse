FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    GSRV_CONFIG=/app/config/config.yaml

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data logs

EXPOSE 8888/tcp 9900/tcp

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import socket;socket.create_connection(('127.0.0.1',8888),2)" || exit 1

CMD ["python", "-m", "app.main", "-c", "/app/config/config.yaml"]