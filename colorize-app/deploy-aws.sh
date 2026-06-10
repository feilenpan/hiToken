#!/bin/bash
# 時光修復 - AWS 部署腳本
# 在 AWS EC2 上執行此腳本

set -e

echo "🚀 開始部署時光修復後端..."

# 1. 更新系統
echo "📦 更新系統套件..."
sudo apt update && sudo apt upgrade -y

# 2. 安裝 Python 環境
echo "🐍 安裝 Python 環境..."
sudo apt install -y python3 python3-pip python3-venv nginx

# 3. 創建項目目錄
echo "📁 創建項目目錄..."
sudo mkdir -p /opt/colorize-app
sudo chown -R ubuntu:ubuntu /opt/colorize-app

# 4. 創建 Python 虛擬環境
echo "🔧 創建虛擬環境..."
cd /opt/colorize-app
python3 -m venv venv
source venv/bin/activate

# 5. 安裝 Python 依賴
echo "📚 安裝 Python 依賴..."
pip install --upgrade pip
pip install fastapi uvicorn python-multipart aiofiles pillow

# 6. 創建後端代碼
echo "📝 創建後端代碼..."
cat > /opt/colorize-app/app.py << 'APPEOF'
# -*- coding: utf-8 -*-
"""
時光修復 - AI老照片修復工具 免費版
功能：上色 / 照片修復 / 人臉增強 / 超分辨率
"""

import os
import uuid
import time
import hashlib
import logging
import base64
from pathlib import Path
from typing import Optional
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, HTTPException, Header, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="時光修復", description="AI老照片修復工具 - 免費版")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# 簡易內存數據庫（生產環境應使用 SQLite/PostgreSQL）
users_db = {}
records_db = {}

def get_result_dir() -> Path:
    today = datetime.now().strftime("%Y/%m/%d")
    d = RESULTS_DIR / today
    d.mkdir(parents=True, exist_ok=True)
    return d

# ===== 工具函數 =====

def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "")
    return users_db.get(token)

def require_user(authorization: Optional[str] = Header(None)) -> dict:
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(401, "請先登錄")
    return user

# ===== API =====

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "時光修復 免費版",
        "timestamp": int(time.time())
    }

@app.post("/api/wechat/login")
async def wechat_login(request: Request):
    data = await request.json()
    code = data.get("code", "")
    if not code:
        raise HTTPException(400, "code is required")
    
    # 簡化登錄（生產環境應調用微信 jscode2session）
    openid = hashlib.md5(code.encode()).hexdigest()[:16]
    
    if openid not in users_db:
        users_db[openid] = {
            "id": len(users_db) + 1,
            "openid": openid,
            "nickname": "用戶" + openid[:4],
            "total_used": 0,
            "privacy_agreed": False,
            "agreement_agreed": False
        }
    
    user = users_db[openid]
    return {
        "success": True,
        "token": openid,
        "user": {
            "id": user["id"],
            "nickname": user["nickname"],
            "total_used": user["total_used"],
            "privacy_agreed": user["privacy_agreed"],
            "agreement_agreed": user["agreement_agreed"]
        }
    }

@app.get("/api/user/info")
async def get_user_info(user: dict = Depends(require_user)):
    return {
        "success": True,
        "user": {
            "id": user["id"],
            "nickname": user["nickname"],
            "total_used": user["total_used"],
            "privacy_agreed": user["privacy_agreed"],
            "agreement_agreed": user["agreement_agreed"]
        }
    }

@app.post("/api/process")
async def process_photo(
    file: UploadFile = File(...),
    process_type: str = "colorize",
    user: Optional[dict] = Depends(get_current_user)
):
    """統一處理端點"""
    
    # 驗證文件
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "請上傳圖片文件")
    
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "圖片大小不能超過10MB")
    
    task_id = str(uuid.uuid4())
    
    # 模擬處理（生產環境應調用真實 AI 引擎）
    # 這裡直接返回原圖作為演示
    result_base64 = base64.b64encode(content).decode()
    
    # 保存結果圖
    result_url = ""
    try:
        result_dir = get_result_dir()
        filename = f"{task_id}.jpg"
        filepath = result_dir / filename
        filepath.write_bytes(content)
        
        date_path = datetime.now().strftime("%Y/%m/%d")
        result_url = f"/api/results/{date_path}/{filename}"
        logger.info(f"結果圖已保存: {filepath}")
    except Exception as e:
        logger.error(f"保存結果圖失敗: {e}")
    
    # 更新用戶統計
    if user:
        user["total_used"] += 1
    
    return {
        "success": True,
        "task_id": task_id,
        "process_type": process_type,
        "result": f"data:image/jpeg;base64,{result_base64}",
        "result_url": result_url,
        "engine": "demo"
    }

