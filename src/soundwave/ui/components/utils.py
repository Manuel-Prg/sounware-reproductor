import math
from typing import Optional


def hex_to_rgb(hex_str: str, default: tuple[float, float, float] = (0.48, 0.28, 0.98)) -> tuple[float, float, float]:
    try:
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 3:
            hex_str = ''.join([c*2 for c in hex_str])
        r = int(hex_str[0:2], 16) / 255.0
        g = int(hex_str[2:4], 16) / 255.0
        b = int(hex_str[4:6], 16) / 255.0
        return r, g, b
    except Exception:
        return default


def draw_rounded_rect(cr, x, y, w, h, r):
    if w <= 0 or h <= 0:
        return
    if r > w / 2.0:
        r = w / 2.0
    if r > h / 2.0:
        r = h / 2.0
    cr.new_sub_path()
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.arc(x + w - r, y + r, r, 1.5 * math.pi, 2 * math.pi)
    cr.arc(x + w - r, y + h - r, r, 0, 0.5 * math.pi)
    cr.arc(x + r, y + h - r, r, 0.5 * math.pi, math.pi)
    cr.close_path()


def format_time(ns: int) -> str:
    if ns <= 0:
        return "0:00"
    total_sec = int(ns / 1e9)
    m, s = divmod(total_sec, 60)
    return f"{m}:{s:02d}"


def clear_container(container) -> None:
    while True:
        child = container.get_first_child()
        if child:
            container.remove(child)
        else:
            break
