FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
RUN pip install --no-cache-dir \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0 \
    python-multipart==0.0.6 \
    aiofiles==23.2.1 \
    Pillow==10.2.0 \
    requests==2.31.0 \
    httpx==0.26.0

# 复制应用代码
COPY app-simple.py ./

# 创建必要目录
RUN mkdir -p /app/results

# 云托管默认使用 80 端口
EXPOSE 80

# 启动服务
CMD ["python", "-m", "uvicorn", "app-simple:app", "--host", "0.0.0.0", "--port", "80"]
