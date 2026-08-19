"""
서버 주간 채팅 순위 카드 이미지 생성 모듈 (Pillow)
generate_leaderboard_card()가 완성된 카드 이미지를 BytesIO로 반환합니다.
"""
import io
from PIL import Image, ImageDraw

from leveling.utils.image_common import load_font, circle_image, fit_font_and_text

WIDTH = 934
HEADER_H = 44
ROW_H = 58
ROW_GAP = 6
TOP_PAD = 16
BOTTOM_PAD = 18
DIVIDER_H = 34

BG_COLOR = (30, 33, 40)
CARD_COLOR = (44, 47, 56)
HEADER_COLOR = (36, 39, 47)
ROW_COLOR = (52, 55, 65)
ME_ROW_COLOR = (58, 62, 92)   # 내 순위 행 강조 배경
ACCENT = (88, 101, 242)
TEXT_MAIN = (255, 255, 255)
TEXT_SUB = (170, 173, 182)

RANK_COLORS = {
    1: (255, 208, 80),   # 금
    2: (200, 205, 214),  # 은
    3: (205, 140, 90),   # 동
}


def _draw_row(img, draw, y, entry, is_me=False):
    """
    entry: {"rank": int|None, "name": str, "avatar_bytes": bytes|None,
            "level": int, "exp": int, "weekly_count": int}
    """
    row_bg = ME_ROW_COLOR if is_me else ROW_COLOR
    draw.rounded_rectangle([24, y, WIDTH - 24, y + ROW_H], radius=12, fill=row_bg)
    if is_me:
        draw.rounded_rectangle([24, y, 28, y + ROW_H], radius=2, fill=ACCENT)

    pad_x = 20
    cy = y + ROW_H // 2

    # ---- 순위 숫자 ----
    rank = entry["rank"]
    rank_str = f"{rank}" if rank else "-"
    rank_color = RANK_COLORS.get(rank, TEXT_MAIN)
    font_rank = load_font(24, bold=True)
    rw = draw.textlength(rank_str, font=font_rank)
    rank_col_w = 56
    draw.text((24 + pad_x + rank_col_w - rw, cy - 14), rank_str, font=font_rank, fill=rank_color)

    # ---- 아바타 ----
    avatar_size = 40
    ax = 24 + pad_x + rank_col_w + 16
    avatar = circle_image(entry.get("avatar_bytes"), avatar_size)
    img.paste(avatar, (ax, y + (ROW_H - avatar_size) // 2), avatar)

    # ---- 이름 (+나) ----
    name_x = ax + avatar_size + 16
    name_text = entry["name"] + ("  (나)" if is_me else "")
    stat_col_w = 230   # 우측 "Lv / EXP" 영역
    right_col_w = 150  # 우측 "주간 채팅" 영역
    name_max_w = WIDTH - 24 - pad_x - right_col_w - stat_col_w - name_x - 20
    font_name, fitted_name = fit_font_and_text(
        draw, name_text, name_max_w, base_size=22, bold=True, min_size=15
    )
    draw.text((name_x, cy - 14), fitted_name, font=font_name, fill=ACCENT if is_me else TEXT_MAIN)

    # ---- Lv / EXP ----
    font_sub = load_font(15)
    stat_x = WIDTH - 24 - pad_x - right_col_w - stat_col_w
    lv_text = f"Lv.{entry['level']}"
    exp_text = f"{entry['exp']:,} EXP"
    draw.text((stat_x, cy - 16), lv_text, font=load_font(18, bold=True), fill=TEXT_MAIN)
    draw.text((stat_x, cy + 4), exp_text, font=font_sub, fill=TEXT_SUB)

    # ---- 주간 채팅수 ----
    count_str = f"{entry['weekly_count']:,}"
    font_count = load_font(24, bold=True)
    cw = draw.textlength(count_str, font=font_count)
    right_x = WIDTH - 24 - pad_x
    draw.text((right_x - cw, cy - 18), count_str, font=font_count, fill=TEXT_MAIN)
    label = "주간 채팅"
    lw = draw.textlength(label, font=font_sub)
    draw.text((right_x - lw, cy + 6), label, font=font_sub, fill=TEXT_SUB)


def generate_leaderboard_card(
    guild_name: str | None,
    guild_icon_bytes: bytes | None,
    top_entries: list,   # 위 _draw_row entry 형식의 dict 리스트 (최대 10개, is_me 포함 가능)
    my_entry: dict | None = None,   # top_entries 안에 없을 때만 하단에 별도로 그려짐
    my_in_top: bool = False,
) -> io.BytesIO:
    show_separate_me = (my_entry is not None) and (not my_in_top)

    n_rows = len(top_entries)
    height = HEADER_H + TOP_PAD + n_rows * (ROW_H + ROW_GAP) + BOTTOM_PAD
    if show_separate_me:
        height += DIVIDER_H + ROW_H + ROW_GAP

    img = Image.new("RGB", (WIDTH, height), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([(0, 0), (WIDTH - 1, height - 1)], radius=24, fill=CARD_COLOR)

    # ---- 헤더: 서버 아이콘 + 이름 ----
    draw.rounded_rectangle([(0, 0), (WIDTH - 1, HEADER_H)], radius=24, fill=HEADER_COLOR)
    draw.rectangle([(0, HEADER_H - 20), (WIDTH - 1, HEADER_H)], fill=HEADER_COLOR)

    header_icon_size = 28
    header_x = 24
    g_icon = circle_image(guild_icon_bytes, header_icon_size)
    img.paste(g_icon, (header_x, (HEADER_H - header_icon_size) // 2), g_icon)
    text_start = header_x + header_icon_size + 12

    title = f"{guild_name} 주간 채팅 랭킹" if guild_name else "주간 채팅 랭킹"
    font_header = load_font(18, bold=True)
    _, fitted_title = fit_font_and_text(
        draw, title, WIDTH - text_start - 24, 18, bold=True, min_size=14
    )
    draw.text((text_start, (HEADER_H - 22) // 2), fitted_title, font=font_header, fill=TEXT_MAIN)

    # ---- TOP 10 ----
    y = HEADER_H + TOP_PAD
    for entry in top_entries:
        _draw_row(img, draw, y, entry, is_me=entry.get("is_me", False))
        y += ROW_H + ROW_GAP

    # ---- 내 순위 (TOP10 밖일 때만 별도 표시) ----
    if show_separate_me:
        dots_font = load_font(20, bold=True)
        dw = draw.textlength("· · ·", font=dots_font)
        draw.text(((WIDTH - dw) / 2, y + (DIVIDER_H - 22) / 2), "· · ·",
                   font=dots_font, fill=TEXT_SUB)
        y += DIVIDER_H
        _draw_row(img, draw, y, my_entry, is_me=True)
        y += ROW_H + ROW_GAP

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
