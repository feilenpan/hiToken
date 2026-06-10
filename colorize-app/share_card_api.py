"""
时光修复 - 分享卡片 API
POST /api/share-card → 1080x1500 PNG (base64 data URI)
"""
import io
import os
import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# ── 字体加载 ──
FONT_PATHS = [
    # macOS
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    # Docker (fonts-noto-cjk)
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    # 本地开发
    Path(__file__).parent / "fonts" / "NotoSansSC-Regular.ttf",
]

_FONT_CACHE = {}

def _load_font(size: int) -> ImageFont.FreeTypeFont:
    key = size
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    for p in FONT_PATHS:
        path = Path(p) if isinstance(p, str) else p
        if path.exists():
            font = ImageFont.truetype(str(path), size)
            _FONT_CACHE[key] = font
            return font
    font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


# ── 卡片常量 ──
W, H = 1080, 1500
PAD = 60
PHOTO_MAX_W = 900
PHOTO_MAX_H = 650
PHOTO_RADIUS = 24
ORANGE = (255, 107, 53)
DARK = (51, 51, 51)
GREY = (120, 120, 120)
LIGHT_GREY = (170, 170, 170)
WHITE = (255, 255, 255)
BG_TOP = (255, 248, 240)
BG_BOT = (255, 228, 210)


def _round_corners(im: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", im.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (im.size[0]-1, im.size[1]-1)], radius=radius, fill=255)
    result = im.copy()
    result.putalpha(mask)
    return result


def _draw_gradient_bg(draw: ImageDraw.Draw):
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def _text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_center(draw, y, text, font, color):
    tw, th = _text_size(draw, text, font)
    x = (W - tw) // 2
    draw.text((x, y), text, font=font, fill=color)
    return y + th


class ShareCardRequest(BaseModel):
    file_url: str = ""
    file: str = ""
    poem: str = ""
    reviewer_name: str = "李白"
    reviewer_emoji: str = "🍶"
    reviewer_stamp: str = "太白醉评"


def generate_card(photo_bytes: bytes, poem: str, reviewer_name: str,
                  reviewer_emoji: str, reviewer_stamp: str) -> bytes:
    """生成分享卡片，返回 PNG bytes"""
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)
    _draw_gradient_bg(draw)

    # 字体
    font_title = _load_font(42)
    font_poem = _load_font(34)
    font_sign = _load_font(26)
    font_brand = _load_font(36)
    font_sub = _load_font(24)
    font_guide = _load_font(22)

    current_y = PAD

    # ── 照片区 ──
    try:
        photo = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
    except Exception:
        photo = Image.new("RGB", (600, 400), (220, 220, 220))

    pw, ph = photo.size
    scale = min(PHOTO_MAX_W / pw, PHOTO_MAX_H / ph)
    new_w, new_h = int(pw * scale), int(ph * scale)
    photo = photo.resize((new_w, new_h), Image.LANCZOS)

    card_w = new_w + 40
    card_h = new_h + 40
    card_x = (W - card_w) // 2

    # 阴影
    shadow = Image.new("RGBA", (card_w + 20, card_h + 20), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([(10, 14), (card_w + 9, card_h + 13)], radius=PHOTO_RADIUS+4, fill=(0, 0, 0, 40))
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    img.paste(shadow, (card_x - 10, current_y - 4), shadow)

    # 白色卡片
    card = Image.new("RGBA", (card_w, card_h), (255, 255, 255, 255))
    card = _round_corners(card, PHOTO_RADIUS)
    img.paste(card, (card_x, current_y), card)

    # 照片
    photo = _round_corners(photo, PHOTO_RADIUS - 4)
    img.paste(photo, (card_x + 20, current_y + 20), photo)
    current_y += card_h + 50

    # ── 标题 ──
    title = f"{reviewer_emoji}  {reviewer_name}  品鉴"
    current_y = _draw_center(draw, current_y, title, font_title, DARK) + 12

    # ── 分隔线 ──
    line_w = 200
    lx = (W - line_w) // 2
    draw.line([(lx, current_y), (lx + line_w, current_y)], fill=ORANGE, width=3)
    current_y += 36

    # ── 诗词 ──
    poem_lines = [l.strip() for l in poem.strip().split("\n") if l.strip()]
    for line in poem_lines:
        current_y = _draw_center(draw, current_y, line, font_poem, (74, 55, 40)) + 10
    current_y += 16

    # ── 署名 ──
    current_y = _draw_center(draw, current_y, f"—— {reviewer_stamp}", font_sign, GREY) + 40

    # ── 底部分隔线 ──
    draw.line([(lx, current_y), (lx + line_w, current_y)], fill=ORANGE, width=2)
    current_y += 50

    # ── 品牌 ──
    current_y = _draw_center(draw, current_y, "时光修复", font_brand, ORANGE) + 8
    current_y = _draw_center(draw, current_y, "AI 照片品鉴与修复", font_sub, GREY) + 8
    _draw_center(draw, current_y, "扫码体验，让老照片重获新生", font_guide, LIGHT_GREY)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


@router.post("/api/share-card")
async def create_share_card(data: ShareCardRequest):
    """生成品鉴分享卡片，返回 base64 data URI"""
    import base64

    # 获取照片字节
    if data.file_url:
        import requests
        resp = requests.get(data.file_url, timeout=30)
        resp.raise_for_status()
        photo_bytes = resp.content
    elif data.file:
        photo_bytes = base64.b64decode(data.file)
    else:
        from fastapi import HTTPException
        raise HTTPException(400, "请提供图片 (file_url 或 file)")

    try:
        png_bytes = generate_card(
            photo_bytes=photo_bytes,
            poem=data.poem,
            reviewer_name=data.reviewer_name,
            reviewer_emoji=data.reviewer_emoji,
            reviewer_stamp=data.reviewer_stamp,
        )
        b64 = base64.b64encode(png_bytes).decode("utf-8")
        return {
            "success": True,
            "image": f"data:image/png;base64,{b64}",
            "size": len(png_bytes),
        }
    except Exception as e:
        logger.error(f"分享卡片生成失败: {e}")
        from fastapi import HTTPException
        raise HTTPException(500, f"卡片生成失败: {str(e)}")
