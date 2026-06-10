# -*- coding: utf-8 -*-
"""
时光修复 - AI老照片修复工具 免费版
功能：上色 / 照片修复 / 人脸增强 / 超分辨率
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

from photo_ai_engine import process_image, get_available_features, check_health, PROCESS_TYPES
from database import (
    init_db,
    get_user_by_openid, create_user,
    create_colorize_record, update_colorize_record,
    get_user_records,
    update_user_privacy_agreement, update_user_agreement,
    create_deletion_request, delete_user_records
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="时光修复", description="AI老照片修复工具 - 免费版")

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

def get_result_dir() -> Path:
    today = datetime.now().strftime("%Y/%m/%d")
    d = RESULTS_DIR / today
    d.mkdir(parents=True, exist_ok=True)
    return d


# ===== 工具函数 =====

def get_current_user(
    x_token: Optional[str] = Header(None, alias="X-Token"),
    authorization: Optional[str] = Header(None)
) -> Optional[dict]:
    """支持两种认证方式：X-Token 或 Authorization: Bearer <token>"""
    token = None
    
    # 优先使用 X-Token
    if x_token:
        token = x_token
    # 兼容 Authorization: Bearer <token>
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
    
    if not token:
        return None
    try:
        return get_user_by_openid(token)
    except:
        return None

def require_user(
    x_token: Optional[str] = Header(None, alias="X-Token"),
    authorization: Optional[str] = Header(None)
) -> dict:
    user = get_current_user(x_token, authorization)
    if not user:
        raise HTTPException(401, "请先登录")
    return user


# ===== 请求模型 =====

class ProcessRequest(BaseModel):
    process_type: str  # colorize | enhance | face_enhance | upscale


# ===== 页面 =====

@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(str(BASE_DIR / "templates" / "index.html"))

@app.get("/about", response_class=HTMLResponse)
async def about_page():
    return FileResponse(str(BASE_DIR / "templates" / "about.html"))


# ===== API =====

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "时光修复 免费版",
        "engine": check_health(),
        "features": get_available_features(),
        "timestamp": int(time.time())
    }


@app.get("/api/features")
async def features():
    """返回可用功能列表"""
    return {"features": get_available_features()}


# ----- 微信登录 -----

@app.post("/api/wechat/login")
async def wechat_login(request: Request):
    data = await request.json()
    code = data.get("code", "")
    if not code:
        raise HTTPException(400, "code is required")
    
    # TODO: 生产环境调用 jscode2session
    openid = hashlib.md5(code.encode()).hexdigest()[:16]
    
    user = get_user_by_openid(openid)
    if not user:
        user = create_user(openid)
    
    return {
        "success": True,
        "token": user["openid"],
        "user": {
            "id": user["id"],
            "nickname": user["nickname"],
            "total_used": user["total_used"],
            "privacy_agreed": bool(user.get("privacy_agreed", 0)),
            "agreement_agreed": bool(user.get("agreement_agreed", 0))
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
            "privacy_agreed": bool(user.get("privacy_agreed", 0)),
            "agreement_agreed": bool(user.get("agreement_agreed", 0))
        }
    }


# ===== 核心：照片处理（统一端点） =====

@app.post("/api/process")
async def process_photo(
    file: UploadFile = File(...),
    process_type: str = "colorize",
    user: Optional[dict] = Depends(get_current_user)
):
    """
    统一处理端点
    process_type: colorize | enhance | face_enhance | upscale
    
    流程：
    1. 上传图片 → 内存处理（原图不落盘）
    2. AI处理 → 结果图存磁盘
    3. 返回 base64 + 图片URL
    """
    # 验证处理类型
    if process_type not in PROCESS_TYPES:
        raise HTTPException(400, f"不支持的处理类型: {process_type}，可选: {list(PROCESS_TYPES.keys())}")
    
    # 验证文件
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "请上传图片文件")
    
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "图片大小不能超过10MB")
    
    task_id = str(uuid.uuid4())
    process_name = PROCESS_TYPES[process_type]["name"]
    
    # 记录
    if user:
        create_colorize_record(task_id, user["id"], file.filename or "", len(content), 0, 0)
    
    # AI处理
    result = process_image(content, process_type)
    
    if not result["success"]:
        if user:
            update_colorize_record(task_id, "failed")
        raise HTTPException(500, f"{process_name}失败: {result.get('error')}")
    
    # 结果图存盘
    result_url = ""
    try:
        img_data = result["image_base64"]
        if "," in img_data:
            img_data = img_data.split(",", 1)[1]
        img_bytes = base64.b64decode(img_data)
        
        result_dir = get_result_dir()
        filename = f"{task_id}.jpg"
        filepath = result_dir / filename
        filepath.write_bytes(img_bytes)
        
        date_path = datetime.now().strftime("%Y/%m/%d")
        result_url = f"/api/results/{date_path}/{filename}"
        logger.info(f"结果图已保存: {filepath} ({len(img_bytes)} bytes)")
    except Exception as e:
        logger.error(f"保存结果图失败: {e}")
    
    # 更新记录
    if user:
        update_colorize_record(task_id, "completed", result_url=result_url)
    
    return {
        "success": True,
        "task_id": task_id,
        "process_type": process_type,
        "process_name": process_name,
        "result": result["image_base64"],
        "result_url": result_url,
        "engine": result.get("engine", "unknown")
    }


# ===== 兼容旧端点 =====

@app.post("/api/colorize")
async def colorize_api(
    file: UploadFile = File(...),
    user: Optional[dict] = Depends(get_current_user)
):
    """兼容旧的上色端点，内部转发到 /api/process"""
    return await process_photo(file=file, process_type="colorize", user=user)


# ===== 结果图访问 =====

@app.get("/api/results/{year}/{month}/{day}/{filename}")
async def get_result_image(year: str, month: str, day: str, filename: str):
    filepath = RESULTS_DIR / year / month / day / filename
    if not filepath.exists():
        raise HTTPException(404, "图片不存在")
    return FileResponse(str(filepath), media_type="image/jpeg")


# ===== 历史记录 =====

@app.get("/api/wechat/records")
async def get_records(user: dict = Depends(require_user)):
    records = get_user_records(user["id"])
    return {"records": records}


# ===== 协议 =====

@app.post("/api/user/agree-privacy")
async def agree_privacy(user: dict = Depends(require_user)):
    update_user_privacy_agreement(user["openid"])
    return {"success": True}

@app.post("/api/user/agree-agreement")
async def agree_agreement(user: dict = Depends(require_user)):
    update_user_agreement(user["openid"])
    return {"success": True}

@app.post("/api/user/request-deletion")
async def request_deletion(user: dict = Depends(require_user)):
    records = get_user_records(user["id"], limit=9999)
    deleted_count = 0
    for r in records:
        if r.get("result_url"):
            fpath = BASE_DIR / r["result_url"].lstrip("/")
            if fpath.exists():
                fpath.unlink()
                deleted_count += 1
    delete_user_records(user["openid"])
    create_deletion_request(user["openid"])
    return {"success": True, "message": f"已删除 {deleted_count} 张结果图和所有记录"}


# ===== 启动清理 =====

@app.on_event("startup")
async def startup_cleanup():
    # 初始化数据库（创建表）
    init_db()
    logger.info("数据库初始化完成")
    
    import shutil
    now = time.time()
    cutoff = now - 30 * 86400
    cleaned = 0
    try:
        for year_dir in RESULTS_DIR.iterdir():
            if not year_dir.is_dir(): continue
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir(): continue
                for day_dir in month_dir.iterdir():
                    if not day_dir.is_dir(): continue
                    if day_dir.stat().st_mtime < cutoff:
                        shutil.rmtree(day_dir)
                        cleaned += 1
        if cleaned > 0:
            logger.info(f"启动清理：删除了 {cleaned} 个过期目录")
    except Exception as e:
        logger.error(f"启动清理失败: {e}")


# ===== 合规性接口 =====

@app.get("/api/privacy")
async def get_privacy_policy():
    content = """# 时光修复 - 隐私保护政策

