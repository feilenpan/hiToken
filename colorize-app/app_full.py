# -*- coding: utf-8 -*-
"""
时光修复 - AI老照片修复工具
功能：上色 / 照片修复 / 人脸增强 / 超分辨率
存储：SQLite（持久化）
引擎：火山引擎（超分增强）+ 百度 AI（上色）
"""

import os
import uuid
import random
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

app = FastAPI(title="时光修复", description="AI老照片修复工具")

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

# 百度 AI 配置（用于上色）
BAIDU_API_KEY = os.getenv("BAIDU_API_KEY", "rj4yGA4aKtkxqQSy1QBASgG7")
BAIDU_SECRET_KEY = os.getenv("BAIDU_SECRET_KEY", "hTRFeBzKkgricbUyCrPIKeNrMqVo4emM")

# 服务器基础 URL（用于构建图片访问地址）
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "https://yushu-264118-8-1438528191.sh.run.tcloudbase.com")

# ===== SQLite 数据库 =====

# 每日配额配置
DAILY_QUOTA = {
    "evaluate": 10,   # AI 点评（doubao）
    "process": 5,     # AI 处理（seededit）
}

def get_db():
    """获取数据库连接（每次请求新建，用完关闭）"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_db():
    """初始化数据库表结构"""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            openid TEXT UNIQUE NOT NULL,
            session_key TEXT DEFAULT '',
            nickname TEXT DEFAULT '',
            avatar TEXT DEFAULT '',
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

        CREATE TABLE IF NOT EXISTS daily_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            usage_type TEXT NOT NULL,
            usage_date TEXT NOT NULL,
            count INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, usage_type, usage_date)
        );
        CREATE INDEX IF NOT EXISTS idx_daily_usage ON daily_usage(user_id, usage_date);
    """)
    # 迁移：已有数据库添加 avatar 列
    try:
        conn.execute("ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT ''")
        logger.info("数据库迁移: 添加 avatar 列")
    except sqlite3.OperationalError:
        pass  # 列已存在
    conn.commit()
    conn.close()
    logger.info(f"数据库已初始化: {DB_PATH}")

# 启动时初始化
init_db()


def check_and_use_quota(user_id: int, usage_type: str) -> dict:
    """检查并消耗每日配额。返回 {allowed: bool, remaining: int, limit: int}"""
    today = datetime.now().strftime("%Y-%m-%d")
    limit = DAILY_QUOTA.get(usage_type, 5)
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT count FROM daily_usage WHERE user_id=? AND usage_type=? AND usage_date=?",
            (user_id, usage_type, today)
        ).fetchone()
        current = row["count"] if row else 0

        if current >= limit:
            return {"allowed": False, "remaining": 0, "limit": limit}

        # 递增计数
        if row:
            conn.execute(
                "UPDATE daily_usage SET count=count+1 WHERE user_id=? AND usage_type=? AND usage_date=?",
                (user_id, usage_type, today)
            )
        else:
            conn.execute(
                "INSERT INTO daily_usage (user_id, usage_type, usage_date, count) VALUES (?,?,?,1)",
                (user_id, usage_type, today)
            )
        conn.commit()
        remaining = limit - current - 1
        return {"allowed": True, "remaining": remaining, "limit": limit}
    finally:
        conn.close()


def get_user_quota(user_id: int) -> dict:
    """获取用户当前剩余配额"""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    try:
        result = {}
        for usage_type, limit in DAILY_QUOTA.items():
            row = conn.execute(
                "SELECT count FROM daily_usage WHERE user_id=? AND usage_type=? AND usage_date=?",
                (user_id, usage_type, today)
            ).fetchone()
            used = row["count"] if row else 0
            result[usage_type] = {"used": used, "remaining": max(0, limit - used), "limit": limit}
        return result
    finally:
        conn.close()


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

TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)
app.mount("/temp", StaticFiles(directory=str(TEMP_DIR)), name="temp")

SEED_API_KEY = os.getenv("SEED_API_KEY", "SEED_API_KEY_NOT_SET")
SEED_API_URL = "https://ark.cn-beijing.volces.com/api/v3/responses"
SEED_MODEL = "doubao-seed-2-0-mini-260428"

