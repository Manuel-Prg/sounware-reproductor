import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

_MINI_PLAYER_CSS_PRIORITY = Gtk.STYLE_PROVIDER_PRIORITY_USER


def load_base_css(display):
    css = """
    window.background.mini-player-window,
    window.csd.mini-player-window,
    window.mini-player-window,
    window.mini-player-window > decoration,
    window.mini-player-window windowhandle,
    .mini-player-window,
    .mini-player-window.background,
    .mini-player-window > contents,
    .mini-player-window > decoration,
    .mini-player-window windowhandle,
    .mini-player-handle {
        background-color: transparent;
        background-image: none;
        background: transparent;
        box-shadow: none;
        border: none;
    }
    .mini-player {
        background-color: @window_bg_color;
        background-image: linear-gradient(135deg, @window_bg_color, mix(@window_bg_color, @window_fg_color, 0.06));
        border-radius: 16px;
        border: 1px solid alpha(currentColor, 0.08);
        transition: background-color 0.6s ease;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
    }
    .mini-player-repeat-active {
        color: @accent_bg_color;
        opacity: 1.0;
    }
    .mini-player-repeat-inactive {
        color: alpha(currentColor, 0.45);
        opacity: 0.6;
    }
    .mini-player-art {
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
        width: 116px;
        height: 116px;
    }
    .mini-player-title {
        font-weight: 800;
        font-size: 15px;
        transition: color 0.6s ease;
    }
    .mini-player-artist {
        font-size: 12px;
        font-weight: 500;
        transition: color 0.6s ease;
    }
    .mini-player-time {
        font-size: 11px;
        font-weight: bold;
        transition: color 0.6s ease;
    }
    .mini-player-win-btn {
        opacity: 0.5;
        min-width: 24px;
        min-height: 24px;
        padding: 0;
        transition: opacity 0.2s ease, color 0.6s ease;
    }
    .mini-player-win-btn:hover {
        opacity: 1.0;
    }
    .mini-player-ctrl-btn {
        opacity: 0.85;
        min-width: 32px;
        min-height: 32px;
        padding: 0;
        transition: opacity 0.2s ease, color 0.6s ease, transform 0.2s ease;
    }
    .mini-player-ctrl-btn:hover {
        opacity: 1.0;
        transform: scale(1.08);
    }
    .mini-player-play-btn {
        background-color: @accent_bg_color;
        color: #000000;
        border-radius: 50%;
        min-width: 38px;
        min-height: 38px;
        padding: 0;
        box-shadow: 0 3px 10px rgba(0, 0, 0, 0.2);
        transition: background-color 0.6s ease, color 0.6s ease, transform 0.2s ease;
    }
    .mini-player-play-btn:hover {
        transform: scale(1.08);
    }
    .mini-player-scale trough {
        min-height: 4px;
        border-radius: 2px;
        background-color: alpha(currentColor, 0.15);
        transition: background-color 0.6s ease;
        border: none;
        outline: none;
        box-shadow: none;
    }
    .mini-player-scale highlight {
        min-height: 4px;
        border-radius: 2px;
        background-color: @accent_bg_color;
        transition: background-color 0.6s ease;
        border: none;
        outline: none;
        box-shadow: none;
    }
    .mini-player-scale slider {
        min-height: 10px;
        min-width: 10px;
        border-radius: 50%;
        background-color: @accent_bg_color;
        box-shadow: none;
        border: none;
        outline: none;
        transition: background-color 0.6s ease;
    }
    """
    provider = Gtk.CssProvider()
    provider.load_from_string(css)
    Gtk.StyleContext.add_provider_for_display(
        display,
        provider,
        _MINI_PLAYER_CSS_PRIORITY
    )