最后更新日期：2026年5月16日

一、引言
欢迎使用「时光修复」。我们非常重视您的隐私保护。

二、我们收集的信息
- 上传的照片：仅用于AI处理，原图不会保存
- 处理结果：保存在服务器，30天后自动删除
- 设备信息：用于兼容性优化

三、我们提供的服务
- AI上色：黑白照片智能上色
- 照片修复：修复折痕、污渍、损伤
- 人脸增强：模糊人脸变清晰
- 超分辨率：低清照片变高清

四、信息保护
- 您的原图仅在内存中处理，不会保存到服务器
- 处理结果保存30天后自动删除
- 所有数据传输使用HTTPS加密
- 不会出售或分享您的个人信息

五、您的权利
- 您可随时申请删除所有数据
- 联系邮箱：privacy@colorize-hk.com

本隐私政策自2026年5月16日起生效。"""
    return {"success": True, "content": content}


@app.get("/api/agreement")
async def get_user_agreement():
    content = """# 时光修复 - 用户服务协议

最后更新日期：2026年5月16日

一、服务条款
使用本服务即表示您同意本协议。

二、服务内容
AI老照片修复工具，完全免费使用。
- AI上色：黑白照片智能上色
- 照片修复：修复折痕、污渍、损伤
- 人脸增强：模糊人脸变清晰
- 超分辨率：低清照片变高清

三、使用规范
- 请勿上传违法违规内容
- 请勿对服务进行反向工程或攻击

四、知识产权
您上传的照片知识产权归您所有。

五、联系我们
- 邮箱：support@colorize-hk.com"""
    return {"success": True, "content": content}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8888)