# 点评师角色库
REVIEWERS = [
    {"name": "老张", "emoji": "😂", "persona": "风趣幽默的老照片点评师", "tone": "口语化像老友唠嗑，带点调侃但暖心，3-5句，长短句交替"},
    {"name": "小鱼", "emoji": "💕", "persona": "温柔治愈的文艺女青年", "tone": "以「这张照片让我想起…」起头，细腻感性，多用比喻和拟人，像写信一样娓娓道来，3-4句"},
    {"name": "阿Ken", "emoji": "🎨", "persona": "毒舌但心地善良的艺术评论家", "tone": "以「嗯…」沉吟起头，先挑刺再夸，带点冷幽默，3-4句"},
    {"name": "老王", "emoji": "📸", "persona": "资深摄影老法师", "tone": "以专业术语起头如「这个构图…」「这光线…」，术语夹杂白话，惜字如金，2-3句"},
    {"name": "丫丫", "emoji": "🌟", "persona": "元气满满的少女点评师", "tone": "以「哇！这张好…」惊叹起头，活泼可爱，善用emoji，网络热词，元气满满，3-4句"},
    {"name": "老周", "emoji": "🧙", "persona": "阅片无数的神秘老法师", "tone": "以「细细看来…」沉吟起头，玄学风格，从照片看故事和人生，带禅意，3-4句"},
]

def get_random_reviewer():
    return random.choice(REVIEWERS)

@app.post("/api/evaluate")
async def evaluate_photo(data: FileInput, user: Optional[dict] = Depends(get_current_user)):
    """AI 点评照片：豆包多模态主观评分 + 修图建议"""
    try:
        # 配额检查
        if user:
            quota = check_and_use_quota(user["id"], "evaluate")
            if not quota["allowed"]:
                raise HTTPException(429, f"今日点评次数已用完（{quota['limit']}次/天），明天再来吧～")
        image_data = base64.b64decode(data.file)
        if len(image_data) > 10 * 1024 * 1024:
            raise HTTPException(400, "图片大小不能超过10MB")
        
        # 图片预处理：缩放到最长边1024px，压缩体积加速火山API调用
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(image_data))
        img = img.convert("RGB")
        w, h = img.size
        MAX_DIM = 768
        if max(w, h) > MAX_DIM:
            ratio = MAX_DIM / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        image_data = buf.getvalue()
        
        # 豆包多模态点评（直接 data URI，无需保存临时文件）
        import base64 as b64
        data_uri = f"data:image/jpeg;base64,{b64.b64encode(image_data).decode()}"
        reviewer = get_random_reviewer()

        prompt_text = f"""你是{reviewer['persona']}，{reviewer['tone']}。输出简体中文。
评分40-98自然分散，普通照60-82，极出色才90+。能识别地点就提。
1-3个修图建议，质量修复和创意编辑各至少一。建议≤20字。金句≤15字有画面感。
返回JSON：{{"text":"点评","title":"时光宝藏/岁月珍品/温暖瞬间/美好时刻/珍贵印记/朴实记录","score":40-98,"tags":[],"quote":"金句","location":"地点或空","suggestions":[{{"type":"quality/creative","label":"≤10字","prompt":"≤20字"}}]}}"""
        
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
        response["reviewer"] = reviewer["name"]
        response["reviewer_emoji"] = reviewer["emoji"]
        if user:
            response["quota"] = get_user_quota(user["id"])
        
        return response
        
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"豆包返回非JSON: {e}")
        return {"success": True, "text": "这是一张珍贵的照片。", "title": "珍贵印记", "score": 85, "tags": ["📸 珍贵记忆"], "quote": "每一张都值得被珍惜", "location": "", "suggestions": [], "fallback": True}
    except Exception as e:
        logger.error(f"点评异常: {e}")
        return {"success": True, "text": "这是一张珍贵的照片。", "title": "珍贵印记", "score": 85, "tags": ["📸 珍贵记忆"], "quote": "每一张都值得被珍惜", "location": "", "suggestions": [], "fallback": True}

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "鱼数修照",
        "storage": "sqlite",
        "engine": "volcengine",
        "features": ["evaluate", "restore", "suggest-edit"],
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
        # 新用戶，nickname 留空等待用户自行设置
        conn.execute(
            "INSERT INTO users (openid, session_key) VALUES (?, ?)",
            (openid, session_key)
        )
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        user = {
            "id": user_id,
            "openid": openid,
            "nickname": "",
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
            "nickname": user.get("nickname", ""),
            "avatar": ("/api/avatar/" + str(user["id"])) if user.get("avatar") else "",
            "total_used": user["total_used"],
            "privacy_agreed": bool(user["privacy_agreed"]),
            "agreement_agreed": bool(user["agreement_agreed"])
        }
    }


@app.get("/api/user/info")
async def get_user_info(user: dict = Depends(require_user)):
    avatar = user.get("avatar", "")
    return {
        "success": True,
        "user": {
            "id": user["id"],
            "nickname": user.get("nickname", ""),
            "avatar": ("/api/avatar/" + str(user["id"])) if avatar else "",
            "total_used": user["total_used"],
            "privacy_agreed": bool(user["privacy_agreed"]),
            "agreement_agreed": bool(user["agreement_agreed"])
        }
    }


