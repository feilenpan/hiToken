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
CANVAS_W = 1080
CARD_MARGIN = 32         # 白卡到画布边缘
CARD_RADIUS = 24         # 白卡圆角
CARD_PAD = 48            # 白卡内部边距
PHOTO_MAX_W = CANVAS_W - CARD_MARGIN * 2 - CARD_PAD * 2  # 照片最大宽 ~920
PHOTO_MAX_H = 1100       # 照片最大高（更宽松）
PHOTO_RADIUS = 12        # 照片圆角
POEM_MAX_W = PHOTO_MAX_W - 40  # 诗词最大宽度

# 暖纸色调
BG = (250, 247, 242)           # 暖白底色
CARD_BG = (255, 255, 255)      # 白卡
TITLE_C = (80, 50, 30)         # 深棕（标题）
POEM_C = (80, 65, 50)          # 棕（诗词正文）
AUTHOR_C = (160, 140, 120)     # 浅棕（署名）
BRAND_C = (180, 150, 120)      # 淡金（品牌）
DIVIDER_C = (230, 220, 210)    # 分隔线


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
    x = (CANVAS_W - tw) // 2
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
    """中文换行，不限制行数"""
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


def generate_card(photo_bytes: bytes, poem: str = "", text: str = "",
                  quote: str = "", reviewer_name: str = "",
                  reviewer_emoji: str = "", reviewer_stamp: str = "") -> bytes:
    """生成分享卡片 — 动态高度，单白卡包裹照片+文字"""
    
    # ── 字体 ──
    font_title = _load_font(32)
    font_quote = _load_font(30)
    font_text  = _load_font(24)
    font_poem  = _load_font(28)
    font_author = _load_font(22)
    font_brand = _load_font(20)
    
    # ── 1. 加载照片，计算尺寸 ──
    try:
        photo = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
    except Exception:
        photo = Image.new("RGB", (600, 400), (220, 220, 220))
    
    pw, ph = photo.size
    scale = min(PHOTO_MAX_W / pw, PHOTO_MAX_H / ph, 1.0)
    new_w, new_h = int(pw * scale), int(ph * scale)
    photo = photo.resize((new_w, new_h), Image.LANCZOS)
    
    # 照片在卡内的 x 位置（居中）
    photo_x = CARD_PAD + (PHOTO_MAX_W - new_w) // 2
    
    # ── 2. 预计算文字区域高度 ──
    # 用临时 draw 计算
    temp_img = Image.new("RGB", (CANVAS_W, 100))
    temp_draw = ImageDraw.Draw(temp_img)
    
    text_height = 0
    
    # 点评师标题行
    reviewer_line = ""
    if reviewer_name:
        r_emoji = reviewer_emoji or ""
        reviewer_line = f"{r_emoji}  {reviewer_name}  品鉴"
    if reviewer_line:
        _, th = _text_size(temp_draw, reviewer_line, font_title)
        text_height += th + 16  # 标题 + 间距
    
    # 分隔线
    if reviewer_line:
        text_height += 16  # 线 + 上下间距
    
    # 金句
    quote_lines = []
    if quote:
        quote_lines = _wrap_text(temp_draw, f"「{quote}」", font_quote, POEM_MAX_W)
        for _ in quote_lines:
            _, th = _text_size(temp_draw, "测", font_quote)
            text_height += th + 6
        text_height += 8  # 金句底部间距
    
    # 品鉴评语
    text_lines = []
    if text:
        short = text[:80].rstrip()
        text_lines = _wrap_text(temp_draw, short, font_text, POEM_MAX_W)
        text_lines = text_lines[:3]  # 最多3行
        for _ in text_lines:
            _, th = _text_size(temp_draw, "测", font_text)
            text_height += th + 6
        text_height += 10  # 评语底部间距
    
    # 诗词
    poem_lines_list = []
    if poem:
        raw_lines = [l.strip() for l in poem.strip().split("\n") if l.strip()]
        for line in raw_lines:
            wrapped = _wrap_text(temp_draw, line, font_poem, POEM_MAX_W)
            poem_lines_list.extend(wrapped)
    if poem_lines_list:
        for _ in poem_lines_list:
            _, th = _text_size(temp_draw, "测", font_poem)
            text_height += th + 8
        text_height += 12  # 底部间距
    
    # 署名
    show_stamp = bool(reviewer_stamp)
    if show_stamp:
        _, th = _text_size(temp_draw, "测", font_author)
        text_height += th + 12
    
    # ── 3. 计算卡片总高度 ──
    card_content_h = CARD_PAD + new_h + 20  # 顶部padding + 照片 + 间距
    if text_height > 0:
        card_content_h += text_height + CARD_PAD
    else:
        card_content_h += CARD_PAD
    card_h = card_content_h
    card_w = CANVAS_W - CARD_MARGIN * 2
    card_x = CARD_MARGIN
    
    # 画布高度 = 卡片高度 + 上下边距
    canvas_h = card_h + CARD_MARGIN * 2
    
    # ── 4. 创建画布 + 白卡 ──
    img = Image.new("RGB", (CANVAS_W, canvas_h), BG)
    draw = ImageDraw.Draw(img)
    
    # 白卡阴影
    shadow = Image.new("RGBA", (card_w + 24, card_h + 24), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [(12, 16), (card_w + 11, card_h + 15)],
        radius=CARD_RADIUS + 4, fill=(0, 0, 0, 18)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    img.paste(shadow, (card_x - 12, CARD_MARGIN - 4), shadow)
    
    # 白卡
    card = Image.new("RGBA", (card_w, card_h), (255, 255, 255, 255))
    card = _round_corners(card, CARD_RADIUS)
    img.paste(card, (card_x, CARD_MARGIN), card)
    
    # ── 5. 绘制照片 ──
    photo_rounded = _round_corners(photo, PHOTO_RADIUS)
    img.paste(photo_rounded, (card_x + photo_x, CARD_MARGIN + CARD_PAD), photo_rounded)
    
    current_y = CARD_MARGIN + CARD_PAD + new_h + 20
    
    # ── 6. 绘制文字 ──
    if reviewer_line:
        current_y = _draw_center(draw, current_y, reviewer_line, font_title, TITLE_C)
        current_y += 16
        # 分隔线
        line_w = 200
        line_x = (CANVAS_W - line_w) // 2
        draw.line([(line_x, current_y), (line_x + line_w, current_y)], fill=DIVIDER_C, width=2)
        current_y += 16
    
    # 金句
    if quote_lines:
        for line in quote_lines:
            current_y = _draw_center(draw, current_y, line, font_quote, TITLE_C) + 6
        current_y += 8
    
    # 品鉴评语
    if text_lines:
        for line in text_lines:
            current_y = _draw_center(draw, current_y, line, font_text, POEM_C) + 6
        current_y += 10
    
    # 诗词
    if poem_lines_list:
        for line in poem_lines_list:
            current_y = _draw_center(draw, current_y, line, font_poem, POEM_C) + 8
    
    # 署名
    if show_stamp:
        current_y += 8
        sign_text = f"—— {reviewer_stamp}"
        _draw_center(draw, current_y, sign_text, font_author, AUTHOR_C)
    
    # ── 品牌签章 ──
    current_y += 8
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
