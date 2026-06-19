import gi
gi.require_version("cairo", "1.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Pango, GLib, Gdk
import cairo
try:
    import gi.repository.cairo
except ImportError:
    pass
import math
from typing import Optional, Callable
from pathlib import Path

from soundwave.library.database import Song
from soundwave.library.album_art import get_art_path
from soundwave.library.color_extract import get_theme_colors_from_art
from soundwave.ui.utils import hex_to_rgb, draw_rounded_rect, clear_container


PlaySongCallback = Callable[[Song, list[Song]], None]


CAIRO_SUPPORTED = False
try:
    import gi.repository.cairo
    import _gi_cairo
    CAIRO_SUPPORTED = True
except (ImportError, ModuleNotFoundError):
    CAIRO_SUPPORTED = False


class VisualizerView(Gtk.Overlay):
    def __init__(self, db, player):
        super().__init__()
        self.db = db
        self._player = player
        self._play_song_cbs: list[PlaySongCallback] = []
        self._current_artist: str = ""

        self._current_values = [0.0] * 64
        self._target_values = [0.0] * 64
        self._timer_id = None
        self._is_visible = False
        self._show_discography = False

        self._bg_color = (0.05, 0.05, 0.05)
        self._accent_color = (0.11, 0.73, 0.33)
        self._fg_color = (0.8, 0.8, 0.8)

        self._setup_ui()

    def _setup_ui(self):
        if CAIRO_SUPPORTED:
            self._drawing_area = Gtk.DrawingArea()
            self._drawing_area.set_draw_func(self._draw_callback, None)
            self.set_child(self._drawing_area)
        else:
            self._drawing_area = None
            bg_box = Gtk.Box()
            bg_box.set_css_classes(["visualizer-bg"])
            self._no_viz_label = Gtk.Label(
                label="Espectro no disponible (instale python3-gi-cairo)",
                css_classes=["caption"]
            )
            self._no_viz_label.set_halign(Gtk.Align.END)
            self._no_viz_label.set_valign(Gtk.Align.END)
            self._no_viz_label.set_margin_end(12)
            self._no_viz_label.set_margin_bottom(12)
            bg_box.append(self._no_viz_label)
            self.set_child(bg_box)

        overlay_scroll = Gtk.ScrolledWindow()
        overlay_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        overlay_scroll.set_halign(Gtk.Align.FILL)
        overlay_scroll.set_valign(Gtk.Align.FILL)
        overlay_scroll.set_vexpand(True)

        overlay_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        overlay_box.set_halign(Gtk.Align.CENTER)
        overlay_box.set_valign(Gtk.Align.CENTER)
        overlay_box.set_vexpand(True)

        self._art_picture = Gtk.Picture()
        self._art_picture.set_size_request(220, 220)
        self._art_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self._art_picture.set_css_classes(["album-cover", "visualizer-art"])
        self._art_picture.set_halign(Gtk.Align.CENTER)
        overlay_box.append(self._art_picture)

        labels_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        labels_box.set_halign(Gtk.Align.CENTER)

        self._title_label = Gtk.Label(label="Sin reproducción")
        self._title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._title_label.set_max_width_chars(30)
        self._title_label.add_css_class("visualizer-title")
        labels_box.append(self._title_label)

        self._artist_label = Gtk.Label(label="")
        self._artist_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._artist_label.set_max_width_chars(35)
        self._artist_label.add_css_class("visualizer-artist")
        self._artist_label.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        gesture = Gtk.GestureClick()
        gesture.connect("pressed", self._on_artist_clicked)
        self._artist_label.add_controller(gesture)
        labels_box.append(self._artist_label)

        overlay_box.append(labels_box)

        self._discography_revealer = Gtk.Revealer()
        self._discography_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self._discography_revealer.set_transition_duration(250)
        self._discography_revealer.set_reveal_child(False)

        self._discography_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._discography_box.set_halign(Gtk.Align.CENTER)
        self._discography_revealer.set_child(self._discography_box)
        overlay_box.append(self._discography_revealer)

        overlay_scroll.set_child(overlay_box)
        self.add_overlay(overlay_scroll)

        self._load_css()

    def _load_css(self):
        css_provider = Gtk.CssProvider()
        css = """
        .visualizer-bg {
            background-color: #080808;
        }
        .visualizer-art {
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            background-color: #242424;
        }
        .visualizer-title {
            font-size: 20pt;
            font-weight: bold;
            color: #ffffff;
            text-shadow: 0 2px 4px rgba(0,0,0,0.5);
        }
        .visualizer-artist {
            font-size: 13pt;
            color: rgba(255, 255, 255, 0.7);
            text-shadow: 0 2px 4px rgba(0,0,0,0.5);
        }
        .visualizer-artist:hover {
            color: #ffffff;
        }
        .discography-section {
            background-color: rgba(0, 0, 0, 0.45);
            border-radius: 12px;
            padding: 8px;
        }
        .discography-header {
            font-size: 11pt;
            font-weight: bold;
            color: rgba(255, 255, 255, 0.85);
            text-shadow: 0 1px 2px rgba(0,0,0,0.5);
            padding: 4px 0;
        }
        .discography-album {
            font-size: 10pt;
            color: rgba(255, 255, 255, 0.8);
            text-shadow: 0 1px 2px rgba(0,0,0,0.5);
            padding: 3px 8px;
            border-radius: 6px;
        }
        .discography-album:hover {
            background-color: rgba(255, 255, 255, 0.1);
        }
        .discography-song {
            font-size: 9pt;
            color: rgba(255, 255, 255, 0.65);
            text-shadow: 0 1px 2px rgba(0,0,0,0.5);
            padding: 2px 8px;
            border-radius: 4px;
        }
        .discography-song:hover {
            background-color: rgba(255, 255, 255, 0.08);
            color: #ffffff;
        }
        .discography-song-current {
            color: #1db954;
        }
        """
        css_provider.load_from_data(css.encode("utf-8"))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 10
        )

    def _on_artist_clicked(self, gesture, n_press, x, y):
        if self._current_artist:
            self._show_discography = not self._show_discography
            if self._show_discography:
                self._populate_discography()
            self._discography_revealer.set_reveal_child(self._show_discography)

    def _populate_discography(self):
        clear_container(self._discography_box)

        if not self._current_artist:
            return

        songs = self.db.get_songs_by_artist(self._current_artist)
        if not songs:
            return

        albums: dict[str, list[Song]] = {}
        for s in songs:
            album_name = s.display_album
            if album_name not in albums:
                albums[album_name] = []
            albums[album_name].append(s)

        current_song = self._player.get_current_song()
        current_id = current_song.id if current_song else None

        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        section.set_css_classes(["discography-section"])
        section.set_halign(Gtk.Align.CENTER)

        header = Gtk.Label(label=f"Discografía de {self._current_artist}")
        header.set_css_classes(["discography-header"])
        section.append(header)

        for album_name, album_songs in albums.items():
            album_label = Gtk.Label(label=album_name)
            album_label.set_css_classes(["discography-album"])
            album_label.set_xalign(0)
            section.append(album_label)

            for s in album_songs:
                song_label = Gtk.Label(label=GLib.markup_escape_text(s.display_title))
                song_label.set_xalign(0)
                song_label.set_css_classes(["discography-song"])
                if s.id == current_id:
                    song_label.add_css_class("discography-song-current")
                song_label.set_cursor(Gdk.Cursor.new_from_name("pointer"))
                song_gesture = Gtk.GestureClick()
                song_gesture.connect("pressed", lambda g, n, x, y, song=s, all_songs=songs: self._on_disco_song_clicked(song, all_songs))
                song_label.add_controller(song_gesture)
                section.append(song_label)

        self._discography_box.append(section)
        self._discography_box.show()

    def _on_disco_song_clicked(self, song: Song, all_songs: list[Song]):
        for cb in self._play_song_cbs:
            cb(song, all_songs)

    def update_song(self, song: Optional[Song]):
        if not song:
            self._title_label.set_text("Sin reproducción")
            self._artist_label.set_text("")
            self._art_picture.set_paintable(None)
            self._bg_color = (0.05, 0.05, 0.05)
            self._accent_color = (0.11, 0.73, 0.33)
            self._fg_color = (0.8, 0.8, 0.8)
            self._current_artist = ""
            if self._show_discography:
                self._show_discography = False
                self._discography_revealer.set_reveal_child(False)
            return

        self._title_label.set_text(song.display_title)
        self._artist_label.set_text(song.display_artist)
        self._current_artist = song.display_artist

        art_path = get_art_path(song.id, self.db)
        if art_path and art_path.exists():
            self._art_picture.set_filename(str(art_path))
            try:
                bg_hex, accent_hex, fg_hex = get_theme_colors_from_art(art_path)
                self._bg_color = hex_to_rgb(bg_hex)
                self._accent_color = hex_to_rgb(accent_hex)
                self._fg_color = hex_to_rgb(fg_hex)
            except Exception:
                pass
        else:
            self._art_picture.set_paintable(None)
            self._bg_color = (0.05, 0.05, 0.05)
            self._accent_color = (0.11, 0.73, 0.33)
            self._fg_color = (0.8, 0.8, 0.8)

        if self._show_discography:
            self._populate_discography()

    def _draw_callback(self, area, cr, width, height, user_data):
        bg_pat = cairo.LinearGradient(0, 0, 0, height)
        r, g, b = self._bg_color
        bg_pat.add_color_stop_rgb(0, r * 0.15, g * 0.15, b * 0.15)
        bg_pat.add_color_stop_rgb(1.0, 0.03, 0.03, 0.03)
        cr.rectangle(0, 0, width, height)
        cr.set_source(bg_pat)
        cr.fill()

        num_bars = len(self._current_values)
        if num_bars == 0:
            return

        spacing = 4
        bar_width = (width - spacing * (num_bars + 1)) / num_bars
        if bar_width < 1.0:
            bar_width = 1.0

        pat = cairo.LinearGradient(0, 0, width, 0)
        ar, ag, ab = self._accent_color
        fr, fg, fb = self._fg_color
        pat.add_color_stop_rgb(0.0, ar, ag, ab)
        pat.add_color_stop_rgb(0.5, fr, fg, fb)
        pat.add_color_stop_rgb(1.0, ar, ag, ab)

        cr.set_source(pat)

        max_h = height * 0.35
        baseline = height - 16

        for i in range(num_bars):
            val = self._current_values[i]
            bar_h = val * max_h
            if bar_h < 2.0:
                bar_h = 2.0
            x = spacing + i * (bar_width + spacing)
            y = baseline - bar_h
            draw_rounded_rect(cr, x, y, bar_width, bar_h, min(bar_width / 2.0, 4.0))
            cr.fill()

    def _on_spectrum_data(self, magnitudes: list[float]):
        threshold = -60.0
        for i in range(min(len(magnitudes), len(self._target_values))):
            val = magnitudes[i]
            if val < threshold:
                norm = 0.0
            else:
                norm = (val - threshold) / (-threshold)
            self._target_values[i] = norm

    def _start_timer(self):
        self._stop_timer()
        self._timer_id = GLib.timeout_add(33, self._animate_step)

    def _stop_timer(self):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    def _animate_step(self) -> bool:
        decay_rate = 0.05
        for i in range(len(self._current_values)):
            target = self._target_values[i]
            current = self._current_values[i]
            if target > current:
                self._current_values[i] += (target - current) * 0.35
            else:
                self._current_values[i] = max(target, current - decay_rate)
        if self._drawing_area:
            self._drawing_area.queue_draw()
        return True

    def on_show(self):
        self._is_visible = True
        self.update_song(self._player.get_current_song())
        self._player.connect_spectrum(self._on_spectrum_data)
        self._player.connect_song(self.update_song)
        self._start_timer()

    def on_hide(self):
        self._is_visible = False
        self._stop_timer()
        self._player.disconnect_spectrum(self._on_spectrum_data)
        self._player.disconnect_song(self.update_song)
        self._current_values = [0.0] * 64
        self._target_values = [0.0] * 64
        if self._show_discography:
            self._show_discography = False
            self._discography_revealer.set_reveal_child(False)

    def connect_play_song(self, cb: PlaySongCallback):
        self._play_song_cbs.append(cb)
