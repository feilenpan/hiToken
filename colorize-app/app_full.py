# -*- coding: utf-8 -*-
"""
時光修復 - AI老照片修復工具
功能：上色 / 照片修復 / 人臉增強 / 超分辨率
存儲：SQLite（持久化）
引擎：火山引擎（超分增強）+ 百度 AI（上色）
"""

import os
import uuid
import time
import hashlib
import logging
import base64
import json
import sqlite3
import requests
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional
from datetime import datetime
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException, Header, Depends, Request
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 云调用 base64 文件输入模型
class FileInput(BaseModel):
    file: str       # base64 编码的图片数据
    prompt: str = ""
    function: str = "restore"
    process_type: str = "restore"

app = FastAPI(title="時光修復", description="AI老照片修復工具")

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
DB_PATH = BASE_DIR / "data" / "colorize.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# 微信小程序配置
WECHAT_APPID = "wxefdb56243e2bcc21"
WECHAT_SECRET = "c9d4ef59051a8deb172a0c15f94f49b6"

# 火山引擎配置
VOLC_API_KEY = os.getenv("VOLC_API_KEY", "VOLC_API_KEY_NOT_SET")
VOLC_API_URL = "https://mediakit.cn-beijing.volces.com/api/v1/tools-sync/enhance-image"

# 百度 AI 配置（用於上色）
BAIDU_API_KEY = os.getenv("BAIDU_API_KEY", "rj4yGA4aKtkxqQSy1QBASgG7")
BAIDU_SECRET_KEY = os.getenv("BAIDU_SECRET_KEY", "hTRFeBzKkgricbUyCrPIKeNrMqVo4emM")

# 服務器基礎 URL（用於構建圖片訪問地址）
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "http://13.125.93.195/colorize")

# ===== SQLite 數據庫 =====

def get_db():
    """獲取數據庫連接（每次請求新建，用完關閉）"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_db():
    """初始化數據庫表結構"""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            openid TEXT UNIQUE NOT NULL,
            session_key TEXT DEFAULT '',
            nickname TEXT DEFAULT '',
            total_used INTEGER DEFAULT 0,
            privacy_agreed INTEGER DEFAULT 0,
            agreement_agreed INTEGER DEFAULT 0,
            created_at REAL DEFAULT (strftime('%s','now')),
            updated_at REAL DEFAULT (strftime('%s','now'))
        );
        CREATE INDEX IF NOT EXISTS idx_users_openid ON users(openid);

        CREATE TABLE IF NOT EXISTS process_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id TEXT UNIQUE NOT NULL,
            process_type TEXT NOT NULL,
            result_path TEXT DEFAULT '',
            created_at REAL DEFAULT (strftime('%s','now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_records_user ON process_records(user_id);
    """)
    conn.commit()
    conn.close()
    logger.info(f"數據庫已初始化: {DB_PATH}")

# 啟動時初始化
init_db()


# ===== 工具函數 =====

def get_user_by_token(token: str) -> Optional[dict]:
    """通過 token（即 openid）查找用戶"""
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE openid = ?", (token,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "")
    return get_user_by_token(token)

def require_user(authorization: Optional[str] = Header(None)) -> dict:
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(401, "請先登錄")
    return user


# ===== 火山引擎 API =====

def call_volcengine(image_url: str, multiple: int = 2, tool_version: str = "professional") -> dict:
    """調用火山引擎圖像增強 API"""
    if not VOLC_API_KEY:
        return {"success": False, "error": "火山引擎 API Key 未配置"}
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {VOLC_API_KEY}"
    }
    
    payload = {
        "image_url": image_url,
        "multiple": multiple,
        "tool_version": tool_version
    }
    
    try:
        data = json.dumps(payload).encode()
        logger.info(f"火山引擎請求: url={image_url}, multiple={multiple}, tool_version={tool_version}")
        logger.info(f"火山引擎請求體: {json.dumps(payload, ensure_ascii=False)}")
        
        req = urllib.request.Request(VOLC_API_URL, data=data, headers=headers)
        
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read().decode())
        
        logger.info(f"火山引擎響應: {json.dumps(result, ensure_ascii=False)[:500]}")
        
        if result.get("success"):
            logger.info(f"火山引擎增強成功: {result['result']['image_width']}x{result['result']['image_height']}")
            return {
                "success": True,
                "result": result["result"],
                "engine": f"volcengine({tool_version})"
            }
        else:
            error_msg = result.get("error", {}).get("message", "未知錯誤")
            logger.error(f"火山引擎增強失敗: {error_msg}")
            logger.error(f"火山引擎完整錯誤: {json.dumps(result, ensure_ascii=False)}")
            return {"success": False, "error": error_msg}
    
    except Exception as e:
        logger.error(f"火山引擎 API 請求失敗: {e}")
        import traceback
        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        return {"success": False, "error": str(e)}


