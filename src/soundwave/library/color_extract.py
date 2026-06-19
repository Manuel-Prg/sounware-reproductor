import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

from collections import Counter
from pathlib import Path
from typing import Optional


def extract_dominant_colors(
    image_path: Path,
    num_colors: int = 3,
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

        color_weights: Counter = Counter()

        for y in range(height):
            row_start = y * rowstride
            for x in range(width):
                idx = row_start + x * n_channels
                r = pixels[idx]
                g = pixels[idx + 1]
                b = pixels[idx + 2]

                # Finer quantization (16 instead of 32) for richer color bins
                rq = (r // 16) * 16
                gq = (g // 16) * 16
                bq = (b // 16) * 16

                # Calculate vibrancy (difference between max and min color channels)
                max_c = max(r, g, b)
                min_c = min(r, g, b)
                vibrancy = max_c - min_c

                # Weight: more vibrant/saturated colors get higher precedence
                weight = vibrancy + 1.0

                # De-prioritize pure black or pure white backgrounds (often letterboxing/borders)
                if max_c < 45 or min_c > 210:
                    weight = 0.1

                color_weights[(rq, gq, bq)] += weight

        return [color for color, _ in color_weights.most_common(num_colors)]
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

            # Search for a distinct accent color from the extracted colors
            accent_rgb = None
            for candidate in colors[1:]:
                # Calculate color distance (difference)
                dist = sum(abs(c1 - c2) for c1, c2 in zip(colors[0], candidate))
                if dist > 60:  # visually distinct
                    accent_rgb = candidate
                    break

            if accent_rgb is None and len(colors) >= 2:
                accent_rgb = colors[1]

            if accent_rgb:
                ar, ag, ab = accent_rgb
            else:
                # Fallback to a slightly brighter/shifted variant of the dominant color
                ar = min(255, r + 40)
                ag = min(255, g + 40)
                ab = min(255, b + 40)

            accent_hex = rgb_to_hex(ar, ag, ab)

    return bg_hex, accent_hex, fg_hex
