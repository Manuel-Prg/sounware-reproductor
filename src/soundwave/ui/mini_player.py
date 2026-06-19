import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk, Pango

from pathlib import Path
from typing import Optional, Callable

from soundwave.player.engine import Player, PlayerState, RepeatMode, PlaybackPosition
from soundwave.library.database import Song
from soundwave.library.color_extract import get_theme_colors_from_art


RestoreWindowCallback = Callable[[], None]

_MINI_PLAYER_CSS_PRIORITY = Gtk.STYLE_PROVIDER_PRIORITY_USER


class MiniPlayer(Gtk.Window):
    def __init__(self, player: Player):
        super().__init__()
        self._player = player
        self._restore_cbs: list[RestoreWindowCallback] = []

        self.set_title("Soundwave")
        self.set_default_size(440, 140)
        self.set_resizable(False)
        self.set_decorated(False)
        self.add_css_class("mini-player-window")

        self._theme_provider = Gtk.CssProvider()

        self._build_ui()

        self._player.connect_state(self._on_state_changed)
        self._player.connect_song(self._on_song_changed)
        self._player.connect_position(self._on_position_changed)

    def _build_ui(self):
        # Main container with horizontal layout
        self._main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self._main_box.set_css_classes(["mini-player"])
        self._main_box.set_margin_start(12)
        self._main_box.set_margin_end(12)
        self._main_box.set_margin_top(12)
        self._main_box.set_margin_bottom(12)

        # Left Column: Cover Art
        art_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        art_box.set_valign(Gtk.Align.CENTER)

        self._art_image = Gtk.Picture()
        self._art_image.set_size_request(116, 116)
        self._art_image.set_content_fit(Gtk.ContentFit.COVER)
        self._art_image.set_css_classes(["mini-player-art"])
        art_box.append(self._art_image)
        self._main_box.append(art_box)

        # Right Column: Song metadata, playback controls, and timeline
        right_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        right_column.set_hexpand(True)
        right_column.set_valign(Gtk.Align.CENTER)

        # Top row: Title/Artist + Window Management (minimize, restore, close)
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info_box.set_hexpand(True)
        
        self._title_label = Gtk.Label(label="Soundwave")
        self._title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._title_label.set_xalign(0)
        self._title_label.set_css_classes(["mini-player-title"])
        
        self._artist_label = Gtk.Label(label="Sin reproducción")
        self._artist_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._artist_label.set_xalign(0)
        self._artist_label.set_css_classes(["mini-player-artist"])
        
        info_box.append(self._title_label)
        info_box.append(self._artist_label)
        top_row.append(info_box)

        # Compact Window controls
        win_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        win_controls.set_valign(Gtk.Align.START)
        
        restore_btn = Gtk.Button.new_from_icon_name("go-up-symbolic")
        restore_btn.set_css_classes(["flat", "circular", "mini-player-win-btn"])
        restore_btn.set_size_request(24, 24)
        restore_btn.set_tooltip_text("Restaurar ventana")
        restore_btn.connect("clicked", lambda b: self._emit_restore())
        win_controls.append(restore_btn)

        close_btn = Gtk.Button.new_from_icon_name("window-close-symbolic")
        close_btn.set_css_classes(["flat", "circular", "mini-player-win-btn"])
        close_btn.set_size_request(24, 24)
        close_btn.set_tooltip_text("Cerrar")
        close_btn.connect("clicked", lambda b: self._emit_restore())
        win_controls.append(close_btn)
        
        top_row.append(win_controls)
        right_column.append(top_row)

        # Media Control Buttons
        controls_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        controls_row.set_halign(Gtk.Align.START)
        controls_row.set_valign(Gtk.Align.CENTER)

        self._prev_button = Gtk.Button.new_from_icon_name("media-skip-backward-symbolic")
        self._prev_button.set_css_classes(["flat", "circular", "mini-player-ctrl-btn"])
        self._prev_button.set_size_request(32, 32)
        self._prev_button.connect("clicked", lambda b: self._player.previous())
        controls_row.append(self._prev_button)

        self._play_button = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        self._play_button.set_css_classes(["mini-player-play-btn", "circular"])
        self._play_button.set_size_request(38, 38)
        self._play_button.connect("clicked", lambda b: self._player.play_pause())
        controls_row.append(self._play_button)

        self._next_button = Gtk.Button.new_from_icon_name("media-skip-forward-symbolic")
        self._next_button.set_css_classes(["flat", "circular", "mini-player-ctrl-btn"])
        self._next_button.set_size_request(32, 32)
        self._next_button.connect("clicked", lambda b: self._player.next())
        controls_row.append(self._next_button)

        self._repeat_btn = Gtk.Button.new_from_icon_name("media-playlist-repeat-symbolic")
        self._repeat_btn.set_css_classes(["flat", "circular", "mini-player-ctrl-btn"])
        self._repeat_btn.set_size_request(32, 32)
        self._repeat_btn.connect("clicked", self._on_repeat_clicked)
        controls_row.append(self._repeat_btn)
        
        right_column.append(controls_row)

        # Progress / Timeline slider
        progress_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        progress_row.set_valign(Gtk.Align.CENTER)

        self._time_label = Gtk.Label(label="0:00")
        self._time_label.set_css_classes(["mini-player-time"])
        progress_row.append(self._time_label)

        self._progress_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0.0, 100.0, 0.1
        )
        self._progress_scale.set_hexpand(True)
        self._progress_scale.set_draw_value(False)
        self._progress_scale.set_css_classes(["mini-player-scale"])
        self._progress_scale.connect("change-value", self._on_seek)
        progress_row.append(self._progress_scale)

        self._duration_label = Gtk.Label(label="0:00")
        self._duration_label.set_css_classes(["mini-player-time"])
        progress_row.append(self._duration_label)

        right_column.append(progress_row)
        self._main_box.append(right_column)

        # Enable dragging by wrapping content inside WindowHandle
        handle = Gtk.WindowHandle()
        handle.set_child(self._main_box)
        handle.add_css_class("mini-player-handle")
        self.set_child(handle)

        self._load_base_css()
        self._update_repeat_button_ui()

    def _load_base_css(self):
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
        }
        .mini-player-scale highlight {
            min-height: 4px;
            border-radius: 2px;
            background-color: @accent_bg_color;
            transition: background-color 0.6s ease;
        }
        .mini-player-scale slider {
            min-height: 10px;
            min-width: 10px;
            border-radius: 50%;
            background-color: @accent_bg_color;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25);
            transition: background-color 0.6s ease;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            provider,
            _MINI_PLAYER_CSS_PRIORITY
        )

    def _update_theme_css(self, bg_hex: str, accent_hex: str, fg_hex: str):
        # Programmatically mix bg_hex and accent_hex for a rich depth gradient
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
        }}
        .mini-player-scale highlight {{
            background-color: {accent_hex};
        }}
        .mini-player-scale slider {{
            background-color: {accent_hex};
        }}
        .mini-player-repeat-active {{
            color: {accent_hex};
            opacity: 1.0 !important;
        }}
        .mini-player-repeat-inactive {{
            color: alpha({fg_hex}, 0.45);
            opacity: 0.6;
        }}
        """
        self._theme_provider.load_from_string(css)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            self._theme_provider,
            _MINI_PLAYER_CSS_PRIORITY
        )

    def _reset_theme(self):
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
        }
        .mini-player-scale highlight {
            background-color: @accent_bg_color;
        }
        .mini-player-scale slider {
            background-color: @accent_bg_color;
        }
        .mini-player-repeat-active {
            color: @accent_bg_color;
            opacity: 1.0 !important;
        }
        .mini-player-repeat-inactive {
            color: alpha(@window_fg_color, 0.45);
            opacity: 0.6;
        }
        """
        self._theme_provider.load_from_string(css)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            self._theme_provider,
            _MINI_PLAYER_CSS_PRIORITY
        )

    def _on_seek(self, scale, scroll, value):
        pos = self._player.get_position()
        if pos and pos.duration > 0:
            seek_ns = int((value / 100.0) * pos.duration)
            self._player.seek(seek_ns)

    def _format_time(self, ns: int) -> str:
        if ns <= 0:
            return "0:00"
        total_sec = int(ns / 1e9)
        m, s = divmod(total_sec, 60)
        return f"{m}:{s:02d}"

    def _on_state_changed(self, state: PlayerState):
        if state == PlayerState.PLAYING:
            self._play_button.set_icon_name("media-playback-pause-symbolic")
        else:
            self._play_button.set_icon_name("media-playback-start-symbolic")
        if state == PlayerState.STOPPED:
            self._progress_scale.set_value(0)
        self._update_repeat_button_ui()

    def set_artwork_from_path(self, art_path: Optional[Path]):
        if art_path and art_path.exists():
            texture = Gdk.Texture.new_from_filename(str(art_path))
            self._art_image.set_paintable(texture)
            bg, accent, fg = get_theme_colors_from_art(art_path)
            self._update_theme_css(bg, accent, fg)
        else:
            self._art_image.set_paintable(None)
            self._reset_theme()

    def _on_song_changed(self, song: Optional[Song]):
        self._update_repeat_button_ui()
        if song is None:
            self._title_label.set_label("Soundwave")
            self._artist_label.set_label("Sin reproducción")
            self._art_image.set_paintable(None)
            self._reset_theme()
            return
        self._title_label.set_label(song.display_title)
        self._artist_label.set_label(song.display_artist)

    def _on_position_changed(self, pos: PlaybackPosition):
        self._time_label.set_label(self._format_time(pos.current))
        self._duration_label.set_label(self._format_time(pos.duration))
        if pos.duration > 0:
            self._progress_scale.set_value((pos.current / pos.duration) * 100)

    def _on_repeat_clicked(self, button):
        current = self._player.get_repeat_mode()
        if current == RepeatMode.NONE:
            self._player.set_repeat_mode(RepeatMode.ALL)
        elif current == RepeatMode.ALL:
            self._player.set_repeat_mode(RepeatMode.ONE)
        else:
            self._player.set_repeat_mode(RepeatMode.NONE)
        self._update_repeat_button_ui()

    def _update_repeat_button_ui(self):
        if not hasattr(self, "_repeat_btn"):
            return
        current = self._player.get_repeat_mode()
        if current == RepeatMode.NONE:
            self._repeat_btn.set_icon_name("media-playlist-repeat-symbolic")
            self._repeat_btn.remove_css_class("mini-player-repeat-active")
            self._repeat_btn.add_css_class("mini-player-repeat-inactive")
            self._repeat_btn.set_tooltip_text("Modo repetición")
        elif current == RepeatMode.ALL:
            self._repeat_btn.set_icon_name("media-playlist-repeat-symbolic")
            self._repeat_btn.remove_css_class("mini-player-repeat-inactive")
            self._repeat_btn.add_css_class("mini-player-repeat-active")
            self._repeat_btn.set_tooltip_text("Repetir todo")
        elif current == RepeatMode.ONE:
            self._repeat_btn.set_icon_name("media-playlist-repeat-song-symbolic")
            self._repeat_btn.remove_css_class("mini-player-repeat-inactive")
            self._repeat_btn.add_css_class("mini-player-repeat-active")
            self._repeat_btn.set_tooltip_text("Repetir una")

    def connect_restore_window(self, cb: RestoreWindowCallback):
        self._restore_cbs.append(cb)

    def _emit_restore(self):
        for cb in self._restore_cbs:
            cb()