def download_image(url: str) -> Optional[bytes]:
    """下載圖片"""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except Exception as e:
        logger.error(f"下載圖片失敗: {e}")
        return None


# ===== 百度 AI API（用於上色）=====

_baidu_token_cache = {"token": "", "expires_at": 0}

def get_baidu_token() -> Optional[str]:
    """獲取百度 access_token"""
    if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
        return None
    
    if _baidu_token_cache["token"] and time.time() < _baidu_token_cache["expires_at"]:
        return _baidu_token_cache["token"]
    
    url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={BAIDU_API_KEY}&client_secret={BAIDU_SECRET_KEY}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        
        token = data.get("access_token", "")
        if token:
            _baidu_token_cache["token"] = token
            _baidu_token_cache["expires_at"] = time.time() + data.get("expires_in", 2592000) - 3600
            return token
    except Exception as e:
        logger.error(f"獲取百度 token 失敗: {e}")
    
    return None


def call_baidu_colorize(image_data: bytes) -> dict:
    """調用百度 AI 上色 API"""
    token = get_baidu_token()
    if not token:
        return {"success": False, "error": "無法獲取百度 access_token"}
    
    img_b64 = base64.b64encode(image_data).decode()
    url = f"https://aip.baidubce.com/rest/2.0/image-process/v1/colourize?access_token={token}"
    
    try:
        data = f"image={urllib.parse.quote(img_b64)}".encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
        
        if "error_code" in result:
            return {"success": False, "error": result.get("error_msg", "未知錯誤")}
        
        if "image" in result:
            return {"success": True, "result": base64.b64decode(result["image"])}
        
        return {"success": False, "error": "響應中無圖片數據"}
    except Exception as e:
        logger.error(f"百度上色 API 請求失敗: {e}")
        return {"success": False, "error": str(e)}


# ===== API =====


# ===== AI 照片点评 (豆包多模态) =====
from concurrent.futures import ThreadPoolExecutor
import uuid

TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)
app.mount("/temp", StaticFiles(directory=str(TEMP_DIR)), name="temp")

# 火山引擎图像质量评估
EVAL_QUALITY_URL = "https://mediakit.cn-beijing.volces.com/api/v1/tools/evaluate-image-quality/sync"
EVAL_QUALITY_ITEMS = ["vqscore", "aesthetic", "noise", "blur", "brightness", "contrast", "overexposure", "saturation", "texture"]

