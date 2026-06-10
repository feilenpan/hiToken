# -*- coding: utf-8 -*-
"""
时光修复 - AI 照片处理引擎

功能分工：
- 上色（colorize）：Palette API（真实AI）
- 照片修复（enhance）：本地 PIL 增强

Palette API 集成要求：
必须在 UI 中显示 "Powered with the Palette API" 署名
"""

import os
import io
import base64
import logging
import requests
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from typing import Optional

logger = logging.getLogger(__name__)

# 加载 .env 文件
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# ===== 配置 =====
PALETTE_API_KEY = os.getenv("RAPIDAPI_KEY", "")
PALETTE_API_HOST = "colorize-photo1.p.rapidapi.com"


# ===== 工具函数 =====

def image_to_base64(img: Image.Image, quality: int = 95) -> str:
    """PIL Image → data:image/jpeg;base64,..."""
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"


# ================================================================
#  1. AI 上色（Colorize）— Palette API
# ================================================================

def colorize_palette(image_data: bytes) -> dict:
    """Palette API 上色（multipart/form-data 格式）"""
    if not PALETTE_API_KEY:
        return {"success": False, "error": "API key not configured"}
    try:
        resp = requests.post(
            f"https://{PALETTE_API_HOST}/colorize_image_with_auto_prompt",
            files={"image": ("photo.jpg", image_data, "image/jpeg")},
            data={
                "resolution": "sd",
                "prompt": "",
                "auto_color": "true",
                "white_balance": "true",
                "temperature": "-0.1",
                "saturation": "1.1",
            },
            headers={
                "X-RapidAPI-Key": PALETTE_API_KEY,
                "X-RapidAPI-Host": PALETTE_API_HOST,
            },
            timeout=120
        )
        resp.raise_for_status()
        
        # Palette 返回的是二进制图片数据
        content_type = resp.headers.get("content-type", "")
        if "image" in content_type or len(resp.content) > 1000:
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            return {"success": True, "image_base64": image_to_base64(img)}
        
        # 如果返回 JSON
        result = resp.json()
        if result.get("content"):
            img_data = base64.b64decode(result["content"])
            img = Image.open(io.BytesIO(img_data)).convert("RGB")
            return {"success": True, "image_base64": image_to_base64(img)}
        
        return {"success": False, "error": "No image returned"}
    except Exception as e:
        logger.error(f"Palette colorize failed: {e}")
        return {"success": False, "error": str(e)}

def colorize_local(image_data: bytes) -> dict:
    """本地模拟上色（棕褐色调，兜底方案）"""
    try:
        img = Image.open(io.BytesIO(image_data)).convert("RGB")
        img = ImageEnhance.Contrast(img).enhance(1.3)
        w, h = img.size
        pixels = img.load()
        for x in range(w):
            for y in range(h):
                r, g, b = pixels[x, y]
                brightness = (r + g + b) / 3
                if brightness > 200:
                    r, g, b = min(255, int(r*1.1+15)), min(255, int(g*1.0+8)), int(b*0.85)
                elif brightness > 100:
                    r, g, b = min(255, int(r*1.05+10)), min(255, int(g*0.98+5)), int(b*0.9)
                else:
                    r, g, b = min(255, int(r+8)), int(g*0.95), int(b*0.85)
                pixels[x, y] = (int(r), int(g), int(b))
        img = img.filter(ImageFilter.SMOOTH)
        img = ImageEnhance.Color(img).enhance(1.2)
        img = ImageEnhance.Sharpness(img).enhance(1.1)
        return {"success": True, "image_base64": image_to_base64(img)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def colorize(image_data: bytes) -> dict:
    """上色：优先 Palette API → 兜底本地处理"""
    if PALETTE_API_KEY:
        result = colorize_palette(image_data)
        if result["success"]:
            result["engine"] = "palette"
            return result
        logger.warning(f"Palette failed, fallback to local: {result.get('error')}")
    result = colorize_local(image_data)
    result["engine"] = "local"
    return result


# ================================================================
#  2. 照片修复（Enhance）— 本地 PIL
# ================================================================

def enhance(image_data: bytes) -> dict:
    """照片修复：去噪 + 自动对比度 + 锐化 + 色彩均衡"""
    try:
        img = Image.open(io.BytesIO(image_data)).convert("RGB")
        
        # 去噪（中值滤波）
        img = img.filter(ImageFilter.MedianFilter(size=3))
        # 自动对比度
        img = ImageOps.autocontrast(img, cutoff=2)
        # 锐化
        img = ImageEnhance.Sharpness(img).enhance(1.5)
        # 对比度
        img = ImageEnhance.Contrast(img).enhance(1.2)
        # 亮度
        img = ImageEnhance.Brightness(img).enhance(1.05)
        # 色彩
        img = ImageEnhance.Color(img).enhance(1.1)
        
        return {"success": True, "image_base64": image_to_base64(img), "engine": "local"}
    except Exception as e:
        return {"success": False, "error": str(e), "engine": "local"}


# ================================================================
#  统一接口
# ================================================================

PROCESS_TYPES = {
    "colorize":     {"name": "AI上色",     "icon": "🎨", "desc": "黑白照片智能上色",      "engine": "palette"},
    "enhance":      {"name": "照片修复",   "icon": "🔧", "desc": "修复折痕、去噪增强",  "engine": "local"},
}

def get_available_features() -> dict:
    features = {}
    for key, info in PROCESS_TYPES.items():
        features[key] = {
            "name": info["name"],
            "icon": info["icon"],
            "desc": info["desc"],
            "engine": "palette" if (key == "colorize" and PALETTE_API_KEY) else "local",
        }
    return features

def process_image(image_data: bytes, process_type: str) -> dict:
    """统一处理入口"""
    processors = {
        "colorize": colorize,
        "enhance": enhance,
    }
    processor = processors.get(process_type)
    if not processor:
        return {"success": False, "error": f"不支持的处理类型: {process_type}"}
    
    logger.info(f"处理: {process_type}, 大小: {len(image_data)} bytes")
    result = processor(image_data)
    result["process_type"] = process_type
    result["process_name"] = PROCESS_TYPES.get(process_type, {}).get("name", process_type)
    return result

def check_health() -> dict:
    return {
        "palette_api": bool(PALETTE_API_KEY),
        "default_engine": "palette" if PALETTE_API_KEY else "local",
        "features": ["colorize", "enhance"],
    }
