"""
时光修复 - 品鉴分享卡片生成器
1080×1500 高清 PNG，服务端 Pillow 生成
方案C极简情感风格：暖色渐变背景、圆角卡片、橙色主题
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import math
import os
from pathlib import Path

# ── 字体路径 ──
FONT_DIR = Path(__file__).parent / "fonts"

def _load_font(size: int, bold: bool = False):
    """加载字体，优先 PingFang / STHeiti"""
    paths = [
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    # fallback
    return ImageFont.load_default()


# ── 卡片常量 ──
W, H = 1080, 1500
PAD = 60           # 边距
PHOTO_MAX_W = 900
PHOTO_MAX_H = 650
PHOTO_RADIUS = 24
BRAND_H = 200      # 底部品牌区高度
CARD_BG_TOP = (255, 248, 240)      # #FFF8F0
CARD_BG_BOT = (255, 228, 210)      # #FFE4D2
ORANGE = (255, 107, 53)            # #FF6B35
DARK = (51, 51, 51)                # #333
GREY = (120, 120, 120)             # #787878
LIGHT_GREY = (170, 170, 170)       # #aaa
WHITE = (255, 255, 255)


def _round_corners(im: Image.Image, radius: int) -> Image.Image:
    """给图片加圆角（用 mask）"""
    mask = Image.new("L", im.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (im.size[0] - 1, im.size[1] - 1)], radius=radius, fill=255)
    result = im.copy()
    result.putalpha(mask)
    return result


def _draw_gradient_bg(draw: ImageDraw.Draw):
    """从上到下暖色渐变背景"""
    for y in range(H):
        t = y / H
        r = int(CARD_BG_TOP[0] + (CARD_BG_BOT[0] - CARD_BG_TOP[0]) * t)
        g = int(CARD_BG_TOP[1] + (CARD_BG_BOT[1] - CARD_BG_TOP[1]) * t)
        b = int(CARD_BG_TOP[2] + (CARD_BG_BOT[2] - CARD_BG_TOP[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def _text_size(draw, text, font):
    """测量文字尺寸"""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_centered_text(draw, y, text, font, color):
    """居中绘制单行文字，返回下一行 y"""
    tw, th = _text_size(draw, text, font)
    x = (W - tw) // 2
    draw.text((x, y), text, font=font, fill=color)
    return y + th


def generate_share_card(
    photo_path: str,
    poem_text: str,
    reviewer_name: str = "李白",
    reviewer_emoji: str = "🍶",
    reviewer_stamp: str = "太白醉评",
    output_path: str = None,
) -> str:
    """
    生成品鉴分享卡片

    Args:
        photo_path: 用户照片路径（本地文件）
        poem_text: 诗词文本，用 \\n 分行
        reviewer_name: 点评师名
        reviewer_emoji: 点评师 emoji
        reviewer_stamp: 点评师印章文字
        output_path: 输出路径，默认 /tmp/share_card.png

    Returns:
        输出文件路径
    """
    if output_path is None:
        output_path = "/tmp/share_card.png"

    # ── 创建画布 ──
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)
    _draw_gradient_bg(draw)

    # ── 加载字体 ──
    font_title = _load_font(42, bold=True)    # 点评师标题
    font_poem = _load_font(34)                 # 诗词正文
    font_sign = _load_font(26)                 # 署名
    font_brand = _load_font(36)                # 品牌名
    font_sub = _load_font(24)                  # 副标题
    font_guide = _load_font(22)                # 引导语

    current_y = PAD

    # ── 1. 照片区（白色卡片 + 圆角 + 阴影）──
    try:
        photo = Image.open(photo_path).convert("RGB")
    except Exception:
        # 占位图
        photo = Image.new("RGB", (600, 400), (220, 220, 220))

    # 等比缩放
    pw, ph = photo.size
    scale = min(PHOTO_MAX_W / pw, PHOTO_MAX_H / ph)
    new_w, new_h = int(pw * scale), int(ph * scale)
    photo = photo.resize((new_w, new_h), Image.LANCZOS)

    # 照片容器（白色卡片 + 阴影）
    card_w = new_w + 40
    card_h = new_h + 40
    card_x = (W - card_w) // 2

    # 阴影
    shadow = Image.new("RGBA", (card_w + 20, card_h + 20), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        [(10, 14), (card_w + 9, card_h + 13)],
        radius=PHOTO_RADIUS + 4,
        fill=(0, 0, 0, 40),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    img.paste(shadow, (card_x - 10, current_y - 4), shadow)

    # 白色卡片
    card = Image.new("RGBA", (card_w, card_h), (255, 255, 255, 255))
    card = _round_corners(card, PHOTO_RADIUS)
    img.paste(card, (card_x, current_y), card)

    # 照片贴入卡片
    photo = _round_corners(photo, PHOTO_RADIUS - 4)
    img.paste(photo, (card_x + 20, current_y + 20), photo)

    current_y += card_h + 50

    # ── 2. 点评师标题 ──
    title = f"{reviewer_emoji}  {reviewer_name}  品鉴"
    current_y = _draw_centered_text(draw, current_y, title, font_title, DARK) + 12

    # ── 3. 分隔线 ──
    line_w = 200
    line_x = (W - line_w) // 2
    draw.line([(line_x, current_y), (line_x + line_w, current_y)], fill=ORANGE, width=3)
    current_y += 36

    # ── 4. 诗词正文 ──
    poem_lines = [l.strip() for l in poem_text.strip().split("\n") if l.strip()]
    for line in poem_lines:
        current_y = _draw_centered_text(draw, current_y, line, font_poem, (74, 55, 40)) + 10
    current_y += 16

    # ── 5. 署名 ──
    sign_text = f"—— {reviewer_stamp}"
    current_y = _draw_centered_text(draw, current_y, sign_text, font_sign, GREY) + 40

    # ── 6. 底部分隔线 ──
    draw.line([(line_x, current_y), (line_x + line_w, current_y)], fill=ORANGE, width=2)
    current_y += 50

    # ── 7. 品牌区 ──
    # 品牌名
    current_y = _draw_centered_text(draw, current_y, "时光修复", font_brand, ORANGE) + 8
    # 副标题
    current_y = _draw_centered_text(draw, current_y, "AI 照片品鉴与修复", font_sub, GREY) + 8
    # 引导语
    current_y = _draw_centered_text(draw, current_y, "扫码体验，让老照片重获新生", font_guide, LIGHT_GREY)

    # ── 保存 ──
    img.save(output_path, "PNG", quality=95)
    return output_path


# ── 测试入口 ──
if __name__ == "__main__":
    # 用一张测试图片
    test_photo = "/Users/fiona/WeChatProjects/colorize-miniapp/images/btn-camera.png"
    poem = """春风不解江南雨，
笑看浮云自卷舒。
一壶浊酒邀明月，
半卷诗书半日无。"""

    path = generate_share_card(
        photo_path=test_photo,
        poem_text=poem,
        reviewer_name="李白",
        reviewer_emoji="🍶",
        reviewer_stamp="太白醉评",
    )
    print(f"✅ 卡片已生成: {path}")