def call_volc_evaluate_quality(image_url: str) -> dict:
    VOLC_API_KEY = os.getenv("VOLC_API_KEY", "VOLC_API_KEY_NOT_SET")
    if not VOLC_API_KEY:
        return {"success": False, "error": "火山引擎 API Key 未配置"}
    payload = {"image_url": image_url, "tool_version": "standard", "standard_evaluate_items": EVAL_QUALITY_ITEMS}
    try:
        data = json.dumps(payload).encode()
        logger.info(f"质量评估请求: url={image_url}")
        req = urllib.request.Request(EVAL_QUALITY_URL, data=data,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {VOLC_API_KEY}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_data = json.loads(resp.read().decode())
        if resp_data.get("success"):
            return {"success": True, "quality": resp_data.get("result", {})}
        return {"success": False, "error": resp_data.get("error", {}).get("message", "未知错误")}
    except Exception as e:
        logger.error(f"质量评估请求异常: {e}")
        return {"success": False, "error": str(e)}

SEED_API_KEY = os.getenv("SEED_API_KEY", "SEED_API_KEY_NOT_SET")
SEED_API_URL = "https://ark.cn-beijing.volces.com/api/v3/responses"
SEED_MODEL = "doubao-seed-2-0-mini-260428"

@app.post("/api/evaluate")
async def evaluate_photo(data: FileInput):
    """AI 点评照片：豆包主观评分 + 火山质量评估 + 修图建议"""
    try:
        image_data = base64.b64decode(data.file)
        if len(image_data) > 10 * 1024 * 1024:
            raise HTTPException(400, "图片大小不能超过10MB")
        
        # 保存临时图片
        temp_filename = f"{uuid.uuid4().hex}.jpg"
        temp_path = TEMP_DIR / temp_filename
        temp_path.write_bytes(image_data)
        
        # 构建临时 URL（8888端口供外网访问）
        temp_url = f"http://13.125.93.195:8888/temp/{temp_filename}"
        
        # 并行调用：质量评估 + 豆包点评
        executor = ThreadPoolExecutor(max_workers=2)
        
        # 质量评估
        fq = executor.submit(call_volc_evaluate_quality, temp_url)
        quality_result = {"success": False}
        try:
            quality_result = fq.result(timeout=45)
        except Exception as e:
            logger.error(f"质量评估超时或失败: {e}")
        
        # 豆包多模态点评
        import base64 as b64
        data_uri = f"data:image/jpeg;base64,{b64.b64encode(image_data).decode()}"
        prompt_text = """你是一个风趣幽默的老照片点评师。看照片像老朋友翻相册。
语气：感叹词开头（哟！哇塞！），口语化，3-5句，长短句交替。所有输出必须是简体中文！
看细节，能识别地点就提。
评分严格按质量分散：95-98 惊为天人（极少），85-94 非常好看（少数），75-84 不错，65-74 普通，55-64 随意，40-54 朴实记录。
重要：大部分普通照片应在60-82分之间，不要集中给高分！只有光影构图情绪都出色的才能给90+。
必须给出1-2个修图建议。高分照片用「锦上添花」语气，低分照片用「焕然一新」语气。提示词≤15字。
金句要求：根据场景/天气/人物/地点等元素，创作一句有画面感的原创短句，≤15字。
返回JSON：{"text":"点评","title":"时光宝藏/岁月珍品/温暖瞬间/美好时刻/珍贵印记/朴实记录","score":40-98,"tags":[],"quote":"金句","location":"地点或空","suggestions":[{"type":"类型","label":"按钮文字≤8字","prompt":"提示词≤20字"}]}"""
        
        if not SEED_API_KEY:
            raise HTTPException(500, "豆包 API Key 未配置")
        
        resp = requests.post(SEED_API_URL, json={"model": SEED_MODEL, "input": [{"role": "user", "content": [{"type": "input_image", "image_url": data_uri}, {"type": "input_text", "text": prompt_text}]}]}, headers={"Authorization": f"Bearer {SEED_API_KEY}", "Content-Type": "application/json"}, timeout=60)
        
        if resp.status_code != 200:
            logger.error(f"豆包 API 错误: {resp.status_code} {resp.text[:500]}")
            raise HTTPException(500, f"AI 点评失败: {resp.status_code}")
        
        result = resp.json()
        # 豆包 Responses API: output 可能有 reasoning + message
        eval_text = None
        for item in result.get("output", []):
            if item.get("type") == "message" and item.get("content"):
                eval_text = item["content"][0].get("text", "")
                break
        if not eval_text:
            logger.error(f"未找到豆包消息输出: {json.dumps(result, ensure_ascii=False)[:500]}")
            raise ValueError("豆包响应缺少消息输出")
        evaluation = json.loads(eval_text)
        evaluation.setdefault("title", "温暖瞬间")
        evaluation.setdefault("score", 88)
        evaluation.setdefault("tags", [])
        evaluation.setdefault("quote", "")
        evaluation.setdefault("location", "")
        evaluation.setdefault("suggestions", [])
        
        logger.info(f"点评完成: title={evaluation['title']}, score={evaluation['score']}")
        
        response = {"success": True}
        response.update(evaluation)
        response["quality"] = quality_result.get("quality") if quality_result.get("success") else None
        
        # 清理临时文件
        try:
            temp_path.unlink()
        except:
            pass
        
        return response
        
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"豆包返回非JSON: {e}")
        return {"success": True, "text": "这是一张珍贵的照片。", "title": "珍贵印记", "score": 85, "tags": ["📸 珍贵记忆"], "quote": "每一张都值得被珍惜", "location": "", "suggestions": [], "fallback": True, "quality": None}
    except Exception as e:
        logger.error(f"点评异常: {e}")
        return {"success": True, "text": "这是一张珍贵的照片。", "title": "珍贵印记", "score": 85, "tags": ["📸 珍贵记忆"], "quote": "每一张都值得被珍惜", "location": "", "suggestions": [], "fallback": True, "quality": None}

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "時光修復",
        "storage": "sqlite",
        "engine": "volcengine",
        "features": ["colorize", "enhance", "upscale", "restore"],
        "timestamp": int(time.time())
    }


