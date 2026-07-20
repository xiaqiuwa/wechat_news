from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def create_daily_cover(path: Path, run_at: datetime) -> Path:
    width, height = 900, 383
    image = Image.new("RGB", (width, height), "#081A33")
    pixels = image.load()
    for y in range(height):
        ratio = y / max(1, height - 1)
        for x in range(width):
            blue = int(44 + 55 * (x / width))
            red = int(8 + 18 * ratio)
            green = int(26 + 35 * ratio)
            pixels[x, y] = (red, green, blue)

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((55, 54, 250, 103), radius=24, fill="#2D7FF9")
    draw.text((80, 65), "DAILY NEWS", font=_font(22), fill="white")
    draw.text((55, 135), "今日要闻", font=_font(72), fill="white")
    draw.text((58, 245), run_at.strftime("%Y · %m · %d"), font=_font(30), fill="#B9D4FF")
    draw.text((58, 305), "国内与国际重大新闻速览", font=_font(27), fill="#DDEBFF")
    draw.ellipse((742, 78, 1018, 354), outline="#2D7FF9", width=8)
    draw.ellipse((790, 126, 972, 308), outline="#74A9FF", width=3)

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=88, optimize=True)
    return path