@app.post("/api/user/profile")
async def update_profile(
    request: Request,
    user: dict = Depends(require_user)
):
    """更新用户头像和昵称。avatar: base64, nickname: string"""
    try:
        data = await request.json()
    except:
        raise HTTPException(400, "请求体必须为 JSON")
    
    nickname = data.get("nickname", "").strip()
    avatar_b64 = data.get("avatar", "")
    
    conn = get_db()
    
    if nickname:
        # 合规：限制昵称长度
        nickname = nickname[:32]
        conn.execute(
            "UPDATE users SET nickname = ?, updated_at = ? WHERE id = ?",
            (nickname, time.time(), user["id"])
        )
    
    if avatar_b64:
        try:
            import base64 as b64
            avatar_data = b64.b64decode(avatar_b64)
            if len(avatar_data) > 2 * 1024 * 1024:
                raise HTTPException(400, "头像大小不能超过2MB")
            avatar_dir = os.path.join(os.path.dirname(__file__), "avatars")
            os.makedirs(avatar_dir, exist_ok=True)
            avatar_path = os.path.join(avatar_dir, f"{user['id']}.jpg")
            with open(avatar_path, "wb") as f:
                f.write(avatar_data)
            conn.execute(
                "UPDATE users SET avatar = ?, updated_at = ? WHERE id = ?",
                (f"{user['id']}.jpg", time.time(), user["id"])
            )
        except Exception as e:
            logger.error(f"保存头像失败: {e}")
            raise HTTPException(400, f"头像保存失败: {str(e)}")
    
    conn.commit()
    
    # 返回更新后的用户信息
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    avatar = row["avatar"] if row["avatar"] else ""
    return {
        "success": True,
        "user": {
            "id": row["id"],
            "nickname": row["nickname"],
            "avatar": ("/api/avatar/" + str(row["id"])) if avatar else "",
            "total_used": row["total_used"]
        }
    }


@app.get("/api/avatar/{user_id}")
async def get_avatar(user_id: int):
    """获取用户头像图片"""
    avatar_dir = os.path.join(os.path.dirname(__file__), "avatars")
    avatar_path = os.path.join(avatar_dir, f"{user_id}.jpg")
    if not os.path.exists(avatar_path):
        # 返回默认头像占位
        raise HTTPException(404, "头像不存在")
    return FileResponse(avatar_path, media_type="image/jpeg")


@app.get("/api/user/usage")
async def get_usage(user: Optional[dict] = Depends(get_current_user)):
    """获取用户每日配额使用情况（未登录返回全零）"""
    if not user:
        return {"success": True, "quota": {
            "evaluate": {"used": 0, "remaining": 10, "limit": 10},
            "process": {"used": 0, "remaining": 5, "limit": 5}
        }}
    quota = get_user_quota(user["id"])
    return {"success": True, "quota": quota}


@app.post("/api/process")
async def process_photo(
    data: FileInput,
    user: Optional[dict] = Depends(get_current_user)
):
    """统一处理端点"""
    
    # 配额检查
    if user:
        quota = check_and_use_quota(user["id"], "process")
        if not quota["allowed"]:
            raise HTTPException(429, f"今日处理次数已用完（{quota['limit']}次/天），明天再来吧～")
    
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
async def suggest_edit_photo(data: FileInput, user: Optional[dict] = Depends(get_current_user)):
    """AI 图片编辑（seededit）"""
    # 配额检查（与 /api/process 共享配额）
    if user:
        quota = check_and_use_quota(user["id"], "process")
        if not quota["allowed"]:
            raise HTTPException(429, f"今日处理次数已用完（{quota['limit']}次/天），明天再来吧～")
    
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
    """返回隐私保护政策"""
    paths = [
        BASE_DIR / "legal" / "privacy.md",
        BASE_DIR.parent / "WeChatProjects" / "colorize-miniapp" / "pkg-legal" / "pages" / "privacy" / "privacy.md",
    ]
    content = ""
    for p in paths:
        try:
            content = p.read_text(encoding="utf-8")
            break
        except Exception:
            continue
    if not content:
        content = "# 隐私保护政策\n\n加载失败，请稍后重试。"
    return {"success": True, "content": content}


@app.get("/api/agreement")
async def get_user_agreement():
    """返回用户服务协议"""
    paths = [
        BASE_DIR / "legal" / "agreement.md",
        BASE_DIR.parent / "WeChatProjects" / "colorize-miniapp" / "pkg-legal" / "pages" / "agreement" / "agreement.md",
    ]
    content = ""
    for p in paths:
        try:
            content = p.read_text(encoding="utf-8")
            break
        except Exception:
            continue
    if not content:
        content = "# 用户服务协议\n\n加载失败，请稍后重试。"
    return {"success": True, "content": content}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8888)