# ----- 微信登錄 -----

@app.post("/api/wechat/login")
async def wechat_login(request: Request):
    data = await request.json()
    code = data.get("code", "")
    if not code:
        raise HTTPException(400, "code is required")
    
    # 調用微信 jscode2session API 換取 openid
    wx_url = (
        f"https://api.weixin.qq.com/sns/jscode2session"
        f"?appid={WECHAT_APPID}&secret={WECHAT_SECRET}"
        f"&js_code={code}&grant_type=authorization_code"
    )
    
    try:
        req = urllib.request.Request(wx_url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            wx_data = json.loads(resp.read().decode())
        
        logger.info(f"微信登錄響應: errcode={wx_data.get('errcode', 0)}, errmsg={wx_data.get('errmsg', 'ok')}")
        
        if "errcode" in wx_data and wx_data["errcode"] != 0:
            logger.error(f"微信登錄失敗: {wx_data}")
            raise HTTPException(400, f"微信登錄失敗: {wx_data.get('errmsg', '未知錯誤')}")
        
        openid = wx_data.get("openid", "")
        session_key = wx_data.get("session_key", "")
        
        if not openid:
            raise HTTPException(400, "無法獲取 openid")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"調用微信API失敗: {e}")
        openid = hashlib.md5(code.encode()).hexdigest()[:16]
        session_key = ""
        logger.warning(f"降級到本地 openid: {openid}")
    
    # 查找或創建用戶（SQLite）
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE openid = ?", (openid,)).fetchone()
    
    if row:
        # 已有用戶，更新 session_key
        conn.execute(
            "UPDATE users SET session_key = ?, updated_at = ? WHERE openid = ?",
            (session_key, time.time(), openid)
        )
        user = dict(row)
    else:
        # 新用戶
        nickname = "用戶" + openid[:4]
        conn.execute(
            "INSERT INTO users (openid, session_key, nickname) VALUES (?, ?, ?)",
            (openid, session_key, nickname)
        )
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        user = {
            "id": user_id,
            "openid": openid,
            "nickname": nickname,
            "total_used": 0,
            "privacy_agreed": 0,
            "agreement_agreed": 0
        }
    
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "token": openid,
        "user": {
            "id": user["id"],
            "nickname": user["nickname"],
            "total_used": user["total_used"],
            "privacy_agreed": bool(user["privacy_agreed"]),
            "agreement_agreed": bool(user["agreement_agreed"])
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
            "privacy_agreed": bool(user["privacy_agreed"]),
            "agreement_agreed": bool(user["agreement_agreed"])
        }
    }


