FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0 \
    python-multipart==0.0.6 \
    aiofiles==23.2.1 \
    Pillow==10.2.0 \
    requests==2.31.0 \
    httpx==0.26.0

# 从 colorize-app 子目录复制
COPY colorize-app/app-simple.py ./

RUN mkdir -p /app/results

EXPOSE 80

CMD ["python", "-m", "uvicorn", "app-simple:app", "--host", "0.0.0.0", "--port", "80"]