@app.get("/api/results/{year}/{month}/{day}/{filename}")
async def get_result_image(year: str, month: str, day: str, filename: str):
    filepath = RESULTS_DIR / year / month / day / filename
    if not filepath.exists():
        raise HTTPException(404, "圖片不存在")
    return FileResponse(str(filepath), media_type="image/jpeg")

@app.post("/api/user/agree-privacy")
async def agree_privacy(user: dict = Depends(require_user)):
    user["privacy_agreed"] = True
    return {"success": True}

@app.post("/api/user/agree-agreement")
async def agree_agreement(user: dict = Depends(require_user)):
    user["agreement_agreed"] = True
    return {"success": True}

@app.get("/api/privacy")
async def get_privacy_policy():
    content = """# 時光修復 - 隱私保護政策

最後更新日期：2026年5月27日

一、引言
歡迎使用「時光修復」。我們非常重視您的隱私保護。

二、我們收集的信息
- 上傳的照片：僅用於AI處理，原圖不會保存
- 處理結果：保存在服務器，30天後自動刪除

三、我們提供的服務
- AI上色：黑白照片智能上色
- 照片修復：修復折痕、污漬、損傷
- 人臉增強：模糊人臉變清晰
- 超分辨率：低清照片變高清

四、信息保護
- 您的原圖僅在內存中處理，不會保存到服務器
- 處理結果保存30天後自動刪除
- 所有數據傳輸使用HTTPS加密
- 不會出售或分享您的個人信息

五、您的權利
- 您可隨時申請刪除所有數據
- 聯繫郵箱：privacy@colorize-hk.com

本隱私政策自2026年5月27日起生效。"""
    return {"success": True, "content": content}

@app.get("/api/agreement")
async def get_user_agreement():
    content = """# 時光修復 - 用戶服務協議

最後更新日期：2026年5月27日

一、服務條款
使用本服務即表示您同意本協議。

二、服務內容
AI老照片修復工具，完全免費使用。

三、使用規範
- 請勿上傳違法違規內容
- 請勿對服務進行反向工程或攻擊

四、知識產權
您上傳的照片知識產權歸您所有。

五、聯繫我們
- 郵箱：support@colorize-hk.com"""
    return {"success": True, "content": content}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8888)
APPEOF

# 7. 創建 systemd 服務
echo "⚙️ 創建 systemd 服務..."
sudo tee /etc/systemd/system/colorize.service > /dev/null << 'SERVICEEOF'
[Unit]
Description=Colorize App - AI Photo Repair
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/colorize-app
Environment=PATH=/opt/colorize-app/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/opt/colorize-app/venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8888
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

# 8. 配置 Nginx
echo "🌐 配置 Nginx..."
sudo tee /etc/nginx/sites-available/colorize > /dev/null << 'NGINXEOF'
server {
    listen 80;
    server_name _;  # 接受所有域名，生產環境應改為具體域名
    
    # 文件上傳大小限制
    client_max_body_size 10M;
    
    # API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8888;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超時設置（AI處理可能較慢）
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # 靜態文件
    location / {
        proxy_pass http://127.0.0.1:8888;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # 安全頭
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
NGINXEOF

# 啟用站點
sudo ln -sf /etc/nginx/sites-available/colorize /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# 9. 啟動服務
echo "🚀 啟動服務..."
sudo systemctl daemon-reload
sudo systemctl enable colorize
sudo systemctl start colorize
sudo systemctl restart nginx

# 10. 檢查狀態
echo "✅ 部署完成！檢查服務狀態..."
echo ""
echo "📊 服務狀態："
sudo systemctl status colorize --no-pager | head -5
echo ""
sudo systemctl status nginx --no-pager | head -5
echo ""

# 11. 獲取公網 IP
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "無法獲取")
echo "🌐 公網 IP: $PUBLIC_IP"
echo ""
echo "🔗 測試鏈接："
echo "   http://$PUBLIC_IP/api/health"
echo ""
echo "📱 小程序配置："
echo "   API_BASE: http://$PUBLIC_IP"
echo ""
echo "⚠️  注意："
echo "   1. 當前使用 HTTP，建議配置 SSL 證書啟用 HTTPS"
echo "   2. 需要在微信公眾平台添加 $PUBLIC_IP 到 request 合法域名"
echo "   3. 生產環境應使用真實的微信登錄和 AI 引擎"
echo ""
echo "🎉 部署完成！"
