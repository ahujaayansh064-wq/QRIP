# QRIP's own code is standard library only; the one dependency is the
# Anthropic SDK used by functions 1 and 2.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY samples/ ./samples/

ENV PYTHONUNBUFFERED=1 \
    QRIP_DATA_DIR=/data \
    PORT=8000

RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request,os; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT','8000') + '/api/health').read()"

CMD ["python", "backend/server.py"]
