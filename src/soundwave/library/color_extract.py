import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

from collections import Counter
from pathlib import Path
from typing import Optional


def extract_dominant_colors(
    image_path: Path,
    num_colors: int = 2,
    sample_size: int = 64
) -> list[tuple[int, int, int]]:
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(image_path))
        scaled = pixbuf.scale_simple(
            sample_size, sample_size,
            GdkPixbuf.InterpType.BILINEAR
        )

        pixels = scaled.get_pixels()
        width = scaled.get_width()
        height = scaled.get_height()
        rowstride = scaled.get_rowstride()
        n_channels = scaled.get_n_channels()

        color_counts: Counter = Counter()

        for y in range(height):
            row_start = y * rowstride
            for x in range(width):
                idx = row_start + x * n_channels
                r = pixels[idx]
                g = pixels[idx + 1]
                b = pixels[idx + 2]

                rq = (r // 32) * 32
                gq = (g // 32) * 32
                bq = (b // 32) * 32
                color_counts[(rq, gq, bq)] += 1

        return [color for color, _ in color_counts.most_common(num_colors)]
    except Exception:
        return [(29, 185, 84)]


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def is_light_color(r: int, g: int, b: int) -> bool:
    return (0.299 * r + 0.587 * g + 0.114 * b) > 128


def get_theme_colors_from_art(
    art_path: Optional[Path]
) -> tuple[str, str, str]:
    bg_hex = "#1DB954"
    accent_hex = "#1ED760"
    fg_hex = "#000000"

    if art_path and art_path.exists():
        colors = extract_dominant_colors(art_path, num_colors=3)
        if colors:
            r, g, b = colors[0]
            bg_hex = rgb_to_hex(r, g, b)
            fg_hex = "#ffffff" if not is_light_color(r, g, b) else "#000000"

            if len(colors) >= 2:
                ar, ag, ab = colors[1]
            else:
                ar = min(255, r + 40)
                ag = min(255, g + 40)
                ab = min(255, b + 40)
            accent_hex = rgb_to_hex(ar, ag, ab)

    return bg_hex, accent_hex, fg_hex