def update_theme_css(display, theme_provider, bg_hex: str, accent_hex: str, fg_hex: str):
    try:
        r = int(bg_hex[1:3], 16)
        g = int(bg_hex[3:5], 16)
        b = int(bg_hex[5:7], 16)
        ar = int(accent_hex[1:3], 16)
        ag = int(accent_hex[3:5], 16)
        ab = int(accent_hex[5:7], 16)
    except Exception:
        r, g, b = 29, 185, 84
        ar, ag, ab = 30, 215, 96

    # Gradient target is 75% dominant mixed with 25% accent, then deepened (80% brightness)
    r2 = max(0, int((r * 0.75 + ar * 0.25) * 0.80))
    g2 = max(0, int((g * 0.75 + ag * 0.25) * 0.80))
    b2 = max(0, int((b * 0.75 + ab * 0.25) * 0.80))
    color2_hex = f"#{r2:02x}{g2:02x}{b2:02x}"

    css = f"""
    .mini-player {{
        background-color: {bg_hex};
        background-image: linear-gradient(135deg, {bg_hex}, {color2_hex});
    }}
    .mini-player-title {{
        color: {fg_hex};
    }}
    .mini-player-artist {{
        color: alpha({fg_hex}, 0.75);
    }}
    .mini-player-time {{
        color: alpha({fg_hex}, 0.7);
    }}
    .mini-player-win-btn {{
        color: alpha({fg_hex}, 0.6);
    }}
    .mini-player-win-btn:hover {{
        color: {fg_hex};
    }}
    .mini-player-ctrl-btn {{
        color: alpha({fg_hex}, 0.85);
    }}
    .mini-player-ctrl-btn:hover {{
        color: {fg_hex};
    }}
    .mini-player-play-btn {{
        background-color: {accent_hex};
        color: {bg_hex};
    }}
    .mini-player-scale trough {{
        background-color: alpha({fg_hex}, 0.18);
        border: none;
        outline: none;
        box-shadow: none;
    }}
    .mini-player-scale highlight {{
        background-color: {accent_hex};
        border: none;
        outline: none;
        box-shadow: none;
    }}
    .mini-player-scale slider {{
        background-color: {accent_hex};
        box-shadow: none;
        border: none;
        outline: none;
    }}
    .mini-player-repeat-active {{
        color: {accent_hex};
        opacity: 1.0;
    }}
    .mini-player-repeat-inactive {{
        color: alpha({fg_hex}, 0.45);
        opacity: 0.6;
    }}
    """
    theme_provider.load_from_string(css)
    Gtk.StyleContext.add_provider_for_display(
        display,
        theme_provider,
        _MINI_PLAYER_CSS_PRIORITY
    )


def reset_theme(display, theme_provider):
    css = """
    .mini-player {
        background-color: @window_bg_color;
        background-image: linear-gradient(135deg, @window_bg_color, mix(@window_bg_color, @window_fg_color, 0.06));
    }
    .mini-player-title {
        color: @window_fg_color;
    }
    .mini-player-artist {
        color: alpha(@window_fg_color, 0.75);
    }
    .mini-player-time {
        color: alpha(@window_fg_color, 0.7);
    }
    .mini-player-win-btn {
        color: alpha(@window_fg_color, 0.6);
    }
    .mini-player-win-btn:hover {
        color: @window_fg_color;
    }
    .mini-player-ctrl-btn {
        color: alpha(@window_fg_color, 0.85);
    }
    .mini-player-ctrl-btn:hover {
        color: @window_fg_color;
    }
    .mini-player-play-btn {
        background-color: @accent_bg_color;
        color: @accent_fg_color;
    }
    .mini-player-scale trough {
        background-color: alpha(currentColor, 0.15);
        border: none;
        outline: none;
        box-shadow: none;
    }
    .mini-player-scale highlight {
        background-color: @accent_bg_color;
        border: none;
        outline: none;
        box-shadow: none;
    }
    .mini-player-scale slider {
        background-color: @accent_bg_color;
        box-shadow: none;
        border: none;
        outline: none;
    }
    .mini-player-repeat-active {
        color: @accent_bg_color;
        opacity: 1.0;
    }
    .mini-player-repeat-inactive {
        color: alpha(@window_fg_color, 0.45);
        opacity: 0.6;
    }
    """
    theme_provider.load_from_string(css)
    Gtk.StyleContext.add_provider_for_display(
        display,
        theme_provider,
        _MINI_PLAYER_CSS_PRIORITY
    )
