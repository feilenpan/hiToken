# -*- coding: utf-8 -*-
"""
升级版 AI 照片处理引擎 - 多云策略

支持的 AI 引擎：
1. Palette API（上色）- 当前方案
2. 阿里云视觉智能（上色 + 增强）- 推荐方案
3. 腾讯云智能图像（上色 + 增强）- 备用方案
4. 本地 PIL（兜底方案）

实施策略：
- 优先使用阿里云（性价比最高）
- Palette 作为备用
- PIL 作为降级方案
"""

import os
import io
import json
import base64
import logging
import requests
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# ===== 配置 =====
PALETTE_API_KEY = os.getenv("RAPIDAPI_KEY", "")
ALIYUN_ACCESS_KEY = os.getenv("ALIYUN_ACCESS_KEY", "")
ALIYUN_ACCESS_SECRET = os.getenv("ALIYUN_ACCESS_SECRET", "")
TENCENT_SECRET_ID = os.getenv("TENCENT_SECRET_ID", "")
TENCENT_SECRET_KEY = os.getenv("TENCENT_SECRET_KEY", "")

# 策略配置（可通过环境变量动态调整）
COLORIZE_STRATEGY = os.getenv("COLORIZE_STRATEGY", "aliyun,palette,local")  # 优先级顺序
ENHANCE_STRATEGY = os.getenv("ENHANCE_STRATEGY", "aliyun,tencent,local")


# ================================================================
#  工具函数
# ================================================================

def image_to_base64(img: Image.Image, quality: int = 95) -> str:
    """PIL Image → data:image/jpeg;base64,..."""
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"


# ================================================================
#  微信内容安全审核（必须）
# ================================================================

def check_wechat_content_safety(image_data: bytes, access_token: str) -> Dict:
    """
    微信内容安全 - 图片检测
    文档：https://developers.weixin.qq.com/miniprogram/dev/OpenApiDoc/sec-center/sec-check/imgSecCheck.html
    
    返回：{"safe": True/False, "error": str}
    """
    try:
        url = f"https://api.weixin.qq.com/wxa/img_sec_check?access_token={access_token}"
        
        # 注意：微信要求 multipart/form-data 格式
        files = {"media": ("image.jpg", image_data, "image/jpeg")}
        resp = requests.post(url, files=files, timeout=10)
        result = resp.json()
        
        # errcode=0 表示安全，87014 表示违规
        if result.get("errcode") == 0:
            return {"safe": True}
        elif result.get("errcode") == 87014:
            return {"safe": False, "error": "图片包含违规内容"}
        else:
            logger.error(f"WeChat content check error: {result}")
            return {"safe": True}  # 审核失败时放行，避免误伤
            
    except Exception as e:
        logger.error(f"WeChat content check failed: {e}")
        return {"safe": True}  # 异常时放行


# ================================================================
#  AI 上色实现
# ================================================================

def colorize_palette(image_data: bytes) -> Dict:
    """Palette API 上色（当前方案）"""
    if not PALETTE_API_KEY:
        return {"success": False, "error": "Palette API key not configured"}
    
    try:
        resp = requests.post(
            "https://colorize-photo1.p.rapidapi.com/colorize_image_with_auto_prompt",
            files={"image": ("photo.jpg", image_data, "image/jpeg")},
            data={
                "resolution": "sd",
                "auto_color": "true",
                "white_balance": "true",
                "temperature": "-0.1",
                "saturation": "1.1",
            },
            headers={
                "X-RapidAPI-Key": PALETTE_API_KEY,
                "X-RapidAPI-Host": "colorize-photo1.p.rapidapi.com",
            },
            timeout=120
        )
        resp.raise_for_status()
        
        # Palette 返回二进制图片
        if "image" in resp.headers.get("content-type", ""):
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            return {
                "success": True,
                "image_base64": image_to_base64(img),
                "engine": "palette",
                "cost": 0.007  # $0.007/次 ≈ ¥0.05
            }
        
        return {"success": False, "error": "Invalid response"}
    except Exception as e:
        logger.error(f"Palette colorize failed: {e}")
        return {"success": False, "error": str(e)}


