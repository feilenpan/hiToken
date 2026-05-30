"""
火山引擎視覺大模型 - 老照片修復引擎
使用 seededit_v3.0 異步接口
"""
import os
import json
import base64
import datetime
import hashlib
import hmac
import time
import logging
from io import BytesIO
from typing import Optional
from PIL import Image

logger = logging.getLogger(__name__)

# === 配置 ===
AK = os.environ.get("VOLC_ACCESS_KEY", "")
SK = "WVRVNU9HTmhPRE0zWlRZM05EQTFPV0ZsTUdOak5tSTVOak14WkRSa05tRQ=="
HOST = "visual.volcengineapi.com"
ENDPOINT = f"https://{HOST}"
REGION = "cn-north-1"
SERVICE = "cv"

# 修復參數
RESTORE_PROMPT = "修復老照片，去除噪點和劃痕，增強人臉清晰度，還原膚色"
RESTORE_SCALE = 0.5
MAX_IMAGE_SIZE = 1024  # 最大邊長
MAX_FILE_BYTES = 800 * 1024  # 800KB (留餘量)
POLL_INTERVAL = 5  # 秒
MAX_POLLS = 24  # 最多等 120 秒


def _sign(key, msg):
    """HMAC-SHA256 簽名"""
    k = key.encode("utf-8") if isinstance(key, str) else key
    return hmac.new(k, msg.encode("utf-8"), hashlib.sha256).digest()


def _get_signing_key(secret_key, datestamp):
    """生成 V4 簽名密鑰"""
    k_date = _sign(secret_key, datestamp)
    k_region = _sign(k_date, REGION)
    k_service = _sign(k_region, SERVICE)
    return _sign(k_service, "request")


def _build_headers(query: str, body: str) -> dict:
    """構建 V4 簽名 headers"""
    t = datetime.datetime.utcnow()
    current_date = t.strftime("%Y%m%dT%H%M%SZ")
    datestamp = t.strftime("%Y%m%d")

    payload_hash = hashlib.sha256(body.encode()).hexdigest()
    canonical_headers = (
        f"content-type:application/json\n"
        f"host:{HOST}\n"
        f"x-content-sha256:{payload_hash}\n"
        f"x-date:{current_date}\n"
    )
    signed_headers = "content-type;host;x-content-sha256;x-date"
    canonical_request = (
        f"POST\n/\n{query}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
    )
    credential_scope = f"{datestamp}/{REGION}/{SERVICE}/request"
    string_to_sign = (
        f"HMAC-SHA256\n{current_date}\n{credential_scope}\n"
        + hashlib.sha256(canonical_request.encode()).hexdigest()
    )
    signing_key = _get_signing_key(SK, datestamp)
    signature = hmac.new(
        signing_key, string_to_sign.encode(), hashlib.sha256
    ).hexdigest()

    return {
        "X-Date": current_date,
        "Authorization": (
            f"HMAC-SHA256 Credential={AK}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
        "X-Content-Sha256": payload_hash,
        "Content-Type": "application/json",
    }


def _api_call(action: str, body_dict: dict, timeout: int = 120) -> Optional[dict]:
    """調用火山視覺 API（帶重試）"""
    import requests as req

    query = f"Action={action}&Version=2022-08-31"
    body = json.dumps(body_dict)
    headers = _build_headers(query, body)
    url = f"{ENDPOINT}?{query}"

    for attempt in range(3):
        try:
            r = req.post(url, headers=headers, data=body, timeout=timeout)
            if r.status_code == 200 and r.text:
                return r.json()
            logger.warning(f"API 請求異常: status={r.status_code}, attempt={attempt + 1}")
        except Exception as e:
            logger.warning(f"API 請求失敗: {e}, attempt={attempt + 1}")
        time.sleep(2)

    return None


def _compress_image(image_bytes: bytes) -> bytes:
    """壓縮圖片到 API 限制以內"""
    img = Image.open(BytesIO(image_bytes))

    # 轉 RGB（PNG 可能是 RGBA）
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # 縮放到最大邊長
    if max(img.size) > MAX_IMAGE_SIZE:
        img.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE), Image.LANCZOS)
        logger.info(f"圖片已縮放到 {img.size}")

    # 壓縮到目標大小
    for quality in [85, 75, 65, 55]:
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        size = buf.tell()
        if size <= MAX_FILE_BYTES:
            logger.info(f"圖片已壓縮: {size} bytes, quality={quality}")
            return buf.getvalue()

    # 最低質量兜底
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=50)
    logger.warning(f"圖片壓縮到最低質量: {buf.tell()} bytes")
    return buf.getvalue()


