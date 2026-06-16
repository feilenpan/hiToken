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
PAD_TOP = 60
PHOTO_MAX_W = 1000
PHOTO_MAX_H = 1050
PHOTO_RADIUS = 16
PAD_SIDE = 40
TEXT_MAX_W = W - 2 * PAD_SIDE - 40  # 文字最大宽度

# 暖纸色调
BG = (250, 247, 242)           # 暖白纸色
QUOTE_C = (61, 50, 38)         # 深棕（金句）
TEXT_C = (107, 95, 82)         # 中棕（评语）
POEM_C = (155, 141, 128)       # 浅棕（诗词）
BRAND_C = (196, 168, 130)      # 淡金（品牌）
SHADOW_C = (0, 0, 0, 6)        # 极淡阴影
WHITE = (255, 255, 255)


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
    text: str = ""
    quote: str = ""
    reviewer_name: str = ""
    reviewer_emoji: str = ""
    reviewer_stamp: str = ""


def _wrap_text(draw, text, font, max_width):
    """中文换行"""
    lines = []
    cur = ""
    for ch in text:
        test = cur + ch
        w, _ = _text_size(draw, test, font)
        if w > max_width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines[:3]  # 最多3行


def generate_card(photo_bytes: bytes, poem: str, text: str = "",
                  quote: str = "", reviewer_name: str = "",
                  reviewer_emoji: str = "", reviewer_stamp: str = "") -> bytes:
    """生成分享卡片，返回 PNG bytes"""
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # 字体层级
    font_quote = _load_font(36)
    font_text = _load_font(26)
    font_poem = _load_font(22)
    font_brand = _load_font(20)

    current_y = PAD_TOP

    # ── 照片区 ──
    try:
        photo = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
    except Exception:
        photo = Image.new("RGB", (600, 400), (220, 220, 220))

    pw, ph = photo.size
    scale = min(PHOTO_MAX_W / pw, PHOTO_MAX_H / ph)
    new_w, new_h = int(pw * scale), int(ph * scale)
    photo = photo.resize((new_w, new_h), Image.LANCZOS)

    card_w = new_w + 32
    card_h = new_h + 32
    card_x = (W - card_w) // 2

    # 柔和阴影
    shadow = Image.new("RGBA", (card_w + 24, card_h + 24), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [(12, 16), (card_w + 11, card_h + 15)],
        radius=PHOTO_RADIUS + 6, fill=SHADOW_C
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(20))
    img.paste(shadow, (card_x - 12, current_y - 4), shadow)

    # 白色卡片底
    card = Image.new("RGBA", (card_w, card_h), (255, 255, 255, 255))
    card = _round_corners(card, PHOTO_RADIUS)
    img.paste(card, (card_x, current_y), card)

    # 照片
    photo = _round_corners(photo, PHOTO_RADIUS - 2)
    img.paste(photo, (card_x + 16, current_y + 16), photo)
    current_y += card_h + 36

    # ── 金句 ──
    if quote:
        current_y += 12
        # 左引号装饰
        lq = "「"
        rq = "」"
        full = lq + quote + rq
        current_y = _draw_center(draw, current_y, full, font_quote, QUOTE_C)
        current_y += 20

    # ── 品鉴评语 ──
    if text:
        # 截取前70字，换行处理
        short = text[:70].rstrip()
        text_lines = _wrap_text(draw, short, font_text, TEXT_MAX_W)
        for line in text_lines[:2]:  # 最多2行
            current_y = _draw_center(draw, current_y, line, font_text, TEXT_C) + 8
        current_y += 18

    # ── 诗词 ──
    if poem:
        poem_lines = [l.strip() for l in poem.strip().split("\n") if l.strip()]
        if poem_lines:
            current_y += 6
            # 装饰点
            lx = (W - 160) // 2
            dot_y = current_y + 6
            draw.ellipse([lx, dot_y, lx + 4, dot_y + 4], fill=BRAND_C)
            draw.ellipse([lx + 156, dot_y, lx + 160, dot_y + 4], fill=BRAND_C)
            current_y += 18
            for line in poem_lines:
                current_y = _draw_center(draw, current_y, line, font_poem, POEM_C) + 8
            current_y += 22

    # ── 品牌 ──
    # 确保底部有足够留白
    bottom_min = H - 40
    if current_y < bottom_min:
        current_y = bottom_min - _text_size(draw, "时光修复", font_brand)[1]
    _draw_center(draw, current_y, "时光修复", font_brand, BRAND_C)

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
            text=data.text,
            quote=data.quote,
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