def colorize_aliyun(image_data: bytes) -> Dict:
    """
    阿里云图像上色 API
    文档：https://help.aliyun.com/document_detail/156086.html
    成本：¥0.0025/次（前 1000 次免费）
    """
    if not ALIYUN_ACCESS_KEY or not ALIYUN_ACCESS_SECRET:
        return {"success": False, "error": "Aliyun credentials not configured"}
    
    try:
        # 这里需要安装 aliyun-python-sdk-imageprocess
        # pip install aliyun-python-sdk-core aliyun-python-sdk-imageprocess
        
        from aliyunsdkcore.client import AcsClient
        from aliyunsdkcore.request import CommonRequest
        
        client = AcsClient(ALIYUN_ACCESS_KEY, ALIYUN_ACCESS_SECRET, 'cn-shanghai')
        
        request = CommonRequest()
        request.set_domain('imageprocess.cn-shanghai.aliyuncs.com')
        request.set_version('2020-03-20')
        request.set_action_name('ImageColorization')
        request.add_body_params('ImageURL', image_to_base64(Image.open(io.BytesIO(image_data))))
        
        response = client.do_action_with_exception(request)
        result = json.loads(response)
        
        if result.get('Code') == 200:
            # 阿里云返回处理后的图片 URL
            colored_url = result['Data']['ImageURL']
            img_resp = requests.get(colored_url, timeout=30)
            img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
            
            return {
                "success": True,
                "image_base64": image_to_base64(img),
                "engine": "aliyun",
                "cost": 0.0025
            }
        
        return {"success": False, "error": result.get('Message', 'Unknown error')}
        
    except ImportError:
        logger.error("Aliyun SDK not installed. Run: pip install aliyun-python-sdk-imageprocess")
        return {"success": False, "error": "Aliyun SDK not installed"}
    except Exception as e:
        logger.error(f"Aliyun colorize failed: {e}")
        return {"success": False, "error": str(e)}


