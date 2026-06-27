"""Estilos CSS de la aplicación principal."""

from gi.repository import Gtk

from soundwave.library.config.config import load_settings

HOVER_COLORS = {
    "#1DB954": "#1ED760",
    "#3584e4": "#4a90e2",
    "#9141ac": "#a352be",
    "#e01b24": "#ec2f38",
    "#ff7800": "#ff8c1a",
    "#f6d32d": "#f8dc4b",
    "#16a085": "#1abc9c",
    "#e01b84": "#eb2f96",
    "#777777": "#888888",
}

APP_CSS_TEMPLATE = """
        @define-color accent_bg_color ACCENT_HEX_PLACEHOLDER;
        @define-color accent_color ACCENT_HEX_PLACEHOLDER;
        @define-color accent_fg_color #ffffff;
        @define-color accent_hover_color ACCENT_HOVER_PLACEHOLDER;
        @define-color accent_shadow_30 ACCENT_SHADOW_30_PLACEHOLDER;
        @define-color accent_shadow_40 ACCENT_SHADOW_40_PLACEHOLDER;
        @define-color accent_shadow_45 ACCENT_SHADOW_45_PLACEHOLDER;

        .navigation-sidebar {
            background-color: @view_bg_color;
            border-right: 1px solid @borders;
        }
        .navigation-sidebar headerbar {
            background: none;
            background-color: transparent;
            border-bottom: none;
            box-shadow: none;
        }
        .sidebar-row {
            border-radius: 6px;
            margin: 2px 8px;
            padding: 8px 12px;
            transition: all 0.2s ease;
        }
        .sidebar-row:hover {
            background-color: alpha(currentColor, 0.05);
        }
        .sidebar-row:selected {
            background-color: alpha(@accent_bg_color, 0.12);
            color: @accent_bg_color;
            font-weight: bold;
        }
        .sidebar-row:selected label,
        .sidebar-row:selected image {
            color: @accent_bg_color;
        }
        .sidebar-row:selected .dim-label {
            color: alpha(@accent_bg_color, 0.7);
        }
        .player-bar {
            background-color: @window_bg_color;
            border-top: 1px solid @borders;
            padding: 10px 16px;
        }
        .album-grid, .artist-grid {
            margin: 16px;
        }
        .album-grid flowboxchild, .artist-grid flowboxchild {
            padding: 8px;
            border-radius: 12px;
            transition: all 0.2s ease;
        }
        .album-grid flowboxchild:hover, .artist-grid flowboxchild:hover {
            background-color: alpha(@accent_bg_color, 0.04);
        }
        .album-card, .artist-card {
            padding: 8px;
            background-color: transparent;
        }
        .album-card avatar, .artist-card avatar {
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            border-radius: 9999px;
        }
        .album-card:hover avatar, .artist-card:hover avatar {
            transform: scale(1.04);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.45);
        }
        .album-cover-container, .album-fallback-square {
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            border-radius: 8px;
        }
        .album-card:hover .album-cover-container, .album-card:hover .album-fallback-square {
            transform: scale(1.04);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.45);
        }
        .album-card-title, .artist-card-name {
            font-weight: bold;
            font-size: 13px;
            margin-top: 4px;
        }
        .album-card-subtitle, .artist-card-subtitle {
            font-size: 11px;
            color: alpha(currentColor, 0.6);
        }
        .album-play-btn {
            background-color: @accent_bg_color;
            color: #000000;
            border-radius: 99px;
            border: none;
            opacity: 0.0;
            transition: opacity 0.2s ease, transform 0.2s ease, background-color 0.2s ease;
        }
        .album-card:hover .album-play-btn {
            opacity: 1.0;
        }
        .album-play-btn:hover {
            background-color: @accent_hover_color;
            transform: scale(1.1);
        }
        .genres-grid {
            margin: 16px;
        }
        .genres-grid flowboxchild {
            padding: 0px;
            background: none;
            border-radius: 12px;
        }
        .genre-card {
            border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.15);
            transition: all 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
        }
        .genre-card:hover {
            transform: translateY(-4px) scale(1.02);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.25);
        }
        .genre-card-bg-icon {
            opacity: 0.15;
            color: #ffffff;
            margin-right: -10px;
            margin-bottom: -10px;
            transition: all 0.25s ease;
        }
        .genre-card:hover .genre-card-bg-icon {
            transform: scale(1.15) rotate(-10deg);
            opacity: 0.25;
        }
        .genre-card-name {
            font-weight: 800;
            font-size: 16px;
            color: #ffffff;
            text-shadow: 0 1px 3px rgba(0,0,0,0.3);
        }
        .genre-card-count {
            font-size: 12px;
            color: rgba(255, 255, 255, 0.8);
            font-weight: 500;
            text-shadow: 0 1px 2px rgba(0,0,0,0.3);
        }
        .genre-card-grad-0 {
            background: linear-gradient(135deg, #FF512F, #DD2476);
        }
        .genre-card-grad-1 {
            background: linear-gradient(135deg, #185a9d, #3cba92);
        }
        .genre-card-grad-2 {
            background: linear-gradient(135deg, #ee0979, #ff6a00);
        }
        .genre-card-grad-3 {
            background: linear-gradient(135deg, #11998e, #38ef7d);
        }
        .genre-card-grad-4 {
            background: linear-gradient(135deg, #8A2387, #E94057, #F27121);
        }
        .genre-card-grad-5 {
            background: linear-gradient(135deg, #DA22FF, #9733EE);
        }
        .genre-card-grad-6 {
            background: linear-gradient(135deg, #1f4037, #99f2c8);
        }
        .genre-card-grad-7 {
            background: linear-gradient(135deg, #00c6ff, #0072ff);
        }
        .genre-card-no-genre {
            background: linear-gradient(135deg, #757F9A, #D7DDE8);
        }
        .genre-card-no-genre .genre-card-name, .genre-card-no-genre .genre-card-count {
            color: #2c3e50;
            text-shadow: none;
        }
        .genre-card-no-genre .genre-card-bg-icon {
            color: #2c3e50;
            opacity: 0.12;
        }
        .smart-grid {
            margin: 16px;
        }
        .smart-grid flowboxchild {
            padding: 0px;
            background: none;
            border-radius: 12px;
        }
        .smart-card {
            border-radius: 12px;
            background-color: @card_bg_color;
            transition: all 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
        }
        .smart-card:hover {
            transform: translateY(-4px) scale(1.02);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
            background-color: alpha(@accent_bg_color, 0.04);
        }
        .smart-icon-container {
            border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
            color: #ffffff;
        }
        .smart-card-title {
            font-weight: 800;
            font-size: 15px;
            margin-top: 4px;
        }
        .smart-card-subtitle {
            font-size: 12px;
            color: alpha(currentColor, 0.55);
            font-weight: 500;
        }
        .smart-play-btn {
            background-color: @accent_bg_color;
            color: #000000;
            border-radius: 99px;
            border: none;
            opacity: 0.0;
            transition: opacity 0.2s ease, transform 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
        }
        .smart-card:hover .smart-play-btn {
            opacity: 1.0;
            transform: translateY(-4px);
        }
        .smart-play-btn:hover {
            background-color: @accent_hover_color;
            transform: translateY(-4px) scale(1.1);
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.4);
        }
        .smart-icon-recien-anadido {
            background: linear-gradient(135deg, #f093fb, #f5576c);
        }
        .smart-icon-favoritos {
            background: linear-gradient(135deg, #ff0844, #ffb199);
        }
        .smart-icon-mas-escuchadas {
            background: linear-gradient(135deg, #667eea, #764ba2);
        }
        .smart-icon-jazz {
            background: linear-gradient(135deg, #13f1fc, #0470dc);
        }
        .smart-icon-rock {
            background: linear-gradient(135deg, #434343, #000000);
        }
        .smart-icon-electronica {
            background: linear-gradient(135deg, #0ba360, #3cba92);
        }
        .playlists-grid {
            margin: 16px;
        }
        .playlists-grid flowboxchild {
            padding: 0px;
            background: none;
            border-radius: 12px;
        }
        .playlist-card {
            border-radius: 12px;
            background-color: @card_bg_color;
            transition: all 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
        }
        .playlist-card:hover {
            transform: translateY(-4px) scale(1.02);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
            background-color: alpha(@accent_bg_color, 0.04);
        }
        .playlist-icon-container {
            border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
            color: #ffffff;
        }
        .playlist-card-title {
            font-weight: 800;
            font-size: 15px;
            margin-top: 4px;
        }
        .playlist-card-subtitle {
            font-size: 12px;
            color: alpha(currentColor, 0.55);
            font-weight: 500;
        }
        .playlist-play-btn {
            background-color: @accent_bg_color;
            color: #000000;
            border-radius: 99px;
            border: none;
            opacity: 0.0;
            transition: opacity 0.2s ease, transform 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
        }
        .playlist-delete-btn {
            background-color: alpha(#ff3b30, 0.1);
            color: #ff3b30;
            border-radius: 99px;
            border: none;
            opacity: 0.0;
            transition: opacity 0.2s ease, transform 0.2s ease, background-color 0.2s ease;
        }
        .playlist-delete-btn:hover {
            background-color: #ff3b30;
            color: #ffffff;
        }
        .playlist-card:hover .playlist-play-btn, 
        .playlist-card:hover .playlist-delete-btn {
            opacity: 1.0;
            transform: translateY(-4px);
        }
        .playlist-play-btn:hover {
            background-color: @accent_hover_color;
            transform: translateY(-4px) scale(1.1);
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.4);
        }
        .playlist-icon-grad-0 {
            background: linear-gradient(135deg, #FF5E36, #FFAE33);
        }
        .playlist-icon-grad-1 {
            background: linear-gradient(135deg, #FF2A6D, #9B51E0);
        }
        .playlist-icon-grad-2 {
            background: linear-gradient(135deg, #0575E6, #00F260);
        }
        .playlist-icon-grad-3 {
            background: linear-gradient(135deg, #7F00FF, #E100FF);
        }
        .playlist-icon-grad-4 {
            background: linear-gradient(135deg, #f857a6, #ff5858);
        }
        .playlist-icon-grad-5 {
            background: linear-gradient(135deg, #11998e, #38ef7d);
        }
        .playlist-icon-grad-6 {
            background: linear-gradient(135deg, #4A00E0, #8E2DE2);
        }
        .playlist-icon-grad-7 {
            background: linear-gradient(135deg, #ED213A, #93291E);
        }
        .song-fav-active {
            color: #e02424;
            opacity: 1.0;
            background: none;
            border: none;
            box-shadow: none;
        }
        .song-fav-inactive {
            color: alpha(currentColor, 0.3);
            opacity: 0.6;
            background: none;
            border: none;
            box-shadow: none;
        }
        .song-fav-inactive:hover {
            color: alpha(#e02424, 0.7);
            opacity: 0.9;
        }
        .song-row {
            border-radius: 8px;
            padding: 8px 16px;
            margin: 2px 8px;
            transition: background-color 0.2s ease;
        }
        .song-row:hover {
            background-color: alpha(@accent_bg_color, 0.04);
        }
        .song-row:selected {
            background-color: alpha(@accent_bg_color, 0.15);
            color: @window_fg_color;
        }
        .song-row:selected label {
            color: @window_fg_color;
        }
        .song-row:selected label.subtitle {
            color: alpha(@window_fg_color, 0.6);
        }
        .equalizer-slider {
            min-height: 120px;
        }
        .volume-button {
            min-width: 32px;
        }
        .play-button-main {
            background-color: @accent_bg_color;
            color: #000000;
            border-radius: 50%;
            box-shadow: 0 4px 14px @accent_shadow_30;
            transition: all 0.2s ease;
            padding: 0;
        }
        .play-button-main:hover {
            transform: scale(1.08);
            background-color: @accent_hover_color;
            box-shadow: 0 6px 20px @accent_shadow_45;
        }
        .green-deck-btn {
            background-color: @accent_bg_color;
            color: #000000;
            border-radius: 50%;
            box-shadow: 0 4px 14px @accent_shadow_30;
            transition: all 0.2s ease;
        }
        .green-deck-btn:hover {
            transform: scale(1.08);
            background-color: @accent_hover_color;
        }
        .now-playing-row {
            border-left: 3px solid @accent_bg_color;
            background-color: alpha(@accent_bg_color, 0.06);
        }
        /* General Gtk.Scale overrides */
        scale trough {
            border: none;
            box-shadow: none;
            outline: none;
        }
        scale highlight {
            background-color: @accent_bg_color;
            border: none;
            box-shadow: none;
            outline: none;
        }
        scale slider {
            background-color: @accent_bg_color;
            border: none;
            box-shadow: 0 2px 6px @accent_shadow_40;
            outline: none;
        }

        /* Specific orientation styling */
        scale.horizontal trough {
            min-height: 4px;
            border-radius: 2px;
            background-color: alpha(currentColor, 0.12);
        }
        scale.horizontal highlight {
            min-height: 4px;
            border-radius: 2px;
        }
        scale.horizontal slider {
            min-height: 14px;
            min-width: 14px;
            border-radius: 50%;
        }
        scale.vertical trough {
            min-width: 4px;
            border-radius: 2px;
            background-color: alpha(currentColor, 0.12);
        }
        scale.vertical highlight {
            min-width: 4px;
            border-radius: 2px;
        }
        scale.vertical slider {
            min-height: 14px;
            min-width: 14px;
            border-radius: 50%;
        }

        /* Equalizer sliders specific overrides */
        .equalizer-slider trough {
            min-width: 4px;
            border-radius: 2px;
            background-color: alpha(currentColor, 0.12);
            border: none;
            box-shadow: none;
            outline: none;
        }
        .equalizer-slider highlight {
            min-width: 4px;
            border-radius: 2px;
            background-color: @accent_bg_color;
            border: none;
            box-shadow: none;
            outline: none;
        }
        .equalizer-slider slider {
            min-height: 14px;
            min-width: 14px;
            border-radius: 50%;
            background-color: @accent_bg_color;
            border: none;
            box-shadow: 0 2px 6px @accent_shadow_40;
            outline: none;
        }

        /* General Gtk.Switch overrides */
        switch {
            border: none;
            outline: none;
            box-shadow: none;
        }
        switch trough {
            border: none;
            outline: none;
            box-shadow: none;
        }
        switch:checked {
            background-color: @accent_bg_color;
            border-color: @accent_bg_color;
        }
        switch:checked trough {
            background-color: @accent_bg_color;
            border-color: @accent_bg_color;
            border: none;
            box-shadow: none;
            outline: none;
        }
        switch slider {
            border: none;
            box-shadow: none;
            outline: none;
        }
        switch:checked slider {
            border: none;
            box-shadow: none;
            outline: none;
        }

        /* Suggested action buttons */
        button.suggested-action {
            background-color: @accent_bg_color;
            color: @accent_fg_color;
            border: none;
            outline: none;
            box-shadow: none;
        }
        button.suggested-action:hover {
            background-color: @accent_hover_color;
            border: none;
            outline: none;
            box-shadow: none;
        }
        .album-cover {
            border-radius: 6px;
        }
        .player-bar .album-cover {
            min-width: 56px;
            min-height: 56px;
        }
        .visualizer-art {
            min-width: 300px;
            min-height: 300px;
        }
        .green-deck-header {
            background-color: @window_bg_color;
            border-bottom: 1px solid @borders;
        }
        .songs-list > row {
            border-radius: 8px;
            padding: 4px 12px;
            margin: 1px 8px;
            transition: background-color 0.15s ease;
        }
        .songs-list > row:hover {
            background-color: alpha(@accent_bg_color, 0.04);
        }
        .songs-list > row:selected {
            background-color: alpha(@accent_bg_color, 0.15);
            color: @window_fg_color;
        }
        .songs-list > row:selected label {
            color: @window_fg_color;
        }
        .songs-list > row:selected label.subtitle {
            color: alpha(@window_fg_color, 0.6);
        }
        .lyrics-line {
            font-size: 16px;
            padding: 4px 0;
            transition: all 0.3s ease;
        }
        .lyrics-line-inactive {
            color: alpha(@window_fg_color, 0.35);
        }
        .lyrics-line-active {
            color: @accent_bg_color;
            font-weight: bold;
            font-size: 18px;
        }
        .album-details-header {
            padding: 16px 0;
            border-bottom: 1px solid alpha(currentColor, 0.08);
            margin-bottom: 16px;
        }
        .album-details-type {
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 1px;
            color: alpha(currentColor, 0.6);
        }
        .album-details-title {
            font-size: 32px;
            font-weight: 800;
            margin: 4px 0;
            line-height: 1.2;
        }
        .album-details-artist {
            font-size: 16px;
            font-weight: bold;
            color: @accent_bg_color;
        }
        .album-details-meta {
            font-size: 13px;
            color: alpha(currentColor, 0.55);
            margin-top: 4px;
        }
        .audio-info-label {
            font-size: 10px;
            color: alpha(currentColor, 0.5);
            font-weight: bold;
            margin-top: 2px;
            margin-bottom: 2px;
        }
"""