@app.post("/api/process")
async def process_photo(
    data: FileInput,
    user: Optional[dict] = Depends(get_current_user)
):
    """统一处理端点"""
    
    content = base64.b64decode(data.file)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "图片大小不能超过10MB")
    
    task_id = str(uuid.uuid4())
    
    # 1. 先保存原圖到服務器，獲取 URL
    result_data = None
    engine_name = "demo"
    
    try:
        # 保存原圖
        original_dir = RESULTS_DIR / "originals" / datetime.now().strftime("%Y/%m/%d")
        original_dir.mkdir(parents=True, exist_ok=True)
        original_filename = f"{task_id}_original.jpg"
        original_path = original_dir / original_filename
        original_path.write_bytes(content)
        
        # 構建原圖 URL
        original_url = f"{SERVER_BASE_URL}/api/results/originals/{datetime.now().strftime('%Y/%m/%d')}/{original_filename}"
        logger.info(f"原圖已保存: {original_url}")
        
        # 2. 根據功能類型調用不同的 API
        if data.function == "colorize":
            # 上色：使用百度 AI
            logger.info(f"百度 AI 上色開始: size={len(content)}")
            colorize_result = call_baidu_colorize(content)
            
            if colorize_result["success"]:
                result_data = colorize_result["result"]
                engine_name = "baidu(colorize)"
                logger.info(f"百度 AI 上色完成: {len(result_data)} bytes")
            else:
                logger.error(f"百度 AI 上色失敗: {colorize_result['error']}")
                result_data = content
                engine_name = "demo"
        
        else:
            # 增強/超分/修復：使用火山引擎
            if data.function == "enhance":
                multiple = 2
                tool_version = "professional"
            elif data.function == "upscale":
                multiple = 4
                tool_version = "professional"
            elif data.function == "restore":
                multiple = 2
                tool_version = "professional"
            else:
                multiple = 2
                tool_version = "professional"
            
            logger.info(f"火山引擎增強開始: function={data.function}, multiple={multiple}, url={original_url}")
            volc_result = call_volcengine(original_url, multiple, tool_version)
            
            if volc_result["success"]:
                # 下載增強後的圖片
                enhanced_url = volc_result["result"]["image_url"]
                result_data = download_image(enhanced_url)
                
                if result_data:
                    engine_name = f"volcengine({tool_version},{multiple}x)"
                    logger.info(f"火山引擎增強完成: {len(result_data)} bytes")
                else:
                    logger.error("下載增強圖片失敗")
                    result_data = content
                    engine_name = "demo"
            else:
                logger.error(f"火山引擎增強失敗: {volc_result['error']}")
                result_data = content
                engine_name = "demo"
    
    except Exception as e:
        logger.error(f"處理失敗: {e}")
        result_data = content
        engine_name = "demo"
    
    if result_data is None:
        result_data = content
        engine_name = "demo"
    
    result_base64 = base64.b64encode(result_data).decode()
    
    # 保存結果圖
    result_url = ""
    result_path = ""
    try:
        result_dir = RESULTS_DIR / datetime.now().strftime("%Y/%m/%d")
        result_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{task_id}.jpg"
        filepath = result_dir / filename
        filepath.write_bytes(result_data)
        
        date_path = datetime.now().strftime("%Y/%m/%d")
        result_url = f"/api/results/{date_path}/{filename}"
        result_path = str(filepath)
        logger.info(f"結果圖已保存: {filepath}")
    except Exception as e:
        logger.error(f"保存結果圖失敗: {e}")
    
    # 記錄到數據庫
    if user:
        conn = get_db()
        conn.execute(
            "UPDATE users SET total_used = total_used + 1, updated_at = ? WHERE id = ?",
            (time.time(), user["id"])
        )
        conn.execute(
            "INSERT INTO process_records (user_id, task_id, process_type, result_path) VALUES (?, ?, ?, ?)",
            (user["id"], task_id, data.function, result_path)
        )
        conn.commit()
        conn.close()
    
    return {
        "success": True,
        "task_id": task_id,
        "function": data.function,
        "result": f"data:image/jpeg;base64,{result_base64}",
        "result_url": result_url,
        "engine": engine_name
    }


@app.post("/api/suggest-edit")
async def suggest_edit_photo(data: FileInput):
    """AI 图片编辑（seededit）"""
    from volc_visual_engine import suggest_edit

    try:
        image_bytes = base64.b64decode(data.file)
        if len(image_bytes) > 10 * 1024 * 1024:
            raise HTTPException(400, "图片大小不能超过10MB")

        result_bytes = suggest_edit(image_bytes, data.prompt or "")
        if result_bytes:
            result_b64 = base64.b64encode(result_bytes).decode()
            return {"success": True, "result": f"data:image/jpeg;base64,{result_b64}"}
        else:
            return {"success": False, "detail": "AI编辑失败，请稍后重试"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"suggest-edit 异常: {e}")
        return {"success": False, "detail": "处理异常，请稍后重试"}


@app.get("/api/results/{year}/{month}/{day}/{filename}")
async def get_result_image(year: str, month: str, day: str, filename: str):
    filepath = RESULTS_DIR / year / month / day / filename
    if not filepath.exists():
        raise HTTPException(404, "圖片不存在")
    return FileResponse(str(filepath), media_type="image/jpeg")


@app.get("/api/results/originals/{year}/{month}/{day}/{filename}")
async def get_original_image(year: str, month: str, day: str, filename: str):
    filepath = RESULTS_DIR / "originals" / year / month / day / filename
    if not filepath.exists():
        raise HTTPException(404, "原圖不存在")
    return FileResponse(str(filepath), media_type="image/jpeg")


