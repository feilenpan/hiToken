"""
时光修复 - 分享卡片 API
POST /api/share-card → 动态高度 PNG (base64 data URI)
极简风格：透明背景、白卡 + 照片、金句 + 诗词 + 署名 + 品牌
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
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
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
CARD_W = 1080                # 白卡宽度
CARD_RADIUS = 24             # 白卡圆角
CARD_PAD = 48                # 白卡内部边距
SHADOW_MARGIN = 20           # 阴影外延
PHOTO_MAX_W = CARD_W - CARD_PAD * 2       # 照片最大宽 ~984
PHOTO_MAX_H = 1200           # 照片最大高
PHOTO_RADIUS = 12            # 照片圆角
TEXT_MAX_W = PHOTO_MAX_W - 40  # 文字最大宽度

# 色调
CARD_BG = (255, 255, 255)      # 白卡
QUOTE_C = (60, 40, 25)         # 深棕（金句）
TEXT_C  = (100, 85, 70)        # 中棕（评语）
POEM_C  = (120, 105, 90)       # 浅棕（诗词）
AUTHOR_C = (160, 140, 120)     # 浅棕（署名）
BRAND_C = (180, 150, 120)      # 淡金（品牌）
WHITE = (255, 255, 255)


def _round_corners(im: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", im.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (im.size[0]-1, im.size[1]-1)], radius=radius, fill=255)
    result = im.copy()
    result.putalpha(mask)
    return result


def _text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_center(draw, y, text, font, color):
    tw, th = _text_size(draw, text, font)
    x = (CARD_W - tw) // 2
    draw.text((x, y), text, font=font, fill=color)
    return y + th


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
    return lines


def _smart_truncate(text: str, max_chars: int) -> str:
    """智能截断：优先在句号/问号/感叹号处断句"""
    if len(text) <= max_chars:
        return text
    for sep in '。！？!?':
        idx = text[:max_chars].rfind(sep)
        if idx > max_chars * 2 // 3:
            return text[:idx+1]
    return text[:max_chars].rstrip() + '…'


class ShareCardRequest(BaseModel):
    file_url: str = ""
    file: str = ""
    poem: str = ""
    text: str = ""
    quote: str = ""
    reviewer_name: str = ""     # 不再渲染，保留兼容
    reviewer_emoji: str = ""    # 不再渲染，保留兼容
    reviewer_stamp: str = ""


def generate_card(photo_bytes: bytes, poem: str = "", text: str = "",
                  quote: str = "", reviewer_name: str = "",
                  reviewer_emoji: str = "", reviewer_stamp: str = "") -> bytes:
    """生成分享卡片 — 透明背景、白卡 + 照片 + 文字"""

    # ── 字体 ──
    font_quote  = _load_font(34)
    font_text   = _load_font(26)
    font_poem   = _load_font(28)
    font_author = _load_font(22)
    font_brand  = _load_font(20)

    # ── 1. 加载照片 ──
    try:
        photo = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
    except Exception:
        photo = Image.new("RGB", (600, 400), (220, 220, 220))

    pw, ph = photo.size
    scale = min(PHOTO_MAX_W / pw, PHOTO_MAX_H / ph, 1.0)
    new_w, new_h = int(pw * scale), int(ph * scale)
    photo = photo.resize((new_w, new_h), Image.LANCZOS)

    photo_x = CARD_PAD + (PHOTO_MAX_W - new_w) // 2

    # ── 2. 预计算文字高度 ──
    temp_img = Image.new("RGB", (CARD_W, 100))
    temp_draw = ImageDraw.Draw(temp_img)
    text_height = 0

    # 金句
    quote_lines = []
    if quote:
        quote_lines = _wrap_text(temp_draw, f"「{quote}」", font_quote, TEXT_MAX_W)
        for _ in quote_lines:
            _, th = _text_size(temp_draw, "测", font_quote)
            text_height += th + 6
        text_height += 12

    # 品鉴评语 — 精简为1-2句
    text_lines = []
    if text:
        concise = _smart_truncate(text, 50)
        text_lines = _wrap_text(temp_draw, concise, font_text, TEXT_MAX_W)
        text_lines = text_lines[:2]
        for _ in text_lines:
            _, th = _text_size(temp_draw, "测", font_text)
            text_height += th + 6
        text_height += 12

    # 诗词
    poem_lines_list = []
    if poem:
        raw_lines = [l.strip() for l in poem.strip().split("\n") if l.strip()]
        for line in raw_lines:
            wrapped = _wrap_text(temp_draw, line, font_poem, TEXT_MAX_W)
            poem_lines_list.extend(wrapped)
    if poem_lines_list:
        for _ in poem_lines_list:
            _, th = _text_size(temp_draw, "测", font_poem)
            text_height += th + 8
        text_height += 12

    # 署名
    show_stamp = bool(reviewer_stamp)
    if show_stamp:
        _, th = _text_size(temp_draw, "测", font_author)
        text_height += th + 8

    # 品牌（固定）
    _, brand_th = _text_size(temp_draw, "时光修复", font_brand)
    text_height += brand_th + 16

    # ── 3. 计算卡片高度 ──
    card_content_h = CARD_PAD + new_h + 24
    if text_height > 0:
        card_content_h += text_height + CARD_PAD
    else:
        card_content_h += CARD_PAD
    card_h = card_content_h

    # 画布 = 卡片 + 阴影 margin
    canvas_w = CARD_W + SHADOW_MARGIN * 2
    canvas_h = card_h + SHADOW_MARGIN * 2

    # ── 4. 创建画布（RGBA，透明背景）──
    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 阴影
    shadow = Image.new("RGBA", (CARD_W + 24, card_h + 24), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [(12, 16), (CARD_W + 11, card_h + 15)],
        radius=CARD_RADIUS + 4, fill=(0, 0, 0, 18)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    card_x = SHADOW_MARGIN
    card_y = SHADOW_MARGIN
    img.paste(shadow, (card_x - 12, card_y - 4), shadow)

    # 白卡
    card = Image.new("RGBA", (CARD_W, card_h), (255, 255, 255, 255))
    card = _round_corners(card, CARD_RADIUS)
    img.paste(card, (card_x, card_y), card)

    # ── 5. 照片 ──
    photo_rounded = _round_corners(photo, PHOTO_RADIUS)
    photo_paste_x = card_x + photo_x
    photo_paste_y = card_y + CARD_PAD
    img.paste(photo_rounded, (photo_paste_x, photo_paste_y), photo_rounded)

    current_y = card_y + CARD_PAD + new_h + 24

    # ── 6. 文字 ──
    # 金句
    if quote_lines:
        for line in quote_lines:
            current_y = _draw_center(draw, current_y, line, font_quote, QUOTE_C) + 6
        current_y += 12

    # 品鉴评语
    if text_lines:
        for line in text_lines:
            current_y = _draw_center(draw, current_y, line, font_text, TEXT_C) + 6
        current_y += 12

    # 诗词
    if poem_lines_list:
        for line in poem_lines_list:
            current_y = _draw_center(draw, current_y, line, font_poem, POEM_C) + 8

    # 署名
    if show_stamp:
        current_y += 8
        sign_text = f"—— {reviewer_stamp}"
        current_y = _draw_center(draw, current_y, sign_text, font_author, AUTHOR_C) + 4

    # 品牌
    current_y += 16
    _draw_center(draw, current_y, "时光修复", font_brand, BRAND_C)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


@router.post("/api/share-card")
async def create_share_card(data: ShareCardRequest):
    """生成品鉴分享卡片，返回 base64 data URI"""
    import base64

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
