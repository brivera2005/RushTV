"""Generate RushTV branded logo.png and icon.ico if missing."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BRAND_RED = "#E31E24"
BRAND_BG = "#0D0D0D"
BRAND_WHITE = "#FFFFFF"
BRAND_MUTED = "#6B6B6B"

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_logo(size: tuple[int, int] = (640, 360)) -> Image.Image:
    w, h = size
    img = Image.new("RGB", (w, h), BRAND_BG)
    draw = ImageDraw.Draw(img)

    # Speed lines
    for i, offset in enumerate(range(0, w, 48)):
        alpha = 180 - (i % 5) * 20
        color = (227, 30, 36) if i % 2 == 0 else (40, 40, 40)
        draw.line((offset, h // 2 - 40, offset + 80, h // 2 + 40), fill=color, width=3)

    # Stylized R
    cx, cy = int(w * 0.22), int(h * 0.42)
    r = int(min(w, h) * 0.14)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=BRAND_RED, width=6)
    draw.line((cx, cy - r + 8, cx, cy + r - 8), fill=BRAND_RED, width=8)
    draw.arc((cx - r + 10, cy - r // 2, cx + r - 4, cy + r // 2), 270, 90, fill=BRAND_RED, width=8)
    draw.line((cx, cy, cx + r - 6, cy + r - 10), fill=BRAND_RED, width=8)

    # Title
    title_font = _font(int(h * 0.14), bold=True)
    tag_font = _font(int(h * 0.05))
    draw.text((int(w * 0.38), int(h * 0.32)), "RUSHTV", fill=BRAND_RED, font=title_font)
    draw.text((int(w * 0.38), int(h * 0.52)), "LOCAL IPTV STREAMING", fill=BRAND_WHITE, font=tag_font)

    # Accent bar
    draw.rectangle((int(w * 0.38), int(h * 0.48), int(w * 0.82), int(h * 0.49)), fill=BRAND_RED)

    return img


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)

    logo_path = ASSETS / "logo.png"
    if not logo_path.exists():
        draw_logo().save(logo_path, "PNG")
        print(f"Created {logo_path}")

    icon_path = ASSETS / "icon.ico"
    if not icon_path.exists():
        logo = draw_logo((256, 256))
        logo.save(
            icon_path,
            format="ICO",
            sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
        )
        print(f"Created {icon_path}")


if __name__ == "__main__":
    main()
