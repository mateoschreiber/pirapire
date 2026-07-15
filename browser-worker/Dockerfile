FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastapi==0.139.0 \
    uvicorn[standard]==0.51.0 \
    playwright

RUN playwright install chromium
RUN playwright install-deps chromium

COPY browser_worker.py /app/

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "-u", "/app/browser_worker.py"]