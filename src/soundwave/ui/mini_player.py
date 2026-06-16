import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk, Pango

from pathlib import Path
from typing import Optional, Callable

from soundwave.player.engine import Player, PlayerState, RepeatMode, PlaybackPosition
from soundwave.library.database import Song


RestoreWindowCallback = Callable[[], None]


class MiniPlayer(Adw.Window):
    def __init__(self, player: Player):
        super().__init__()
        self._player = player
        self._restore_cbs: list[RestoreWindowCallback] = []

        self.set_title("Soundwave")
        self.set_default_size(320, 520)
        self.set_resizable(False)

        self._build_ui()

        self._player.connect_state(self._on_state_changed)
        self._player.connect_song(self._on_song_changed)
        self._player.connect_position(self._on_position_changed)

    def _build_ui(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_css_classes(["mini-player"])

        # Close / restore button
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        header_box.set_margin_top(6)
        header_box.set_margin_start(6)
        header_box.set_margin_end(6)

        restore_btn = Gtk.Button.new_from_icon_name("go-up-symbolic")
        restore_btn.set_css_classes(["flat", "circular"])
        restore_btn.set_tooltip_text("Restaurar ventana")
        restore_btn.connect("clicked", lambda b: self._emit_restore())
        header_box.append(restore_btn)

        header_box.set_hexpand(True)

        close_btn = Gtk.Button.new_from_icon_name("window-close-symbolic")
        close_btn.set_css_classes(["flat", "circular"])
        close_btn.set_tooltip_text("Cerrar")
        close_btn.connect("clicked", lambda b: self._emit_restore())
        header_box.append(close_btn)

        box.append(header_box)

        # Album art (large)
        self._art_image = Gtk.Picture()
        self._art_image.set_size_request(280, 280)
        self._art_image.set_content_fit(Gtk.ContentFit.COVER)
        self._art_image.set_margin_top(12)
        self._art_image.set_margin_start(20)
        self._art_image.set_margin_end(20)
        self._art_image.set_css_classes(["album-cover"])
        box.append(self._art_image)

        # Song info
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info_box.set_margin_top(16)
        info_box.set_margin_start(20)
        info_box.set_margin_end(20)

        self._title_label = Gtk.Label(label="Soundwave")
        self._title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._title_label.set_css_classes(["title", "heading"])
        self._title_label.set_xalign(0.5)
        info_box.append(self._title_label)

        self._artist_label = Gtk.Label(label="Sin reproducción")
        self._artist_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._artist_label.set_xalign(0.5)
        self._artist_label.add_css_class("caption")
        info_box.append(self._artist_label)

        box.append(info_box)

        # Progress bar
        progress_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        progress_box.set_margin_top(8)
        progress_box.set_margin_start(20)
        progress_box.set_margin_end(20)

        self._time_label = Gtk.Label(label="0:00")
        self._time_label.add_css_class("caption")
        progress_box.append(self._time_label)

        self._progress_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0.0, 100.0, 0.1
        )
        self._progress_scale.set_hexpand(True)
        self._progress_scale.set_draw_value(False)
        self._progress_scale.connect("change-value", self._on_seek)
        progress_box.append(self._progress_scale)

        self._duration_label = Gtk.Label(label="0:00")
        self._duration_label.add_css_class("caption")
        progress_box.append(self._duration_label)

        box.append(progress_box)

        # Controls
        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        controls_box.set_halign(Gtk.Align.CENTER)
        controls_box.set_margin_top(16)
        controls_box.set_margin_bottom(20)

        self._prev_button = Gtk.Button.new_from_icon_name("media-skip-backward-symbolic")
        self._prev_button.set_css_classes(["flat", "circular"])
        self._prev_button.set_size_request(44, 44)
        self._prev_button.connect("clicked", lambda b: self._player.previous())
        controls_box.append(self._prev_button)

        self._play_button = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        self._play_button.set_css_classes(["flat", "circular"])
        self._play_button.set_size_request(56, 56)
        self._play_button.connect("clicked", lambda b: self._player.play_pause())
        controls_box.append(self._play_button)

        self._next_button = Gtk.Button.new_from_icon_name("media-skip-forward-symbolic")
        self._next_button.set_css_classes(["flat", "circular"])
        self._next_button.set_size_request(44, 44)
        self._next_button.connect("clicked", lambda b: self._player.next())
        controls_box.append(self._next_button)

        box.append(controls_box)

        self.set_content(box)

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

    # --- State updates ---
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
        else:
            self._art_image.set_paintable(None)

    def _on_song_changed(self, song: Optional[Song]):
        if song is None:
            self._title_label.set_label("Soundwave")
            self._artist_label.set_label("Sin reproducción")
            self._art_image.set_paintable(None)
            return
        self._title_label.set_label(song.display_title)
        self._artist_label.set_label(song.display_artist)

    def _on_position_changed(self, pos: PlaybackPosition):
        self._time_label.set_label(self._format_time(pos.current))
        self._duration_label.set_label(self._format_time(pos.duration))
        if pos.duration > 0:
            self._progress_scale.set_value((pos.current / pos.duration) * 100)

    # --- Callbacks ---
    def connect_restore_window(self, cb: RestoreWindowCallback):
        self._restore_cbs.append(cb)

    def _emit_restore(self):
        for cb in self._restore_cbs:
            cb()