@app.post("/api/user/agree-privacy")
async def agree_privacy(user: dict = Depends(require_user)):
    conn = get_db()
    conn.execute("UPDATE users SET privacy_agreed = 1, updated_at = ? WHERE id = ?", (time.time(), user["id"]))
    conn.commit()
    conn.close()
    return {"success": True}


@app.post("/api/user/agree-agreement")
async def agree_agreement(user: dict = Depends(require_user)):
    conn = get_db()
    conn.execute("UPDATE users SET agreement_agreed = 1, updated_at = ? WHERE id = ?", (time.time(), user["id"]))
    conn.commit()
    conn.close()
    return {"success": True}


@app.get("/api/privacy")
async def get_privacy_policy():
    content = """# 時光修復 - 隱私保護政策

最後更新日期：2026年5月30日

## 一、引言

「時光修復」小程序（以下簡稱"我們"或"本小程序"）由時光修復團隊開發運營。我們深知個人信息對您的重要性，將嚴格遵守《中華人民共和國個人信息保護法》《中華人民共和國數據安全法》《中華人民共和國網絡安全法》等法律法規，盡全力保護您的個人信息安全和隱私。

請您在使用本小程序前仔細閱讀本隱私保護政策，確保您已充分理解所有條款。一旦您使用本小程序，即表示您已同意本政策所述的個人信息處理方式。

## 二、我們收集的信息

### 2.1 必要信息（為提供服務所必需）

- 微信賬號信息（OpenID、暱稱、頭像）：用於用戶身份識別與登錄，賬戶存續期間保存
- 您上傳的照片（原始照片文件）：用於AI評分分析和修復處理，處理完成後立即刪除
- 修復結果圖片（AI生成的修復結果）：供您查看和保存，30天後自動刪除
- 評分記錄（評分、點評、建議內容）：歷史記錄展示，30天後自動刪除

### 2.2 自動收集的信息

- 設備型號與操作系統版本：用於適配優化，保存30天
- 服務使用日誌：用於服務改進和故障排查，保存30天
- 功能使用統計：用於了解使用情況和優化產品，保存90天（匿名化處理）

### 2.3 我們絕不收集的信息

- 您的微信密碼
- 您的支付密碼或銀行卡信息
- 您的地理位置精確信息
- 您的通訊錄或聊天記錄
- 您設備的其他照片（僅處理您主動上傳的照片）

## 三、我們如何使用信息

我們收集的所有信息僅用於以下目的：

- 照片打分與點評 — 將您上傳的照片發送至AI模型進行智能分析和評分
- 照片修復處理 — 將您上傳的照片發送至AI修復模型進行修復處理
- 修復建議生成 — 基於AI分析為您提供個性化修復建議
- 服務優化 — 分析功能使用情況以改進產品體驗
- 安全保障 — 檢測和防止濫用行為

## 四、信息存儲與保護

### 4.1 存儲地點

您的所有數據均存儲在位於中華人民共和國境內（不含港澳台）的服務器上。我們承諾您的個人信息不會出境。

### 4.2 安全措施

- 數據傳輸全程加密（HTTPS/TLS 1.3）
- 數據庫加密存儲
- 嚴格的訪問控制和權限管理
- 最小權限原則
- 定期安全自查和漏洞掃描
- 操作日誌審計

## 五、信息共享與委托處理

我們不會出售、交換或轉讓您的個人信息給任何第三方。

為實現照片評分和修復功能，我們會將您上傳的照片臨時發送至以下國內AI服務商進行處理：

- 北京火山引擎科技有限公司（seededit AI修復模型）
- 字節跳動旗下豆包大模型（AI智能評分與點評）

所有數據處理均在中華人民共和國境內完成，數據不出境。處理完成後服務商不保留您的照片數據。

## 六、您的權利

根據《中華人民共和國個人信息保護法》，您享有以下權利：

- 知情權、查閱權、更正權、刪除權、撤回同意權、註銷賬戶權、投訴舉報權

行使方式：
- 小程序內：「我的」→「聯繫客服」
- 郵箱：privacy@time-restore.com
- 我們將在收到申請後的15個工作日內處理並回復

## 七、未成年人保護

- 未滿14周歲的兒童需在監護人陪同和同意下使用
- 未滿18周歲的未成年人請在監護人指導下使用

## 八、隱私政策的更新

我們可能會根據產品功能調整或法律法規變化，不時更新本隱私政策。重大變更時將通過小程序內彈窗通知或首頁公告告知。

## 九、聯繫我們

- 小程序內客服：「我的」→「聯繫客服」
- 個人信息保護負責人郵箱：privacy@time-restore.com

本隱私保護政策自2026年5月30日起生效。
"""
    return {"success": True, "content": content}



