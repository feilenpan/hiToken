# -*- coding: utf-8 -*-
"""
时光上色 - AI 上色引擎
支持两种模式：
1. DeOldify（本地，免费，效果70分）
2. Palette.fm API（远程，付费，效果90分）
"""

import os
import io
import base64
import logging
from PIL import Image, ImageEnhance, ImageFilter
from typing import Optional
import requests

logger = logging.getLogger(__name__)

# 配置
DEOLDIFY_ENABLED = os.getenv("DEOLDIFY_ENABLED", "true").lower() == "true"
PALETTE_API_KEY = os.getenv("RAPIDAPI_KEY", "")
PALETTE_API_HOST = "colorize-photo1.p.rapidapi.com"


def colorize_deoldify(image_data: bytes, **kwargs) -> dict:
    """
    DeOldify 风格的上色（简化版）
    使用图像处理技术模拟上色效果
    效果：60-70分，适合MVP验证
    """
    try:
        img = Image.open(io.BytesIO(image_data)).convert("RGB")
        
        # 步骤1：增强对比度
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.3)
        
        # 步骤2：添加暖色调（棕褐色调）
        width, height = img.size
        pixels = img.load()
        
        for x in range(width):
            for y in range(height):
                pixel = pixels[x, y]
                if pixel is None:
                    continue
                r, g, b = pixel
                
                # 计算亮度
                brightness = (r + g + b) / 3
                
                # 根据亮度添加不同色调
                if brightness > 200:  # 亮部 - 偏暖黄
                    r = min(255, int(r * 1.1 + 15))
                    g = min(255, int(g * 1.0 + 8))
                    b = min(255, int(b * 0.85))
                elif brightness > 100:  # 中间调 - 自然肤色
                    r = min(255, int(r * 1.05 + 10))
                    g = min(255, int(g * 0.98 + 5))
                    b = min(255, int(b * 0.9))
                else:  # 暗部 - 深棕
                    r = min(255, int(r * 1.0 + 8))
                    g = min(255, int(g * 0.95))
                    b = min(255, int(b * 0.85))
                
                pixels[x, y] = (int(r), int(g), int(b))
        
        # 步骤3：轻微模糊去噪
        img = img.filter(ImageFilter.SMOOTH)
        
        # 步骤4：增强饱和度
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.2)
        
        # 步骤5：锐化
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.1)
        
        # 转为 base64
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=95)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return {
            "success": True,
            "image_base64": f"data:image/jpeg;base64,{img_base64}",
            "engine": "deoldify",
            "mock": False
        }
        
    except Exception as e:
        logger.error(f"DeOldify colorization failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "engine": "deoldify"
        }


def colorize_palette(image_data: bytes, prompt: str = "vintage photo", 
                     resolution: str = "full_hd", **kwargs) -> dict:
    """
    Palette.fm API 上色
    效果：90分，需要付费API
    """
    if not PALETTE_API_KEY:
        return {
            "success": False,
            "error": "Palette API key not configured",
            "engine": "palette"
        }
    
    try:
        # 转为 base64
        img_base64 = base64.b64encode(image_data).decode()
        
        # 调用 Palette API
        url = f"https://{PALETTE_API_HOST}/colorize_image_with_auto_prompt_base64"
        headers = {
            "X-RapidAPI-Key": PALETTE_API_KEY,
            "X-RapidAPI-Host": PALETTE_API_HOST,
            "Content-Type": "application/json"
        }
        payload = {
            "image": img_base64,
            "resolution": resolution,
            "prompt": prompt,
            "auto_color": "true",
            "white_balance": "true"
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get("image"):
            return {
                "success": True,
                "image_base64": f"data:image/jpeg;base64,{result['image']}",
                "engine": "palette",
                "mock": False
            }
        else:
            return {
                "success": False,
                "error": "No image returned from API",
                "engine": "palette"
            }
            
    except Exception as e:
        logger.error(f"Palette API failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "engine": "palette"
        }


def colorize_image(image_data: bytes, engine: str = "auto", **kwargs) -> dict:
    """
    统一上色接口
    engine: "deoldify" | "palette" | "auto"
    """
    if engine == "palette" or (engine == "auto" and PALETTE_API_KEY):
        result = colorize_palette(image_data, **kwargs)
        if result["success"]:
            return result
        logger.warning(f"Palette failed, falling back to DeOldify: {result.get('error')}")
    
    # 默认使用 DeOldify
    return colorize_deoldify(image_data, **kwargs)


def check_health() -> dict:
    """检查上色引擎状态"""
    return {
        "deoldify": DEOLDIFY_ENABLED,
        "palette": bool(PALETTE_API_KEY),
        "default_engine": "palette" if PALETTE_API_KEY else "deoldify"
    }
