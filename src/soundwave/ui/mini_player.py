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

_MINI_PLAYER_CSS_PRIORITY = Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 10


class MiniPlayer(Adw.Window):
    def __init__(self, player: Player):
        super().__init__()
        self._player = player
        self._restore_cbs: list[RestoreWindowCallback] = []

        self.set_title("Soundwave")
        self.set_default_size(520, 120)
        self.set_resizable(False)
        self.set_decorated(False)

        self._theme_provider = Gtk.CssProvider()

        self._build_ui()
        self._make_draggable(self._main_box)

        self._player.connect_state(self._on_state_changed)
        self._player.connect_song(self._on_song_changed)
        self._player.connect_position(self._on_position_changed)

    def _build_ui(self):
        self._main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._main_box.set_css_classes(["mini-player"])
        self._main_box.set_cursor_from_name("grab")

        # Thumbnail
        art_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        art_box.set_valign(Gtk.Align.CENTER)
        art_box.set_margin_start(8)

        self._art_image = Gtk.Picture()
        self._art_image.set_size_request(56, 56)
        self._art_image.set_content_fit(Gtk.ContentFit.COVER)
        self._art_image.set_css_classes(["mini-player-art"])
        art_box.append(self._art_image)
        self._main_box.append(art_box)

        # Center: info + controls
        center_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        center_box.set_hexpand(True)
        center_box.set_valign(Gtk.Align.CENTER)
        center_box.set_margin_start(8)
        center_box.set_margin_end(4)

        # Row 1: title + time
        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self._title_label = Gtk.Label(label="Soundwave")
        self._title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._title_label.set_xalign(0)
        self._title_label.set_css_classes(["mini-player-title"])
        self._title_label.set_hexpand(True)
        row1.append(self._title_label)

        self._time_label = Gtk.Label(label="0:00")
        self._time_label.set_css_classes(["mini-player-time"])
        self._time_label.set_xalign(1)
        row1.append(self._time_label)

        center_box.append(row1)

        # Row 2: artist + controls + progress
        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        row2.set_valign(Gtk.Align.CENTER)

        self._artist_label = Gtk.Label(label="Sin reproducción")
        self._artist_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._artist_label.set_xalign(0)
        self._artist_label.set_css_classes(["mini-player-artist"])
        self._artist_label.set_size_request(100, -1)
        row2.append(self._artist_label)

        self._prev_button = Gtk.Button.new_from_icon_name("media-skip-backward-symbolic")
        self._prev_button.set_css_classes(["flat", "circular", "mini-player-btn"])
        self._prev_button.set_size_request(30, 30)
        self._prev_button.connect("clicked", lambda b: self._player.previous())
        row2.append(self._prev_button)

        self._play_button = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        self._play_button.set_css_classes(["mini-player-play-btn", "circular"])
        self._play_button.set_size_request(34, 34)
        self._play_button.connect("clicked", lambda b: self._player.play_pause())
        row2.append(self._play_button)

        self._next_button = Gtk.Button.new_from_icon_name("media-skip-forward-symbolic")
        self._next_button.set_css_classes(["flat", "circular", "mini-player-btn"])
        self._next_button.set_size_request(30, 30)
        self._next_button.connect("clicked", lambda b: self._player.next())
        row2.append(self._next_button)

        self._progress_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0.0, 100.0, 0.1
        )
        self._progress_scale.set_size_request(90, -1)
        self._progress_scale.set_draw_value(False)
        self._progress_scale.set_css_classes(["mini-player-scale"])
        self._progress_scale.connect("change-value", self._on_seek)
        row2.append(self._progress_scale)

        self._duration_label = Gtk.Label(label="0:00")
        self._duration_label.set_css_classes(["mini-player-time"])
        row2.append(self._duration_label)

        center_box.append(row2)
        self._main_box.append(center_box)

        # Right: close button
        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        right_box.set_valign(Gtk.Align.CENTER)
        right_box.set_margin_end(8)

        restore_btn = Gtk.Button.new_from_icon_name("go-up-symbolic")
        restore_btn.set_css_classes(["flat", "circular", "mini-player-btn"])
        restore_btn.set_size_request(30, 30)
        restore_btn.set_tooltip_text("Restaurar ventana")
        restore_btn.connect("clicked", lambda b: self._emit_restore())
        right_box.append(restore_btn)

        close_btn = Gtk.Button.new_from_icon_name("window-close-symbolic")
        close_btn.set_css_classes(["flat", "circular", "mini-player-btn"])
        close_btn.set_size_request(30, 30)
        close_btn.set_tooltip_text("Cerrar")
        close_btn.connect("clicked", lambda b: self._emit_restore())
        right_box.append(close_btn)

        self._main_box.append(right_box)

        self.set_content(self._main_box)

        self._load_base_css()

    def _make_draggable(self, widget):
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._on_drag_begin)
        widget.add_controller(drag)

    def _on_drag_begin(self, gesture, start_x, start_y):
        surface = self.get_surface()
        if not surface:
            return
        display = self.get_display()
        timestamp = Gtk.get_current_event_time()
        button = Gdk.BUTTON_PRIMARY
        sx, sy = float(start_x), float(start_y)
        for obj, fn_name, args in [
            (self, "begin_move_drag", (button, sx, sy, timestamp)),
            (Gtk.Window, "begin_move_drag", (self, button, sx, sy, timestamp)),
            (surface, "begin_move", (display, None, button, sx, sy, timestamp)),
        ]:
            fn = getattr(obj, fn_name, None)
            if fn:
                try:
                    fn(*args)
                    return
                except TypeError:
                    continue

    def _load_base_css(self):
        css = """
        .mini-player {
            background-color: @window_bg_color;
            border: none;
            padding: 0;
        }
        .mini-player-art {
            border-radius: 4px;
        }
        .mini-player-title {
            font-weight: bold;
            font-size: 13px;
        }
        .mini-player-artist {
            font-size: 11px;
        }
        .mini-player-time {
            font-size: 11px;
        }
        .mini-player-btn {
            opacity: 0.7;
        }
        .mini-player-btn:hover {
            opacity: 1.0;
        }
        .mini-player-play-btn {
            background-color: @accent_bg_color;
            color: #000000;
            border-radius: 50%;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
            transition: all 0.2s ease;
        }
        .mini-player-play-btn:hover {
            transform: scale(1.08);
        }
        .mini-player-scale trough {
            min-height: 3px;
            border-radius: 2px;
            background-color: alpha(currentColor, 0.15);
        }
        .mini-player-scale highlight {
            min-height: 3px;
            border-radius: 2px;
            background-color: @accent_bg_color;
        }
        .mini-player-scale slider {
            min-height: 10px;
            min-width: 10px;
            border-radius: 50%;
            background-color: @accent_bg_color;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _update_theme_css(self, bg_hex: str, accent_hex: str, fg_hex: str):
        css = f"""
        .mini-player {{
            background-color: {bg_hex};
        }}
        .mini-player-title {{
            color: {fg_hex};
        }}
        .mini-player-artist {{
            color: alpha({fg_hex}, 0.7);
        }}
        .mini-player-time {{
            color: alpha({fg_hex}, 0.7);
        }}
        .mini-player-btn {{
            color: alpha({fg_hex}, 0.7);
        }}
        .mini-player-btn:hover {{
            color: {fg_hex};
        }}
        .mini-player-play-btn {{
            background-color: {accent_hex};
            color: {fg_hex};
            border-radius: 50%;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
            transition: all 0.2s ease;
        }}
        .mini-player-play-btn:hover {{
            transform: scale(1.08);
        }}
        .mini-player-scale trough {{
            min-height: 3px;
            border-radius: 2px;
            background-color: alpha({fg_hex}, 0.15);
        }}
        .mini-player-scale highlight {{
            min-height: 3px;
            border-radius: 2px;
            background-color: {accent_hex};
        }}
        .mini-player-scale slider {{
            min-height: 10px;
            min-width: 10px;
            border-radius: 50%;
            background-color: {accent_hex};
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
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
        }
        .mini-player-title {
            color: @window_fg_color;
        }
        .mini-player-artist {
            color: alpha(@window_fg_color, 0.7);
        }
        .mini-player-time {
            color: alpha(@window_fg_color, 0.7);
        }
        .mini-player-btn {
            color: alpha(@window_fg_color, 0.7);
        }
        .mini-player-btn:hover {
            color: @window_fg_color;
        }
        .mini-player-play-btn {
            background-color: @accent_bg_color;
            color: @accent_fg_color;
            border-radius: 50%;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
            transition: all 0.2s ease;
        }
        .mini-player-play-btn:hover {
            transform: scale(1.08);
        }
        .mini-player-scale trough {
            min-height: 3px;
            border-radius: 2px;
            background-color: alpha(currentColor, 0.15);
        }
        .mini-player-scale highlight {
            min-height: 3px;
            border-radius: 2px;
            background-color: @accent_bg_color;
        }
        .mini-player-scale slider {
            min-height: 10px;
            min-width: 10px;
            border-radius: 50%;
            background-color: @accent_bg_color;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
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

    def connect_restore_window(self, cb: RestoreWindowCallback):
        self._restore_cbs.append(cb)

    def _emit_restore(self):
        for cb in self._restore_cbs:
            cb()
