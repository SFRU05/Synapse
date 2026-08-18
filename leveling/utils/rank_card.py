"""
레벨 카드 이미지 생성 모듈 (Pillow)
generate_rank_card()가 완성된 카드 이미지를 BytesIO로 반환합니다.
"""
import io
import os
from PIL import Image, ImageDraw, ImageFont, ImageOps

WIDTH, HEIGHT = 934, 300
BG_COLOR = (30, 33, 40)
CARD_COLOR = (44, 47, 56)
ACCENT = (88, 101, 242)   # 디스코드 블러플
BAR_BG = (60, 63, 73)
TEXT_MAIN = (255, 255, 255)
TEXT_SUB = (170, 173, 182)

FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")


def _load_font(size: int, bold: bool = False):
    candidates = []
    if bold:
        candidates += [
            os.path.join(FONT_DIR, "NanumGothicBold.ttf"),
            os.path.join(FONT_DIR, "Pretendard-Bold.ttf"),
        ]
    else:
        candidates += [
            os.path.join(FONT_DIR, "NanumGothic.ttf"),
            os.path.join(FONT_DIR, "Pretendard-Regular.ttf"),
        ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    for fallback in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if os.path.exists(fallback):
            return ImageFont.truetype(fallback, size)
    return ImageFont.load_default()


def _rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (size[0] - 1, size[1] - 1)], radius=radius, fill=255)
    return mask


def _circle_avatar(avatar_bytes: bytes, size: int):
    img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    img = ImageOps.fit(img, (size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    img.putalpha(mask)
    return img


def generate_rank_card(
    display_name: str,
    avatar_bytes: bytes,
    level: int,
    exp: int,
    need: int,
    total_messages: int,
    today_count: int,
    week_total: int,
    weekly: list,  # [(date_str, label, count), ...] 7개
) -> io.BytesIO:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([(0, 0), (WIDTH - 1, HEIGHT - 1)], radius=24, fill=CARD_COLOR)

    avatar_size = 128
    avatar = _circle_avatar(avatar_bytes, avatar_size)
    ax, ay = 36, 40
    img.paste(avatar, (ax, ay), avatar)
    draw.ellipse([ax - 3, ay - 3, ax + avatar_size + 3, ay + avatar_size + 3],
                 outline=ACCENT, width=4)

    font_name = _load_font(30, bold=True)
    font_label = _load_font(18)
    font_level = _load_font(26, bold=True)
    font_stat_num = _load_font(30, bold=True)
    font_stat_label = _load_font(16)
    font_small = _load_font(15)

    text_x = ax + avatar_size + 30
    draw.text((text_x, ay - 4), display_name, font=font_name, fill=TEXT_MAIN)
    draw.text((text_x, ay + 40), f"LEVEL {level}", font=font_level, fill=ACCENT)

    # ---- exp 진행바 ----
    bar_x, bar_y = text_x, ay + 84
    bar_w, bar_h = 420, 20
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=10, fill=BAR_BG)
    ratio = min(exp / need, 1.0) if need else 0
    if ratio > 0:
        draw.rounded_rectangle(
            [bar_x, bar_y, bar_x + max(int(bar_w * ratio), bar_h), bar_y + bar_h],
            radius=10, fill=ACCENT
        )
    draw.text((bar_x, bar_y + bar_h + 6), f"{exp} / {need} EXP", font=font_small, fill=TEXT_SUB)

    # ---- 오늘 / 이번주 / 누적 통계 박스 ----
    stats = [
        ("오늘 채팅", f"{today_count}"),
        ("이번주 채팅", f"{week_total}"),
        ("누적 채팅", f"{total_messages}"),
    ]
    stats_area_right = WIDTH - 40
    stats_area_left = 560
    box_w = (stats_area_right - stats_area_left) // len(stats)
    box_y = 40
    for i, (label, value) in enumerate(stats):
        bx = stats_area_left + i * box_w
        draw.text((bx, box_y), value, font=font_stat_num, fill=TEXT_MAIN)
        draw.text((bx, box_y + 38), label, font=font_stat_label, fill=TEXT_SUB)

    # ---- 주간 채팅량 바 차트 ----
    chart_x0, chart_y0 = 36, 210
    chart_w, chart_h = WIDTH - 72, 66
    max_count = max([c for _, _, c in weekly] + [1])
    bar_gap = 14
    n = len(weekly)
    bar_w2 = (chart_w - bar_gap * (n - 1)) / n

    for i, (date_str, label, count) in enumerate(weekly):
        bx0 = chart_x0 + i * (bar_w2 + bar_gap)
        h = int((count / max_count) * (chart_h - 20)) if max_count else 0
        h = max(h, 3)
        by1 = chart_y0 + chart_h
        by0 = by1 - h
        is_today = (i == n - 1)
        color = ACCENT if is_today else BAR_BG
        draw.rounded_rectangle([bx0, by0, bx0 + bar_w2, by1], radius=6, fill=color)
        # 요일 라벨
        label_font = font_small
        lw = draw.textlength(label, font=label_font)
        draw.text((bx0 + bar_w2 / 2 - lw / 2, by1 + 6), label,
                   font=label_font, fill=TEXT_MAIN if is_today else TEXT_SUB)
        # 카운트 숫자 (막대 위)
        cnt_str = str(count)
        cw = draw.textlength(cnt_str, font=label_font)
        draw.text((bx0 + bar_w2 / 2 - cw / 2, by0 - 20), cnt_str,
                   font=label_font, fill=TEXT_SUB)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
