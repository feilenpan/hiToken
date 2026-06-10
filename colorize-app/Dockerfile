# CloudBase Run 部署 — 时光修复 v2.1
# evaluate + suggest-edit + process (seededit_v3.0)
# 2026-05-30: fix data.function bug
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0 \
    python-multipart==0.0.6 \
    aiofiles==23.2.1 \
    Pillow==10.2.0 \
    requests==2.31.0 \
    httpx==0.26.0 \
    python-jose[cryptography]==3.3.0 \
    passlib[bcrypt]==1.7.4

COPY app_full.py volc_visual_engine.py share_card_api.py ./
COPY legal/ ./legal/

RUN mkdir -p /app/results /app/data /app/temp /app/uploads

EXPOSE 80

CMD ["python", "-m", "uvicorn", "app_full:app", "--host", "0.0.0.0", "--port", "80"]
