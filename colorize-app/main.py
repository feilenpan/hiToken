"""
时光上色 - AI 老照片上色工具
Colorize Your Memories
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import time
from pathlib import Path
from PIL import Image
import io
import base64

# 导入 Palette API 模块
from palette_api import colorize_image as palette_colorize, check_health

app = FastAPI(title="时光上色", description="AI 老照片上色工具")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 目录
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("output")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# 简单的内存存储（生产环境用数据库）
users_db = {}
tasks_db = {}

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/colorize")
async def colorize_image_api(file: UploadFile = File(...)):
    """
    上传黑白照片并上色（使用 Palette.fm API）
    """
    # 验证文件类型
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "请上传图片文件")
    
    # 生成唯一ID
    task_id = str(uuid.uuid4())
    
    # 读取文件
    content = await file.read()
    
    # 验证文件大小（最大10MB）
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "图片大小不能超过10MB")
    
    # 记录任务
    tasks_db[task_id] = {
        "status": "processing",
        "created_at": time.time(),
        "filename": file.filename,
    }
    
    # 调用 Palette API 上色
    try:
        result = palette_colorize(
            image_data=content,
            prompt="vintage photo, natural colors, realistic",
            resolution="full_hd",
            auto_color=True,
            white_balance=True
        )
        
        if result["success"]:
            tasks_db[task_id]["status"] = "completed"
            tasks_db[task_id]["mock"] = result.get("mock", False)
            
            return {
                "success": True,
                "task_id": task_id,
                "result": result["image_base64"],
                "message": "上色完成！",
                "mock": result.get("mock", False)  # 开发模式标记
            }
        else:
            tasks_db[task_id]["status"] = "failed"
            raise HTTPException(500, f"上色失败: {result.get('error', 'Unknown error')}")
            
    except HTTPException:
        raise
    except Exception as e:
        tasks_db[task_id]["status"] = "failed"
        raise HTTPException(500, f"上色失败: {str(e)}")

@app.get("/api/download/{task_id}")
async def download_result(task_id: str):
    """下载上色后的图片"""
    if task_id not in tasks_db:
        raise HTTPException(404, "任务不存在")
    
    task = tasks_db[task_id]
    if task["status"] != "completed":
        raise HTTPException(400, "任务尚未完成")
    
    # 从 result 中获取 base64 数据并返回
    if "result_base64" in task:
        import base64
        from fastapi.responses import Response
        image_data = base64.b64decode(task["result_base64"].split(",")[1])
        return Response(content=image_data, media_type="image/png")
    
    raise HTTPException(404, "图片数据不存在")


@app.get("/api/health")
async def health():
    """健康检查"""
    api_ok = check_health()
    return {
        "status": "ok" if api_ok else "degraded",
        "service": "时光上色 v1.0",
        "palette_api": "connected" if api_ok else "disconnected",
        "mode": "production" if os.getenv("RAPIDAPI_KEY") else "development"
    }


@app.get("/api/user/credits")
async def get_user_credits():
    """获取用户额度（开发模式返回默认值）"""
    # TODO: 实现真实的用户额度系统
    return {
        "free_credits": 3,
        "paid_credits": 0,
        "total_used": 0
    }

@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page():
    with open("templates/pricing.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/about", response_class=HTMLResponse)
async def about_page():
    with open("templates/about.html", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)