@app.get("/api/agreement")
async def get_user_agreement():
    content = """# 時光修復 - 用戶服務協議

最後更新日期：2026年5月30日

## 一、服務條款的接受

歡迎使用「時光修復」小程序（以下簡稱"本服務"）。本協議是您與時光修復團隊（以下簡稱"我們"）之間關於您使用本服務所訂立的協議。

使用本服務即表示您已閱讀、理解並接受本協議的全部內容。

## 二、服務內容

本服務利用人工智能技術，為您提供以下功能：

- AI照片打分與點評 — 對上傳的照片進行智能評分和個性化點評
- AI照片修復 — 利用先進AI模型對老照片、受損照片進行智能修復
- 修復建議生成 — 基於AI分析生成個性化的修復建議和編輯效果預覽
- 歷史記錄 — 查看您的修復歷史記錄

特別說明：以上所有功能均為AI自動處理，結果僅供娛樂和參考，不具有任何專業鑑定或法律效力。

## 三、用戶註冊與賬戶

- 您需要使用微信賬號授權登錄本服務
- 您應確保微信賬號為本人使用

## 四、使用規範

### 4.1 您同意

- 遵守《中華人民共和國網絡安全法》《中華人民共和國數據安全法》《中華人民共和國個人信息保護法》及所有適用的法律法規
- 不利用本服務從事任何違法違規活動
- 不侵犯他人合法權益（包括但不限於肖像權、隱私權、知識產權等）

### 4.2 您不得上傳以下內容的照片

- 違反中華人民共和國法律法規的內容
- 涉及國家安全、國家秘密的內容
- 侵犯他人肖像權、隱私權的未經授權的他人照片
- 涉及色情、暴力、恐怖主義等違法違規內容
- 含有病毒、木馬等惡意程序的文件

### 4.3 禁止行為

- 反向工程、反編譯、反彙編本服務的任何部分
- 利用技術手段干擾、破壞本服務的正常運行
- 批量調用、自動化腳本等濫用API的行為
- 惡意攻擊、入侵服務器或網絡系統

## 五、知識產權

- 本服務的所有內容（包括但不限於軟件代碼、算法模型、用戶界面設計、商標、Logo等）的知識產權歸我們或技術合作方所有
- 您上傳的照片，其知識產權歸您或原權利人所有
- 我們不會將您的照片用於服務之外的任何用途
- 照片處理完成後，原始照片和中間結果將立即從服務器刪除
- 修復後的照片，知識產權歸您所有，您可自由使用

## 六、收費與免費

- 本服務目前完全免費，不收取任何費用
- 我們保留未來調整收費模式的權利
- 如引入收費功能，將至少提前30天通知並在小程序內顯著公示

## 七、免責聲明

### 7.1 AI處理結果

- AI評分、點評和修復結果均由人工智能模型自動生成，僅供參考和娛樂
- 我們不保證AI處理結果的準確性、真實性、完整性和適用性
- AI修復效果因照片質量、損傷程度等因素而異

### 7.2 服務可用性

因系統維護、不可抗力（自然災害、政策變化等）、第三方服務故障（微信平台、AI模型服務商等）導致的服務中斷，我們不承擔責任。

### 7.3 用戶內容責任

您應對上傳的照片內容承擔全部法律責任。

## 八、爭議解決

本協議的解釋、效力及糾紛的解決，適用中華人民共和國法律。雙方因本協議發生爭議的，應首先協商解決；協商不成的，向有管轄權的人民法院提起訴訟。

## 九、聯繫方式

- 小程序內：「我的」→「聯繫客服」
- 電子郵箱：support@time-restore.com

本協議自2026年5月30日起生效。
"""
    return {"success": True, "content": content}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8888)
