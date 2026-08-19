"""
레벨 카드 이미지 생성 모듈 (Pillow)
generate_rank_card()가 완성된 카드 이미지를 BytesIO로 반환합니다.
"""
import io
from datetime import datetime
from PIL import Image, ImageDraw

from leveling.utils.image_common import load_font, circle_image, fit_font_and_text, draw_smooth_ring

WIDTH, HEIGHT = 934, 340
HEADER_H = 44  # 서버 아이콘/이름이 들어가는 상단 영역 높이
BG_COLOR = (30, 33, 40)
CARD_COLOR = (44, 47, 56)
HEADER_COLOR = (36, 39, 47)
ACCENT = (88, 101, 242)   # 디스코드 블러플
BAR_BG = (60, 63, 73)
TEXT_MAIN = (255, 255, 255)
TEXT_SUB = (170, 173, 182)


def generate_rank_card(
    display_name: str,
    avatar_bytes: bytes,
    level: int,
    exp: int,
    need: int,
    total_messages: int,
    today_count: int,
    week_total: int,
    weekly: list,  # [(date_str, label, count), ...] 7개, 일~토 고정 순서
    guild_name: str | None = None,
    guild_icon_bytes: bytes | None = None,
) -> io.BytesIO:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 카드 배경
    draw.rounded_rectangle([(0, 0), (WIDTH - 1, HEIGHT - 1)], radius=24, fill=CARD_COLOR)

    # ---- 상단 헤더: 서버 아이콘 + 서버 이름 ----
    draw.rounded_rectangle([(0, 0), (WIDTH - 1, HEADER_H)], radius=24, fill=HEADER_COLOR)
    draw.rectangle([(0, HEADER_H - 20), (WIDTH - 1, HEADER_H)], fill=HEADER_COLOR)  # 아래쪽 각 살리기

    font_header = load_font(18, bold=True)
    header_icon_size = 28
    header_x = 24
    g_icon = circle_image(guild_icon_bytes, header_icon_size)
    img.paste(g_icon, (header_x, (HEADER_H - header_icon_size) // 2), g_icon)
    text_start = header_x + header_icon_size + 12

    if guild_name:
        _, fitted_guild_name = fit_font_and_text(
            draw, guild_name, WIDTH - text_start - 24, 18, bold=True, min_size=14
        )
        text_y = (HEADER_H - 22) // 2
        draw.text((text_start, text_y), fitted_guild_name, font=font_header, fill=TEXT_MAIN)

    # ---- 아바타 ----
    avatar_size = 128
    avatar = circle_image(avatar_bytes, avatar_size)
    ax, ay = 36, HEADER_H + 36
    img.paste(avatar, (ax, ay), avatar)
    draw_smooth_ring(img, (ax - 3, ay - 3, ax + avatar_size + 3, ay + avatar_size + 3), ACCENT, 4)

    # ---- 이름 / 레벨 ----
    font_level = load_font(26, bold=True)
    font_stat_num = load_font(30, bold=True)
    font_stat_label = load_font(16)
    font_small = load_font(15)

    text_x = ax + avatar_size + 30
    name_max_width = 560 - text_x - 20  # 통계 박스 시작 지점(560) 전까지만 사용
    font_name, fitted_name = fit_font_and_text(
        draw, display_name, name_max_width, base_size=30, bold=True, min_size=16
    )
    draw.text((text_x, ay - 4), fitted_name, font=font_name, fill=TEXT_MAIN)
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
    draw.text((bar_x, bar_y + bar_h + 6), f"{exp:,} / {need:,} EXP", font=font_small, fill=TEXT_SUB)

    # ---- 오늘 / 이번주 / 누적 통계 박스 ----
    stats = [
        ("오늘 채팅", f"{today_count:,}"),
        ("이번주 채팅", f"{week_total:,}"),
        ("누적 채팅", f"{total_messages:,}"),
    ]
    stats_area_right = WIDTH - 40
    stats_area_left = 560
    box_w = (stats_area_right - stats_area_left) // len(stats)
    box_y = HEADER_H + 40
    for i, (label, value) in enumerate(stats):
        bx = stats_area_left + i * box_w
        draw.text((bx, box_y), value, font=font_stat_num, fill=TEXT_MAIN)
        draw.text((bx, box_y + 38), label, font=font_stat_label, fill=TEXT_SUB)

    # ---- 주간 채팅량 바 차트 (일~토 고정 순서) ----
    chart_x0, chart_y0 = 36, HEADER_H + 188
    chart_w, chart_h = WIDTH - 72, 66
    max_count = max([c for _, _, c in weekly] + [1])
    bar_gap = 14
    n = len(weekly)
    bar_w2 = (chart_w - bar_gap * (n - 1)) / n
    today_str = datetime.now().strftime("%Y-%m-%d")

    for i, (date_str, label, count) in enumerate(weekly):
        bx0 = chart_x0 + i * (bar_w2 + bar_gap)
        h = int((count / max_count) * (chart_h - 20)) if max_count else 0
        h = max(h, 3)
        by1 = chart_y0 + chart_h
        by0 = by1 - h
        is_today = (date_str == today_str)
        color = ACCENT if is_today else BAR_BG
        draw.rounded_rectangle([bx0, by0, bx0 + bar_w2, by1], radius=6, fill=color)
        # 요일 라벨
        label_font = font_small
        lw = draw.textlength(label, font=label_font)
        draw.text((bx0 + bar_w2 / 2 - lw / 2, by1 + 6), label,
                   font=label_font, fill=TEXT_MAIN if is_today else TEXT_SUB)
        # 카운트 숫자 (막대 위)
        cnt_str = f"{count:,}"
        cw = draw.textlength(cnt_str, font=label_font)
        draw.text((bx0 + bar_w2 / 2 - cw / 2, by0 - 20), cnt_str,
                   font=label_font, fill=TEXT_SUB)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