def get_accent_colors(accent_hex: str | None = None) -> tuple[str, str, str, str, str]:
    if accent_hex is None:
        settings = load_settings()
        accent_hex = settings.get("accent_color", "#1DB954")

    hover_hex = HOVER_COLORS.get(accent_hex, accent_hex)
    hex_clean = accent_hex.lstrip("#")
    r = int(hex_clean[0:2], 16)
    g = int(hex_clean[2:4], 16)
    b = int(hex_clean[4:6], 16)
    shadow_30 = f"rgba({r}, {g}, {b}, 0.3)"
    shadow_40 = f"rgba({r}, {g}, {b}, 0.4)"
    shadow_45 = f"rgba({r}, {g}, {b}, 0.45)"
    return accent_hex, hover_hex, shadow_30, shadow_40, shadow_45


def build_app_css(accent_hex: str | None = None) -> str:
    accent_hex, hover_hex, shadow_30, shadow_40, shadow_45 = get_accent_colors(accent_hex)
    css = APP_CSS_TEMPLATE
    css = css.replace("ACCENT_HEX_PLACEHOLDER", accent_hex)
    css = css.replace("ACCENT_HOVER_PLACEHOLDER", hover_hex)
    css = css.replace("ACCENT_SHADOW_30_PLACEHOLDER", shadow_30)
    css = css.replace("ACCENT_SHADOW_40_PLACEHOLDER", shadow_40)
    css = css.replace("ACCENT_SHADOW_45_PLACEHOLDER", shadow_45)
    return css


def setup_window_css(window, css_provider: Gtk.CssProvider | None = None) -> Gtk.CssProvider:
    if css_provider is None:
        css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            window.get_display(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER,
        )
    css_provider.load_from_string(build_app_css())
    return css_provider
