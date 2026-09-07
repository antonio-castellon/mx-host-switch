"""Generate the tray / executable icon."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def assets_dir() -> Path:
    path = project_root() / "assets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ico_path() -> Path:
    return assets_dir() / "icon.ico"


def png_path() -> Path:
    return assets_dir() / "icon.png"


def _draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = max(1, size // 16)
    # Dark rounded tile
    draw.rounded_rectangle(
        [margin, margin, size - margin - 1, size - margin - 1],
        radius=size // 5,
        fill=(18, 22, 28, 255),
        outline=(45, 212, 191, 255),
        width=max(1, size // 32),
    )
    # Mouse body
    body = [
        size * 0.30,
        size * 0.28,
        size * 0.70,
        size * 0.78,
    ]
    draw.rounded_rectangle(body, radius=size // 6, fill=(226, 232, 240, 255))
    # Center seam
    cx = size / 2
    draw.line([(cx, size * 0.34), (cx, size * 0.70)], fill=(18, 22, 28, 255), width=max(1, size // 32))
    # Scroll wheel
    wheel = [cx - size * 0.06, size * 0.36, cx + size * 0.06, size * 0.50]
    draw.ellipse(wheel, fill=(45, 212, 191, 255))
    # Three Easy-Switch dots
    r = max(1.2, size * 0.035)
    y = size * 0.86
    colors = [(45, 212, 191, 255), (148, 163, 184, 255), (148, 163, 184, 255)]
    xs = [size * 0.38, size * 0.50, size * 0.62]
    for x, color in zip(xs, colors):
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)
    return img


def render_tray_image(size: int = 64) -> Image.Image:
    return _draw_icon(size)


def write_assets() -> Path:
    png = render_tray_image(256)
    png.save(png_path(), format="PNG")
    png.save(ico_path(), format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)])
    return ico_path()