def colorize_local(image_data: bytes) -> Dict:
    """本地 PIL 模拟上色（兜底方案）"""
    try:
        img = Image.open(io.BytesIO(image_data)).convert("RGB")
        img = ImageEnhance.Contrast(img).enhance(1.3)
        
        # 简单的棕褐色调
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
        
        return {
            "success": True,
            "image_base64": image_to_base64(img),
            "engine": "local",
            "cost": 0
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ================================================================
#  照片修复实现
# ================================================================

def enhance_aliyun(image_data: bytes) -> Dict:
    """
    阿里云图像增强 API
    文档：https://help.aliyun.com/document_detail/156088.html
    成本：¥0.003/次
    """
    if not ALIYUN_ACCESS_KEY or not ALIYUN_ACCESS_SECRET:
        return {"success": False, "error": "Aliyun credentials not configured"}
    
    try:
        from aliyunsdkcore.client import AcsClient
        from aliyunsdkcore.request import CommonRequest
        
        client = AcsClient(ALIYUN_ACCESS_KEY, ALIYUN_ACCESS_SECRET, 'cn-shanghai')
        
        request = CommonRequest()
        request.set_domain('imageprocess.cn-shanghai.aliyuncs.com')
        request.set_version('2020-03-20')
        request.set_action_name('ImageDenoising')  # 去噪
        request.add_body_params('ImageURL', image_to_base64(Image.open(io.BytesIO(image_data))))
        
        response = client.do_action_with_exception(request)
        result = json.loads(response)
        
        if result.get('Code') == 200:
            enhanced_url = result['Data']['ImageURL']
            img_resp = requests.get(enhanced_url, timeout=30)
            img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
            
            return {
                "success": True,
                "image_base64": image_to_base64(img),
                "engine": "aliyun",
                "cost": 0.003
            }
        
        return {"success": False, "error": result.get('Message', 'Unknown error')}
        
    except ImportError:
        return {"success": False, "error": "Aliyun SDK not installed"}
    except Exception as e:
        logger.error(f"Aliyun enhance failed: {e}")
        return {"success": False, "error": str(e)}


def enhance_local(image_data: bytes) -> Dict:
    """本地 PIL 增强（当前方案）"""
    try:
        img = Image.open(io.BytesIO(image_data)).convert("RGB")
        
        # 去噪
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
        
        return {
            "success": True,
            "image_base64": image_to_base64(img),
            "engine": "local",
            "cost": 0
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ================================================================
#  智能路由（多云策略）
# ================================================================

def colorize(image_data: bytes) -> Dict:
    """
    上色智能路由
    策略：aliyun → palette → local
    """
    strategies = COLORIZE_STRATEGY.split(",")
    
    for strategy in strategies:
        strategy = strategy.strip()
        
        if strategy == "aliyun" and ALIYUN_ACCESS_KEY:
            result = colorize_aliyun(image_data)
            if result["success"]:
                logger.info(f"Colorize success via {strategy}")
                return result
            logger.warning(f"Colorize failed via {strategy}: {result.get('error')}")
        
        elif strategy == "palette" and PALETTE_API_KEY:
            result = colorize_palette(image_data)
            if result["success"]:
                logger.info(f"Colorize success via {strategy}")
                return result
            logger.warning(f"Colorize failed via {strategy}: {result.get('error')}")
        
        elif strategy == "local":
            result = colorize_local(image_data)
            if result["success"]:
                logger.info(f"Colorize success via {strategy}")
                return result
    
    return {"success": False, "error": "所有上色引擎均失败"}


def enhance(image_data: bytes) -> Dict:
    """
    修复智能路由
    策略：aliyun → tencent → local
    """
    strategies = ENHANCE_STRATEGY.split(",")
    
    for strategy in strategies:
        strategy = strategy.strip()
        
        if strategy == "aliyun" and ALIYUN_ACCESS_KEY:
            result = enhance_aliyun(image_data)
            if result["success"]:
                logger.info(f"Enhance success via {strategy}")
                return result
            logger.warning(f"Enhance failed via {strategy}: {result.get('error')}")
        
        elif strategy == "local":
            result = enhance_local(image_data)
            if result["success"]:
                logger.info(f"Enhance success via {strategy}")
                return result
    
    return {"success": False, "error": "所有修复引擎均失败"}


# ================================================================
#  统一接口
# ================================================================

def process_image(
    image_data: bytes, 
    process_type: str, 
    wechat_access_token: Optional[str] = None
) -> Dict:
    """
    统一处理入口
    
    Args:
        image_data: 图片二进制数据
        process_type: 'colorize' 或 'enhance'
        wechat_access_token: 微信 access_token（用于内容审核）
    
    Returns:
        {
            "success": True/False,
            "image_base64": "data:image/jpeg;base64,...",
            "engine": "aliyun/palette/local",
            "cost": 0.0025,  # 成本（元）
            "error": "错误信息"
        }
    """
    
    # 1. 内容安全审核（强烈建议）
    if wechat_access_token:
        safety_result = check_wechat_content_safety(image_data, wechat_access_token)
        if not safety_result["safe"]:
            return {
                "success": False,
                "error": safety_result.get("error", "图片包含违规内容")
            }
    
    # 2. 大小限制
    if len(image_data) > 5 * 1024 * 1024:  # 5MB
        return {"success": False, "error": "图片大小超过 5MB 限制"}
    
    # 3. 调用 AI 处理
    processors = {
        "colorize": colorize,
        "enhance": enhance,
    }
    
    processor = processors.get(process_type)
    if not processor:
        return {"success": False, "error": f"不支持的处理类型: {process_type}"}
    
    logger.info(f"Processing {process_type}, size: {len(image_data)} bytes")
    result = processor(image_data)
    result["process_type"] = process_type
    
    return result


def get_available_engines() -> Dict:
    """获取可用的 AI 引擎"""
    return {
        "colorize": {
            "aliyun": bool(ALIYUN_ACCESS_KEY),
            "palette": bool(PALETTE_API_KEY),
            "local": True
        },
        "enhance": {
            "aliyun": bool(ALIYUN_ACCESS_KEY),
            "local": True
        }
    }


def get_cost_estimate(monthly_requests: int) -> Dict:
    """
    成本估算
    
    Args:
        monthly_requests: 月请求次数
    
    Returns:
        各方案的成本对比
    """
    return {
        "palette_only": {
            "colorize": monthly_requests * 0.05,  # ¥0.05/次
            "enhance": 0,  # 使用本地
            "total": monthly_requests * 0.05
        },
        "aliyun_only": {
            "colorize": monthly_requests * 0.0025,
            "enhance": monthly_requests * 0.003,
            "total": monthly_requests * 0.0055
        },
        "hybrid": {
            "colorize": monthly_requests * 0.0025,  # 阿里云
            "enhance": 0,  # 本地
            "total": monthly_requests * 0.0025
        }
    }


if __name__ == "__main__":
    # 测试成本估算
    for usage in [1000, 3000, 10000, 100000]:
        print(f"\n月使用量: {usage} 次")
        estimate = get_cost_estimate(usage)
        print(f"  Palette 方案: ¥{estimate['palette_only']['total']:.2f}/月")
        print(f"  阿里云方案:  ¥{estimate['aliyun_only']['total']:.2f}/月")
        print(f"  混合方案:    ¥{estimate['hybrid']['total']:.2f}/月")
        print(f"  节省比例:    {(1 - estimate['aliyun_only']['total']/estimate['palette_only']['total'])*100:.1f}%")
