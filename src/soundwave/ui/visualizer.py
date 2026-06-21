import gi
try:
    gi.require_version("cairo", "1.0")
    import cairo
except (ValueError, ImportError):
    cairo = None

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Pango, GLib, Gdk
import math
from typing import Optional, Callable
from pathlib import Path

from soundwave.library.database import Song
from soundwave.library.album_art import get_art_path
from soundwave.library.color_extract import get_theme_colors_from_art
from soundwave.ui.utils import hex_to_rgb, draw_rounded_rect, clear_container
from soundwave.ui.visualizer_styles import load_visualizer_css
from soundwave.ui.visualizer_discography import VisualizerDiscographyMixin, extract_main_artist


PlaySongCallback = Callable[[Song, list[Song]], None]


CAIRO_SUPPORTED = False
if cairo is not None:
    try:
        import gi.repository.cairo
        CAIRO_SUPPORTED = True
    except (ImportError, ModuleNotFoundError):
        CAIRO_SUPPORTED = False


class VisualizerView(Gtk.Overlay, VisualizerDiscographyMixin):
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
        self._visualizer_mode = 0  # 0: Bars, 1: Wave, 2: Blocks, 3: Radial

        self._bg_color = (0.05, 0.05, 0.05)
        self._accent_color = (0.11, 0.73, 0.33)
        self._fg_color = (0.8, 0.8, 0.8)

        self._setup_ui()

    def _setup_ui(self):
        self._dynamic_css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            # pyrefly: ignore [bad-argument-type]
            Gdk.Display.get_default(),
            self._dynamic_css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 11
        )

        bg_click_gesture = Gtk.GestureClick()
        bg_click_gesture.connect("pressed", self._on_bg_clicked)

        if CAIRO_SUPPORTED:
            self._drawing_area = Gtk.DrawingArea()
            self._drawing_area.set_draw_func(self._draw_callback, None)
            self._drawing_area.add_controller(bg_click_gesture)
            self.set_child(self._drawing_area)
            self._update_theme_colors()
        else:
            # pyrefly: ignore [bad-assignment]
            self._drawing_area = None
            bg_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            bg_box.set_css_classes(["visualizer-bg", "visualizer-fallback-bg"])
            bg_box.set_vexpand(True)
            bg_box.set_hexpand(True)
            bg_box.add_controller(bg_click_gesture)
            
            self._bars_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            self._bars_container.set_valign(Gtk.Align.END)
            self._bars_container.set_vexpand(True)
            self._bars_container.set_hexpand(True)
            self._bars_container.set_margin_bottom(16)
            self._bars_container.set_margin_start(16)
            self._bars_container.set_margin_end(16)
            
            self._bar_widgets = []
            for i in range(64):
                bar_wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                bar_wrapper.set_valign(Gtk.Align.END)
                bar_wrapper.set_vexpand(True)
                bar_wrapper.set_hexpand(True)
                
                bar_fill = Gtk.Box()
                bar_fill.set_halign(Gtk.Align.CENTER)
                bar_fill.add_css_class(f"visualizer-bar-{i}")
                
                bar_wrapper.append(bar_fill)
                self._bars_container.append(bar_wrapper)
                self._bar_widgets.append(bar_fill)
                
            bg_box.append(self._bars_container)
            self.set_child(bg_box)
            self._update_theme_colors()

        overlay_scroll = Gtk.ScrolledWindow()
        overlay_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        overlay_scroll.set_halign(Gtk.Align.FILL)
        overlay_scroll.set_valign(Gtk.Align.FILL)
        overlay_scroll.set_vexpand(True)
        overlay_scroll.set_margin_bottom(120)

        overlay_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        overlay_box.set_halign(Gtk.Align.CENTER)
        overlay_box.set_valign(Gtk.Align.CENTER)
        overlay_box.set_vexpand(True)

        self._art_picture = Gtk.Picture()
        self._art_picture.set_size_request(220, 220)
        self._art_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self._art_picture.set_css_classes(["album-cover", "visualizer-art"])
        self._art_picture.set_halign(Gtk.Align.CENTER)
        self._art_picture.set_hexpand(False)
        self._art_picture.set_vexpand(False)
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

        load_visualizer_css()

    def _update_theme_colors(self):
        css_parts = []
        ar, ag, ab = self._accent_color
        ri, gi, bi = int(ar * 255), int(ag * 255), int(ab * 255)

        css_parts.append(f"""
        .discography-song-title-current,
        .discography-song-duration-current,
        .discography-song-icon-current {{
            color: rgb({ri}, {gi}, {bi}) !important;
        }}
        .discography-song-row-current {{
            background-color: rgba({ri}, {gi}, {bi}, 0.12) !important;
        }}
        .discography-song-row-current:hover {{
            background-color: rgba({ri}, {gi}, {bi}, 0.18) !important;
        }}
        """)

        if not CAIRO_SUPPORTED:
            bg_r, bg_g, bg_b = self._bg_color
            r1, g1, b1 = int(bg_r * 0.15 * 255), int(bg_g * 0.15 * 255), int(bg_b * 0.15 * 255)
            css_parts.append(f"""
            .visualizer-fallback-bg {{
                background: linear-gradient(to bottom, rgb({r1}, {g1}, {b1}), #080808);
            }}
            """)
            
            num_bars = len(self._current_values)
            fr, fg, fb = self._fg_color
            for i in range(num_bars):
                half = (num_bars - 1) / 2.0
                if half > 0:
                    t = 1.0 - abs(i - half) / half
                else:
                    t = 0.0
                
                r = ar + (fr - ar) * t
                g = ag + (fg - ag) * t
                b = ab + (fb - ab) * t
                
                bri, bgi, bbi = int(r * 255), int(g * 255), int(b * 255)
                css_parts.append(f"""
                .visualizer-bar-{i} {{
                    background-color: rgb({bri}, {bgi}, {bbi});
                    border-radius: 3px;
                }}
                """)
                
        css_data = "\n".join(css_parts)
        self._dynamic_css_provider.load_from_data(css_data.encode("utf-8"))

    def _update_fallback_bars(self):
        if not hasattr(self, "_bar_widgets") or not self._bar_widgets:
            return
        
        container_width = self.get_width()
        container_height = self.get_height()
        if container_height <= 0:
            container_height = 300
        if container_width <= 0:
            container_width = 800
            
        spacing = 4
        bar_width = int((container_width - spacing * 63) / 64)
        if bar_width < 1:
            bar_width = 1
        elif bar_width > 12:
            bar_width = 12
            
        max_h = min(container_height * 0.20, 100.0)
        
        # Adjust wrapper valigns depending on mode (0: Bottom, 1: Center, 2: Top)
        for i, bar_fill in enumerate(self._bar_widgets):
            parent = bar_fill.get_parent()
            if parent:
                if self._visualizer_mode == 0:
                    parent.set_valign(Gtk.Align.END)
                elif self._visualizer_mode == 1:
                    parent.set_valign(Gtk.Align.CENTER)
                else:
                    parent.set_valign(Gtk.Align.START)

            val = self._current_values[i]
            bar_h = val * max_h
            if bar_h < 2.0:
                bar_h = 2.0
            bar_fill.set_size_request(bar_width, int(bar_h))

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
            self._update_theme_colors()
            return

        self._title_label.set_text(song.display_title)
        self._artist_label.set_text(song.display_artist)
        self._current_artist = song.display_artist

        art_path = get_art_path(song.id, self.db) if song.id is not None else None
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

        self._update_theme_colors()

        if self._show_discography:
            self._populate_discography()

    def _on_bg_clicked(self, gesture, n_press, x, y):
        if CAIRO_SUPPORTED:
            self._visualizer_mode = (self._visualizer_mode + 1) % 4
            self._drawing_area.queue_draw()
        else:
            self._visualizer_mode = (self._visualizer_mode + 1) % 3
            self._update_fallback_bars()

    def _draw_callback(self, area, cr, width, height, user_data):
        # pyrefly: ignore [missing-attribute]
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

        ar, ag, ab = self._accent_color
        fr, fg, fb = self._fg_color

        if self._visualizer_mode == 3:
            # Mode 3: Radial / Circular spectrum surrounding the album art in the center
            cx = width / 2.0
            cy = height / 2.0
            r_base = 145.0  # Base radius (larger than the 220px album cover which is 110px radius)
            
            # Source gradient for radial lines
            # pyrefly: ignore [missing-attribute]
            pat = cairo.LinearGradient(0, 0, width, height)
            pat.add_color_stop_rgb(0.0, ar, ag, ab)
            pat.add_color_stop_rgb(0.5, fr, fg, fb)
            pat.add_color_stop_rgb(1.0, ar, ag, ab)
            cr.set_source(pat)
            
            # Setup line cap and width
            bar_width = (2.0 * math.pi * r_base) / num_bars * 0.6
            if bar_width < 2.0:
                bar_width = 2.0
            cr.set_line_width(bar_width)
            # pyrefly: ignore [missing-attribute]
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            
            max_h = 70.0  # Max length of the pulsing radial lines
            
            for i in range(num_bars):
                val = self._current_values[i]
                h = val * max_h
                if h < 2.0:
                    h = 2.0
                # Distribute bars in a complete circle
                theta = i * (2.0 * math.pi / num_bars) - (math.pi / 2.0)
                cos_t = math.cos(theta)
                sin_t = math.sin(theta)
                
                x1 = cx + r_base * cos_t
                y1 = cy + r_base * sin_t
                x2 = cx + (r_base + h) * cos_t
                y2 = cy + (r_base + h) * sin_t
                
                cr.move_to(x1, y1)
                cr.line_to(x2, y2)
                cr.stroke()
            return

        # Modes 0, 1, 2: Horizontal layouts
        spacing = 4
        bar_width = (width - spacing * (num_bars + 1)) / num_bars
        if bar_width < 1.0:
            bar_width = 1.0

        # pyrefly: ignore [missing-attribute]
        pat = cairo.LinearGradient(0, 0, width, 0)
        pat.add_color_stop_rgb(0.0, ar, ag, ab)
        pat.add_color_stop_rgb(0.5, fr, fg, fb)
        pat.add_color_stop_rgb(1.0, ar, ag, ab)
        cr.set_source(pat)

        max_h = min(height * 0.20, 100.0)
        baseline = height - 16

        if self._visualizer_mode == 1:
            # Mode 1: Continuous Wave
            cr.new_path()
            # Start at left baseline
            cr.move_to(0, baseline)
            for i in range(num_bars):
                val = self._current_values[i]
                bar_h = val * max_h
                x = spacing + i * (bar_width + spacing) + bar_width / 2.0
                y = baseline - bar_h
                cr.line_to(x, y)
            # End at right baseline
            cr.line_to(width, baseline)
            cr.close_path()
            
            # Fill with a nice alpha gradient
            # pyrefly: ignore [missing-attribute]
            fill_pat = cairo.LinearGradient(0, baseline - max_h, 0, baseline)
            fill_pat.add_color_stop_rgba(0.0, ar, ag, ab, 0.55)
            fill_pat.add_color_stop_rgba(1.0, ar, ag, ab, 0.0)
            cr.set_source(fill_pat)
            cr.fill_preserve()
            
            # Stroke outline
            cr.set_source(pat)
            cr.set_line_width(3.0)
            # pyrefly: ignore [missing-attribute]
            cr.set_line_join(cairo.LINE_JOIN_ROUND)
            cr.stroke()

        elif self._visualizer_mode == 2:
            # Mode 2: Digital LED Blocks
            block_h = 4.0
            block_spacing = 2.0
            for i in range(num_bars):
                val = self._current_values[i]
                bar_h = val * max_h
                num_blocks = int(bar_h / (block_h + block_spacing))
                if num_blocks < 1:
                    num_blocks = 1
                x = spacing + i * (bar_width + spacing)
                for b in range(num_blocks):
                    y = baseline - b * (block_h + block_spacing) - block_h
                    draw_rounded_rect(cr, x, y, bar_width, block_h, 1.0)
                    cr.fill()
        else:
            # Mode 0: Rounded Vertical Bars
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
        else:
            self._update_fallback_bars()
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
        if not self._drawing_area:
            self._update_fallback_bars()
        if self._show_discography:
            self._show_discography = False
            self._discography_revealer.set_reveal_child(False)

    def connect_play_song(self, cb: PlaySongCallback):
        self._play_song_cbs.append(cb)
