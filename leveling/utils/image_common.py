"""
rank_card.py, leaderboard_card.py가 공용으로 쓰는 폰트/이미지 유틸 모음.
"""
import io
import os
from PIL import Image, ImageDraw, ImageFont, ImageOps

FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")


def load_font(size: int, bold: bool = False):
    """
    fonts/ 폴더에 넣어둔 한글 폰트를 우선 사용.
    (NanumGothic.ttf / NanumGothicBold.ttf 를 권장 - README 참고)
    없으면 시스템 기본 폰트로 대체하되, 한글이 깨질 수 있음을 감안해야 함.
    """
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

    # 폰트 파일이 없을 때의 폴백 (한글 미지원 가능성 있음)
    for fallback in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if os.path.exists(fallback):
            return ImageFont.truetype(fallback, size)
    return ImageFont.load_default()


def circle_image(image_bytes: bytes | None, size: int, fallback_color=(90, 93, 102), supersample: int = 4):
    """
    이미지를 원형으로 잘라서 반환. image_bytes가 None이면 단색 원(placeholder) 반환.
    실제 크기의 `supersample`배로 그린 뒤 LANCZOS로 축소해서 원 테두리 계단현상(jaggy)을 없앤다.
    """
    ss = size * supersample

    if image_bytes is None:
        big = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
        ImageDraw.Draw(big).ellipse((0, 0, ss - 1, ss - 1), fill=fallback_color)
        return big.resize((size, size), Image.LANCZOS)

    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img = ImageOps.fit(img, (ss, ss))
    mask = Image.new("L", (ss, ss), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, ss - 1, ss - 1), fill=255)
    img.putalpha(mask)
    return img.resize((size, size), Image.LANCZOS)


def draw_smooth_ring(base_img: Image.Image, bbox, color, width: int, supersample: int = 4):
    """
    base_img 위에 안티앨리어싱된 원형 테두리(링)를 그린다.
    bbox: (x0, y0, x1, y1) - 링이 차지할 사각 영역.
    """
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    ss_w, ss_h = w * supersample, h * supersample
    lw = width * supersample

    layer = Image.new("RGBA", (ss_w, ss_h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(
        [lw / 2, lw / 2, ss_w - lw / 2, ss_h - lw / 2], outline=color, width=lw
    )
    layer = layer.resize((w, h), Image.LANCZOS)
    base_img.paste(layer, (x0, y0), layer)


def fit_font_and_text(draw, text, max_width, base_size, bold=True, min_size=14):
    """
    글자가 max_width를 넘으면 폰트 크기를 줄여서 맞추고,
    최소 크기에서도 넘치면 말줄임표(…)로 잘라서 반환한다.
    """
    size = base_size
    font = load_font(size, bold=bold)
    while size > min_size and draw.textlength(text, font=font) > max_width:
        size -= 2
        font = load_font(size, bold=bold)

    if draw.textlength(text, font=font) <= max_width:
        return font, text

    # 최소 크기에서도 넘치면 말줄임표로 자르기
    truncated = text
    while len(truncated) > 1 and draw.textlength(truncated + "…", font=font) > max_width:
        truncated = truncated[:-1]
    return font, truncated + "…"
