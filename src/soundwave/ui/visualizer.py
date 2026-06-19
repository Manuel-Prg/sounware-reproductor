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
from typing import Optional
from pathlib import Path

from soundwave.library.database import Song
from soundwave.library.album_art import get_art_path
from soundwave.library.color_extract import get_theme_colors_from_art

def hex_to_rgb(hex_str: str) -> tuple[float, float, float]:
    try:
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 3:
            hex_str = ''.join([c*2 for c in hex_str])
        r = int(hex_str[0:2], 16) / 255.0
        g = int(hex_str[2:4], 16) / 255.0
        b = int(hex_str[4:6], 16) / 255.0
        return r, g, b
    except Exception:
        return 0.1, 0.1, 0.1  # default dark gray


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

        # State
        self._current_values = [0.0] * 64
        self._target_values = [0.0] * 64
        self._timer_id = None
        self._is_visible = False

        # Default colors (fallback)
        self._bg_color = (0.05, 0.05, 0.05)
        self._accent_color = (0.11, 0.73, 0.33)  # Spotify green
        self._fg_color = (0.8, 0.8, 0.8)

        self._setup_ui()

    def _setup_ui(self):
        # 1. Background drawing area (the visualizer itself)
        if CAIRO_SUPPORTED:
            self._drawing_area = Gtk.DrawingArea()
            self._drawing_area.set_draw_func(self._draw_callback, None)
            self.set_child(self._drawing_area)
        else:
            self._drawing_area = None
            fallback_label = Gtk.Label(label="Visualizador no disponible\n(Instale python3-gi-cairo)")
            fallback_label.set_justify(Gtk.Justification.CENTER)
            fallback_label.add_css_class("caption")
            fallback_label.set_margin_bottom(24)
            self.set_child(fallback_label)

        # 2. Overlay content: centered box
        overlay_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        overlay_box.set_halign(Gtk.Align.CENTER)
        overlay_box.set_valign(Gtk.Align.CENTER)

        # Large rounded album artwork
        self._art_picture = Gtk.Picture()
        self._art_picture.set_size_request(240, 240)
        self._art_picture.set_content_fit(Gtk.ContentFit.COVER)
        self._art_picture.set_css_classes(["album-cover", "visualizer-art"])
        overlay_box.append(self._art_picture)

        # Song metadata labels
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
        labels_box.append(self._artist_label)

        overlay_box.append(labels_box)

        # Add overlay box
        self.add_overlay(overlay_box)

        # Load CSS for labels
        self._load_css()

    def _load_css(self):
        css_provider = Gtk.CssProvider()
        css = """
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
        """
        css_provider.load_from_data(css.encode("utf-8"))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 10
        )

    def update_song(self, song: Optional[Song]):
        if not song:
            self._title_label.set_text("Sin reproducción")
            self._artist_label.set_text("")
            self._art_picture.set_paintable(None)
            self._bg_color = (0.05, 0.05, 0.05)
            self._accent_color = (0.11, 0.73, 0.33)
            self._fg_color = (0.8, 0.8, 0.8)
            return

        self._title_label.set_text(song.display_title)
        self._artist_label.set_text(song.display_artist)

        # Get artwork
        art_path = get_art_path(song.id, self.db)
        if art_path and art_path.exists():
            self._art_picture.set_filename(str(art_path))

            # Extract colors
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

    def _draw_callback(self, area, cr, width, height, user_data):
        # 1. Background gradient (dark with soft accent tint at the bottom/center)
        bg_pat = cairo.LinearGradient(0, 0, 0, height)
        r, g, b = self._bg_color
        bg_pat.add_color_stop_rgb(0, r * 0.15, g * 0.15, b * 0.15)
        bg_pat.add_color_stop_rgb(1.0, 0.03, 0.03, 0.03)
        cr.rectangle(0, 0, width, height)
        cr.set_source(bg_pat)
        cr.fill()

        # 2. Draw spectrum bars
        num_bars = len(self._current_values)
        if num_bars == 0:
            return

        spacing = 4
        bar_width = (width - spacing * (num_bars + 1)) / num_bars
        if bar_width < 1.0:
            bar_width = 1.0

        # Linear gradient horizontal for bars
        pat = cairo.LinearGradient(0, 0, width, 0)
        ar, ag, ab = self._accent_color
        fr, fg, fb = self._fg_color
        # Add dynamic color stops
        pat.add_color_stop_rgb(0.0, ar, ag, ab)
        pat.add_color_stop_rgb(0.5, fr, fg, fb)
        pat.add_color_stop_rgb(1.0, ar, ag, ab)

        cr.set_source(pat)

        # Baseline for bars (at 95% of height, drawing upwards)
        max_h = height * 0.35
        baseline = height - 16

        for i in range(num_bars):
            val = self._current_values[i]
            bar_h = val * max_h
            if bar_h < 2.0:
                bar_h = 2.0

            x = spacing + i * (bar_width + spacing)
            y = baseline - bar_h

            self._draw_rounded_rect(cr, x, y, bar_width, bar_h, min(bar_width / 2.0, 4.0))
            cr.fill()

    def _draw_rounded_rect(self, cr, x, y, w, h, r):
        if h <= 0:
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

    def _on_spectrum_data(self, magnitudes: list[float]):
        # Magnitudes are in dB (e.g. -60 to 0). Normalize to 0..1
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

        # Trigger redraw
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
