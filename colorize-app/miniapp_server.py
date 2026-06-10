# -*- coding: utf-8 -*-
"""
时光上色 - 微信小程序后端
Mini Program API Server
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import time
import hashlib
import json
from typing import Optional

# 导入 Palette API
from palette_api import colorize_image as palette_colorize

app = FastAPI(title="时光上色-小程序API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 微信配置
WECHAT_APPID = os.getenv("WECHAT_APPID", "")
WECHAT_SECRET = os.getenv("WECHAT_SECRET", "")

# 内存存储（生产环境用数据库）
users_db = {}
orders_db = {}
tasks_db = {}


# ===== 微信登录 =====

@app.post("/api/wechat/login")
async def wechat_login(code: str):
    """
    微信小程序登录
    前端 wx.login() 获取 code，换取 openid
    """
    # TODO: 调用微信 API 换取 openid
    # url = f"https://api.weixin.qq.com/sns/jscode2session?appid={WECHAT_APPID}&secret={WECHAT_SECRET}&js_code={code}&grant_type=authorization_code"
    
    # 开发模式：返回模拟数据
    openid = f"mock_openid_{code[:8]}"
    
    if openid not in users_db:
        users_db[openid] = {
            "openid": openid,
            "created_at": time.time(),
            "free_credits": 3,  # 新用户送3张
            "paid_credits": 0,
            "total_used": 0
        }
    
    user = users_db[openid]
    
    # 生成 session token
    token = hashlib.md5(f"{openid}_{time.time()}".encode()).hexdigest()
    
    return {
        "success": True,
        "token": token,
        "user": {
            "openid": openid,
            "free_credits": user["free_credits"],
            "paid_credits": user["paid_credits"],
            "total_used": user["total_used"]
        }
    }


# ===== 用户信息 =====

@app.get("/api/wechat/user")
async def get_user_info(x_token: Optional[str] = Header(None)):
    """获取用户信息"""
    # TODO: 根据 token 查询用户
    # 开发模式：返回默认数据
    return {
        "free_credits": 3,
        "paid_credits": 0,
        "total_used": 0,
        "is_vip": False
    }


# ===== 上色接口 =====

@app.post("/api/wechat/colorize")
async def wechat_colorize(
    file: UploadFile = File(...),
    x_token: Optional[str] = Header(None)
):
    """
    小程序上色接口
    检查额度 → 调用API → 扣除额度
    """
    # 验证文件
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "请上传图片文件")
    
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "图片大小不能超过10MB")
    
    # TODO: 验证 token 并获取用户
    # 开发模式：跳过验证
    
    # 检查额度
    # if user["free_credits"] <= 0 and user["paid_credits"] <= 0:
    #     raise HTTPException(402, "额度不足，请购买")
    
    # 调用上色API
    task_id = str(uuid.uuid4())
    
    result = palette_colorize(
        image_data=content,
        prompt="vintage photo, natural colors",
        resolution="full_hd"
    )
    
    if result["success"]:
        # TODO: 扣除额度
        
        return {
            "success": True,
            "task_id": task_id,
            "result": result["image_base64"],
            "mock": result.get("mock", False)
        }
    else:
        raise HTTPException(500, f"上色失败: {result.get('error')}")


# ===== 购买记录 =====

@app.post("/api/wechat/order")
async def create_order(
    package_id: str,
    x_token: Optional[str] = Header(None)
):
    """
    创建订单（小程序支付）
    """
    # 套餐配置
    packages = {
        "single": {"name": "单张上色", "price": 990, "credits": 1},  # ¥9.90
        "pack5": {"name": "体验包", "price": 2900, "credits": 5},    # ¥29.00
        "pack20": {"name": "珍藏包", "price": 9900, "credits": 20},  # ¥99.00
        "monthly": {"name": "月度会员", "price": 1800, "credits": 999},  # ¥18.00
    }
    
    if package_id not in packages:
        raise HTTPException(400, "无效的套餐")
    
    pkg = packages[package_id]
    order_id = f"ORDER_{uuid.uuid4().hex[:16].upper()}"
    
    orders_db[order_id] = {
        "order_id": order_id,
        "package": package_id,
        "name": pkg["name"],
        "price": pkg["price"],
        "credits": pkg["credits"],
        "status": "pending",
        "created_at": time.time()
    }
    
    # TODO: 调用微信支付 API 创建预支付单
    # 返回 prepay_id 等参数给前端调起支付
    
    return {
        "success": True,
        "order_id": order_id,
        "package": pkg,
        # 微信支付参数（需要接入微信支付后生成）
        "pay_params": {
            "timeStamp": str(int(time.time())),
            "nonceStr": uuid.uuid4().hex,
            "package": f"prepay_id=wx_{order_id}",
            "signType": "RSA",
            "paySign": "mock_signature"
        }
    }


@app.get("/api/wechat/order/{order_id}")
async def get_order(order_id: str):
    """查询订单状态"""
    if order_id not in orders_db:
        raise HTTPException(404, "订单不存在")
    
    return orders_db[order_id]


# ===== 健康检查 =====

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "时光上色-小程序API v1.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8889)