def restore_photo(image_bytes: bytes) -> Optional[bytes]:
    """
    修復老照片

    Args:
        image_bytes: 原始圖片 bytes

    Returns:
        修復後的圖片 bytes，失敗返回 None
    """
    import requests as req

    # 1. 壓縮圖片
    compressed = _compress_image(image_bytes)
    img_b64 = base64.b64encode(compressed).decode()
    logger.info(f"圖片準備完成: {len(compressed)} bytes, base64 {len(img_b64)} chars")

    # 2. 提交異步任務
    submit_body = {
        "req_key": "seededit_v3.0",
        "binary_data_base64": [img_b64],
        "prompt": RESTORE_PROMPT,
        "seed": -1,
        "scale": RESTORE_SCALE,
    }
    resp = _api_call("CVSync2AsyncSubmitTask", submit_body)

    if not resp or resp.get("code") != 10000:
        error_msg = resp.get("message", "提交失敗") if resp else "API 無響應"
        logger.error(f"修復任務提交失敗: {error_msg}")
        return None

    task_id = resp["data"]["task_id"]
    logger.info(f"修復任務已提交: task_id={task_id}")

    # 3. 輪詢結果
    for i in range(MAX_POLLS):
        time.sleep(POLL_INTERVAL)

        query_body = {"req_key": "seededit_v3.0", "task_id": task_id}
        result = _api_call("CVSync2AsyncGetResult", query_body)

        if not result:
            logger.warning(f"查詢結果失敗，重試...")
            continue

        data = result.get("data", {})
        status = data.get("status", "")

        if status == "done":
            b64_list = data.get("binary_data_base64", [])
            if b64_list and len(b64_list) > 0:
                output_bytes = base64.b64decode(b64_list[0])
                logger.info(f"修復完成: {len(output_bytes)} bytes")
                return output_bytes
            else:
                logger.error("修復完成但無返回數據")
                return None

        logger.info(f"等待修復結果... ({i + 1}/{MAX_POLLS}) status={status}")

    logger.error("修復超時")
    return None


def suggest_edit(image_bytes: bytes, prompt: str, scale: float = 0.7) -> Optional[bytes]:
    """AI 图片编辑，支持自定义 prompt"""
    if not prompt or not prompt.strip():
        prompt = RESTORE_PROMPT
    compressed = _compress_image(image_bytes)
    img_b64 = base64.b64encode(compressed).decode()
    submit_body = {
        "req_key": "seededit_v3.0",
        "binary_data_base64": [img_b64],
        "prompt": prompt[:120],
        "seed": -1,
        "scale": scale,
    }
    resp = _api_call("CVSync2AsyncSubmitTask", submit_body)
    if not resp or resp.get("code") != 10000:
        return None
    task_id = resp["data"]["task_id"]
    for i in range(MAX_POLLS):
        time.sleep(POLL_INTERVAL)
        qr = _api_call("CVSync2AsyncGetResult", {"req_key": "seededit_v3.0", "task_id": task_id})
        if not qr or qr.get("code") != 10000:
            continue
        status = qr.get("data", {}).get("status", "")
        if status == "done":
            b64_list = qr["data"].get("binary_data_base64", [])
            if b64_list and len(b64_list) > 0:
                return base64.b64decode(b64_list[0])
            return None
        elif status == "failed":
            return None
    return None


# === 测试入口 ===
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) < 2:
        print("用法: python volc_visual_engine.py <圖片路徑>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "/tmp/volc_restore_result.png"

    with open(input_path, "rb") as f:
        image_bytes = f.read()

    print(f"原圖: {input_path} ({len(image_bytes)} bytes)")
    result = restore_photo(image_bytes)

    if result:
        with open(output_path, "wb") as f:
            f.write(result)
        print(f"✅ 修復完成: {output_path} ({len(result)} bytes)")
    else:
        print("❌ 修復失敗")
