# -*- coding: utf-8 -*-
"""
Palette.fm API 集成模块
通过 RapidAPI 调用 Palette.fm 的上色服务
"""

import os
import requests
import base64
import uuid
from typing import Optional, Dict, Any

# RapidAPI 配置
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "colorize-photo1.p.rapidapi.com")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")


def colorize_image(
    image_data: bytes,
    prompt: str = "vintage photo, natural colors",
    resolution: str = "full_hd",
    auto_color: bool = True,
    white_balance: bool = True,
    temperature: int = 0,
    saturation: int = 0
) -> Dict[str, Any]:
    """
    使用 Palette.fm API 为黑白图片上色
    
    Args:
        image_data: 图片二进制数据
        prompt: 上色提示词
        resolution: 输出分辨率 (hd, full_hd, 4k)
        auto_color: 是否自动调色
        white_balance: 是否白平衡
        temperature: 色温调整 (-100 到 100)
        saturation: 饱和度调整 (-100 到 100)
    
    Returns:
        Dict with 'success', 'image_base64', 'error' keys
    """
    if not RAPIDAPI_KEY:
        # 开发模式：返回模拟结果
        return _mock_colorize(image_data)
    
    url = f"https://{RAPIDAPI_HOST}/colorize_image_with_auto_prompt_base64"
    
    # 转换为 base64
    image_b64 = base64.b64encode(image_data).decode("utf-8")
    
    payload = {
        "image": image_b64,
        "prompt": prompt,
        "resolution": resolution,
        "auto_color": str(auto_color).lower(),
        "white_balance": str(white_balance).lower(),
        "temperature": str(temperature),
        "saturation": str(saturation)
    }
    
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST,
        "Content-Type": "application/json"
    }
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("content"):
            return {
                "success": True,
                "image_base64": f"data:image/png;base64,{data['content']}",
                "task_id": str(uuid.uuid4())
            }
        else:
            return {
                "success": False,
                "error": data.get("message", "Unknown error")
            }
            
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timeout"}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}


def colorize_with_reference(
    image_data: bytes,
    reference_data: bytes,
    resolution: str = "full_hd",
    auto_color: bool = True
) -> Dict[str, Any]:
    """
    使用参考图上色（用彩色照片的颜色参考）
    """
    if not RAPIDAPI_KEY:
        return _mock_colorize(image_data)
    
    url = f"https://{RAPIDAPI_HOST}/colorize_image_with_reference_image"
    
    files = {
        "image": ("photo.jpg", image_data, "image/jpeg"),
        "image_ref": ("reference.jpg", reference_data, "image/jpeg")
    }
    
    data = {
        "resolution": resolution,
        "auto_color": str(auto_color).lower()
    }
    
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY}
    
    try:
        resp = requests.post(url, files=files, data=data, headers=headers, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        
        if result.get("content"):
            return {
                "success": True,
                "image_base64": f"data:image/png;base64,{result['content']}"
            }
        return {"success": False, "error": "No result"}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_health() -> bool:
    """检查 API 健康状态"""
    if not RAPIDAPI_KEY:
        return True  # 开发模式
    
    try:
        url = f"https://{RAPIDAPI_HOST}/health"
        resp = requests.get(url, headers={"X-RapidAPI-Key": RAPIDAPI_KEY}, timeout=10)
        return resp.status_code == 200
    except:
        return False


def _mock_colorize(image_data: bytes) -> Dict[str, Any]:
    """
    开发模式：模拟上色效果
    使用 PIL 给图片添加暖色调
    """
    try:
        from PIL import Image, ImageEnhance, ImageFilter
        import io
        
        # 打开图片
        img = Image.open(io.BytesIO(image_data)).convert("RGB")
        
        # 模拟上色效果：添加暖色调
        enhancer = ImageEnhance.Color(img)
        img_colorized = enhancer.enhance(1.3)
        
        # 增加亮度
        enhancer = ImageEnhance.Brightness(img_colorized)
        img_colorized = enhancer.enhance(1.1)
        
        # 轻微锐化
        img_colorized = img_colorized.filter(ImageFilter.SHARPEN)
        
        # 保存到 bytes
        output = io.BytesIO()
        img_colorized.save(output, format="PNG")
        output.seek(0)
        
        img_base64 = base64.b64encode(output.read()).decode("utf-8")
        
        return {
            "success": True,
            "image_base64": f"data:image/png;base64,{img_base64}",
            "task_id": str(uuid.uuid4()),
            "mock": True  # 标记为模拟结果
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


# 测试函数
if __name__ == "__main__":
    # 创建测试图片
    from PIL import Image
    import io
    
    img = Image.new("RGB", (200, 150), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    
    result = colorize_image(buf.read())
    print(f"Result: {result['success']}")
    if result['success']:
        print(f"Image size: {len(result['image_base64'])} chars")
    else:
        print(f"Error: {result.get('error')}")
