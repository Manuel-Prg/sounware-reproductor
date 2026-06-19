import gi
gi.require_version("cairo", "1.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk, Pango
try:
    import cairo
    import gi.repository.cairo
except ImportError:
    cairo = None

from pathlib import Path
from typing import Optional, Callable
import math
import json
import threading

from soundwave.player.engine import Player, PlayerState, RepeatMode, PlaybackPosition
from soundwave.library.database import Song, Database


ToggleMiniCallback = Callable[[], None]
ShowEqualizerCallback = Callable[[], None]
ToggleLyricsCallback = Callable[[], None]
NavigateAlbumCallback = Callable[[], None]


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
        return 0.48, 0.28, 0.98


# Check cairo and overrides availability
CAIRO_SUPPORTED = False
try:
    import cairo
    import gi.repository.cairo
    import _gi_cairo
    CAIRO_SUPPORTED = True
except (ImportError, ModuleNotFoundError):
    CAIRO_SUPPORTED = False


class WaveformDrawingArea(Gtk.DrawingArea):
    def __init__(self, seek_callback: Optional[Callable[[float], None]] = None):
        super().__init__()
        self._seek_callback = seek_callback
        self._waveform_data: list[float] = []
        self._progress: float = 0.0
        self._hover_progress: Optional[float] = None
        self._sensitive: bool = False
        
        # Default styling colors
        self._accent_color: tuple[float, float, float] = (0.48, 0.28, 0.98)
        self._dim_color: tuple[float, float, float, float] = (0.7, 0.7, 0.7, 0.3)
        self._hover_color: tuple[float, float, float, float] = (0.48, 0.28, 0.98, 0.55)
        
        self.set_draw_func(self._draw_callback, None)
        self._setup_events()
        self.set_cursor_from_name("pointer")

    def set_cursor_from_name(self, cursor_name: str):
        try:
            display = Gdk.Display.get_default()
            cursor = Gdk.Cursor.new_from_name(cursor_name, None)
            self.set_cursor(cursor)
        except Exception:
            pass

    def _setup_events(self):
        motion = Gtk.EventControllerMotion.new()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)
        
        click = Gtk.GestureClick.new()
        click.connect("pressed", self._on_clicked)
        self.add_controller(click)
        
        drag = Gtk.GestureDrag.new()
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.add_controller(drag)

    def set_sensitive(self, sensitive: bool):
        self._sensitive = sensitive
        self.queue_draw()

    def get_sensitive(self) -> bool:
        return self._sensitive

    def set_waveform(self, data: list[float]):
        self._waveform_data = data
        self.queue_draw()

    def set_progress(self, progress: float):
        self._progress = max(0.0, min(1.0, progress))
        self.queue_draw()

    def set_accent_color(self, r: float, g: float, b: float):
        self._accent_color = (r, g, b)
        self._hover_color = (r, g, b, 0.55)
        self.queue_draw()

    def reset_colors(self):
        self._accent_color = (0.48, 0.28, 0.98)
        self._hover_color = (0.48, 0.28, 0.98, 0.55)
        self.queue_draw()

    def _on_motion(self, controller, x, y):
        if not self._sensitive:
            return
        width = self.get_width()
        if width > 0:
            self._hover_progress = max(0.0, min(1.0, x / width))
            self.queue_draw()

    def _on_leave(self, controller):
        self._hover_progress = None
        self.queue_draw()

    def _on_clicked(self, gesture, n_press, x, y):
        if not self._sensitive:
            return
        width = self.get_width()
        if width > 0:
            progress = max(0.0, min(1.0, x / width))
            self._progress = progress
            if self._seek_callback:
                self._seek_callback(progress)
            self.queue_draw()

    def _on_drag_update(self, gesture, offset_x, offset_y):
        if not self._sensitive:
            return
        success, start_x, start_y = gesture.get_start_point()
        if success:
            width = self.get_width()
            if width > 0:
                x = start_x + offset_x
                progress = max(0.0, min(1.0, x / width))
                self._hover_progress = progress
                self.queue_draw()

    def _on_drag_end(self, gesture, offset_x, offset_y):
        if not self._sensitive:
            return
        success, start_x, start_y = gesture.get_start_point()
        if success:
            width = self.get_width()
            if width > 0:
                x = start_x + offset_x
                progress = max(0.0, min(1.0, x / width))
                self._progress = progress
                if self._seek_callback:
                    self._seek_callback(progress)
        self._hover_progress = None
        self.queue_draw()

    def _draw_callback(self, area, cr, width, height, user_data):
        if not self._sensitive:
            cr.set_source_rgba(0.5, 0.5, 0.5, 0.15)
            self._draw_rounded_rect(cr, 0, height/2 - 2, width, 4, 2)
            cr.fill()
            return

        waveform = self._waveform_data
        if not waveform:
            waveform = [
                0.25 + 0.15 * math.sin(i * 0.1) + 0.1 * math.cos(i * 0.25)
                for i in range(150)
            ]

        num_bars = len(waveform)
        spacing = 1.0
        bar_width = (width - (num_bars - 1) * spacing) / num_bars
        if bar_width < 1.0:
            bar_width = 1.0
            
        max_h = height * 0.85
        
        for i in range(num_bars):
            val = waveform[i]
            bar_h = val * max_h
            if bar_h < 3.0:
                bar_h = 3.0
                
            x = i * (bar_width + spacing)
            y = (height - bar_h) / 2
            
            bar_progress = (i + 0.5) / num_bars
            
            if bar_progress <= self._progress:
                r, g, b = self._accent_color
                cr.set_source_rgb(r, g, b)
            elif self._hover_progress is not None and bar_progress <= self._hover_progress:
                r, g, b, a = self._hover_color
                cr.set_source_rgba(r, g, b, a)
            else:
                r, g, b, a = self._dim_color
                cr.set_source_rgba(r, g, b, a)
                
            self._draw_rounded_rect(cr, x, y, bar_width, bar_h, bar_width / 2.0)
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


class WaveformProgressBar(Gtk.Box):
    def __init__(self, seek_callback: Optional[Callable[[float], None]] = None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._seek_callback = seek_callback
        self._sensitive = False

        if CAIRO_SUPPORTED:
            self._drawing_area = WaveformDrawingArea(seek_callback=self._on_internal_seek)
            self._drawing_area.set_hexpand(True)
            self._drawing_area.set_valign(Gtk.Align.CENTER)
            self.append(self._drawing_area)
            self._scale = None
        else:
            self._drawing_area = None
            self._scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 1.0, 0.001)
            self._scale.set_draw_value(False)
            self._scale.set_hexpand(True)
            self._scale.set_valign(Gtk.Align.CENTER)
            self._scale.connect("change-value", self._on_scale_change_value)
            self.append(self._scale)

    def _on_internal_seek(self, progress: float):
        if self._seek_callback:
            self._seek_callback(progress)

    def _on_scale_change_value(self, scale, scroll, value):
        if self._seek_callback:
            self._seek_callback(value)
        return False

    def set_sensitive(self, sensitive: bool):
        self._sensitive = sensitive
        if self._drawing_area:
            self._drawing_area.set_sensitive(sensitive)
        if self._scale:
            self._scale.set_sensitive(sensitive)

    def get_sensitive(self) -> bool:
        return self._sensitive

    def set_waveform(self, data: list[float]):
        if self._drawing_area:
            self._drawing_area.set_waveform(data)

    def set_progress(self, progress: float):
        if self._drawing_area:
            self._drawing_area.set_progress(progress)
        if self._scale:
            self._scale.set_value(progress)

    def set_accent_color(self, r: float, g: float, b: float):
        if self._drawing_area:
            self._drawing_area.set_accent_color(r, g, b)

    def reset_colors(self):
        if self._drawing_area:
            self._drawing_area.reset_colors()


class PlayerBar(Gtk.Box):
    def __init__(self, player: Player, db: Optional[Database] = None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._player = player
        self._db = db
        self._toggle_mini_cbs: list[ToggleMiniCallback] = []
        self._show_eq_cbs: list[ShowEqualizerCallback] = []
        self._toggle_lyrics_cbs: list[ToggleLyricsCallback] = []
        self._navigate_album_cbs: list[NavigateAlbumCallback] = []
        self._toggle_fullscreen_cbs: list[Callable] = []
        self._toggle_sidebar_cbs: list[Callable] = []

        self.set_css_classes(["player-bar"])
        self.set_size_request(-1, 72)

        self._build_ui()

        self._player.connect_state(self._on_state_changed)
        self._player.connect_song(self._on_song_changed)
        self._player.connect_position(self._on_position_changed)

    def _build_ui(self):
        # Left: album art + song info
        left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        left_box.set_hexpand(False)
        left_box.set_size_request(300, -1)
        left_box.set_margin_start(12)
        left_box.set_margin_top(8)
        left_box.set_margin_bottom(8)

        self._art_image = Gtk.Picture()
        self._art_image.set_size_request(56, 56)
        self._art_image.set_content_fit(Gtk.ContentFit.COVER)
        self._art_image.set_css_classes(["album-cover"])
        self._art_image.set_tooltip_text("Mostrar visualizador")
        try:
            display = Gdk.Display.get_default()
            cursor = Gdk.Cursor.new_from_name("pointer", None)
            self._art_image.set_cursor(cursor)
        except Exception:
            pass
        art_gesture = Gtk.GestureClick()
        art_gesture.connect("pressed", lambda g, n, x, y: self._emit_navigate_album())
        self._art_image.add_controller(art_gesture)
        left_box.append(self._art_image)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        info_box.set_valign(Gtk.Align.CENTER)

        self._title_label = Gtk.Label(label="Sin reproducción")
        self._title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._title_label.set_xalign(0)
        self._title_label.set_css_classes(["heading"])
        info_box.append(self._title_label)

        self._artist_label = Gtk.Label(label="")
        self._artist_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._artist_label.set_xalign(0)
        self._artist_label.add_css_class("caption")
        info_box.append(self._artist_label)

        left_box.append(info_box)
        self.append(left_box)

        # Center: playback controls
        center_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        center_box.set_hexpand(True)
        center_box.set_halign(Gtk.Align.CENTER)

        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        controls_box.set_halign(Gtk.Align.CENTER)

        self._prev_button = Gtk.Button.new_from_icon_name("media-skip-backward-symbolic")
        self._prev_button.set_css_classes(["flat", "circular"])
        self._prev_button.connect("clicked", lambda b: self._player.previous())
        self._prev_button.set_tooltip_text("Anterior (Ctrl+Left)")
        controls_box.append(self._prev_button)

        self._play_button = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        self._play_button.set_css_classes(["play-button-main", "circular"])
        self._play_button.set_size_request(44, 44)
        self._play_button.connect("clicked", lambda b: self._on_play_pause())
        self._play_button.set_tooltip_text("Reproducir/Pausar (Space)")
        controls_box.append(self._play_button)

        self._next_button = Gtk.Button.new_from_icon_name("media-skip-forward-symbolic")
        self._next_button.set_css_classes(["flat", "circular"])
        self._next_button.connect("clicked", lambda b: self._player.next())
        self._next_button.set_tooltip_text("Siguiente (Ctrl+Right)")
        controls_box.append(self._next_button)

        center_box.append(controls_box)

        # Progress bar
        progress_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        progress_box.set_halign(Gtk.Align.CENTER)
        progress_box.set_size_request(400, -1)

        self._time_label = Gtk.Label(label="0:00")
        self._time_label.add_css_class("caption")
        progress_box.append(self._time_label)

        self._progress_scale = WaveformProgressBar(seek_callback=self._on_waveform_seek)
        self._progress_scale.set_size_request(300, 24)
        self._progress_scale.set_hexpand(True)
        self._progress_scale.set_sensitive(False)
        progress_box.append(self._progress_scale)

        self._duration_label = Gtk.Label(label="0:00")
        self._duration_label.add_css_class("caption")
        progress_box.append(self._duration_label)

        center_box.append(progress_box)
        self.append(center_box)

        # Right: volume + extras
        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        right_box.set_hexpand(False)
        right_box.set_margin_end(12)
        right_box.set_valign(Gtk.Align.CENTER)

        # Repeat button
        self._repeat_button = Gtk.ToggleButton()
        self._repeat_button.set_child(Gtk.Image.new_from_icon_name("media-playlist-repeat-symbolic"))
        self._repeat_button.set_css_classes(["flat", "circular"])
        self._repeat_button.set_tooltip_text("Modo repetición")
        self._repeat_button.connect("toggled", self._on_repeat_toggled)
        right_box.append(self._repeat_button)

        # Shuffle button
        self._shuffle_button = Gtk.ToggleButton()
        self._shuffle_button.set_child(Gtk.Image.new_from_icon_name("media-playlist-shuffle-symbolic"))
        self._shuffle_button.set_css_classes(["flat", "circular"])
        self._shuffle_button.set_tooltip_text("Aleatorio")
        self._shuffle_button.connect("toggled", self._on_shuffle_toggled)
        right_box.append(self._shuffle_button)

        # Lyrics button
        self._lyrics_btn = Gtk.ToggleButton()
        self._lyrics_btn.set_child(Gtk.Image.new_from_icon_name("document-edit-symbolic"))
        self._lyrics_btn.set_css_classes(["flat", "circular"])
        self._lyrics_btn.set_tooltip_text("Letras")
        self._lyrics_btn.connect("toggled", lambda b: self._emit_toggle_lyrics())
        right_box.append(self._lyrics_btn)

        # Equalizer button
        self._eq_button = Gtk.Button.new_from_icon_name("preferences-desktop-sound-symbolic")
        self._eq_button.set_css_classes(["flat", "circular"])
        self._eq_button.set_tooltip_text("Ecualizador (Ctrl+E)")
        self._eq_button.connect("clicked", lambda b: self._emit_show_equalizer())
        right_box.append(self._eq_button)

        # Volume
        vol_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self._vol_button = Gtk.Button.new_from_icon_name("audio-volume-high-symbolic")
        self._vol_button.set_css_classes(["flat", "circular", "volume-button"])
        self._vol_button.set_tooltip_text("Silenciar")
        self._vol_button.connect("clicked", self._on_volume_mute)
        vol_box.append(self._vol_button)

        self._volume_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0.0, 1.0, 0.01
        )
        self._volume_scale.set_size_request(100, -1)
        self._volume_scale.set_draw_value(False)
        self._volume_scale.set_value(self._player.get_volume())
        self._volume_scale.connect("change-value", self._on_volume_changed)
        self._volume_scale.set_tooltip_text("Volumen")
        vol_box.append(self._volume_scale)

        right_box.append(vol_box)

        # Sidebar toggle button
        self._sidebar_button = Gtk.Button.new_from_icon_name("sidebar-hide-symbolic")
        self._sidebar_button.set_css_classes(["flat", "circular"])
        self._sidebar_button.set_tooltip_text("Colapsar barra lateral")
        self._sidebar_button.connect("clicked", lambda b: self._emit_toggle_sidebar())
        right_box.append(self._sidebar_button)

        # Fullscreen button
        self._fullscreen_button = Gtk.Button.new_from_icon_name("view-fullscreen-symbolic")
        self._fullscreen_button.set_css_classes(["flat", "circular"])
        self._fullscreen_button.set_tooltip_text("Pantalla completa (F11)")
        self._fullscreen_button.connect("clicked", lambda b: self._emit_toggle_fullscreen())
        right_box.append(self._fullscreen_button)

        # Mini player button
        self._mini_button = Gtk.Button.new_from_icon_name("view-dual-symbolic")
        self._mini_button.set_css_classes(["flat", "circular"])
        self._mini_button.set_tooltip_text("Mini reproductor (Ctrl+M)")
        self._mini_button.connect("clicked", lambda b: self._emit_toggle_mini())
        right_box.append(self._mini_button)

        self.append(right_box)

    def _on_play_pause(self):
        self._player.play_pause()

    def _on_waveform_seek(self, progress: float):
        pos = self._player.get_position()
        if pos and pos.duration > 0:
            seek_ns = int(progress * pos.duration)
            self._player.seek(seek_ns)

    def _on_volume_changed(self, scale, scroll, value):
        self._player.set_volume(value)
        self._update_volume_icon()

    def _on_volume_mute(self, button):
        if self._player.get_volume() > 0:
            self._prev_volume = self._player.get_volume()
            self._player.set_volume(0.0)
        else:
            self._player.set_volume(getattr(self, "_prev_volume", 0.8))
        self._volume_scale.set_value(self._player.get_volume())
        self._update_volume_icon()

    def _update_volume_icon(self):
        vol = self._player.get_volume()
        icon_name = "audio-volume-muted-symbolic"
        if vol > 0.5:
            icon_name = "audio-volume-high-symbolic"
        elif vol > 0.1:
            icon_name = "audio-volume-medium-symbolic"
        elif vol > 0:
            icon_name = "audio-volume-low-symbolic"
        self._vol_button.set_icon_name(icon_name)

    def _on_repeat_toggled(self, button):
        current = self._player.get_repeat_mode()
        img = button.get_child()
        if current == RepeatMode.NONE:
            self._player.set_repeat_mode(RepeatMode.ALL)
            if isinstance(img, Gtk.Image):
                img.set_from_icon_name("media-playlist-repeat-symbolic")
            button.set_tooltip_text("Repetir todo")
        elif current == RepeatMode.ALL:
            self._player.set_repeat_mode(RepeatMode.ONE)
            if isinstance(img, Gtk.Image):
                img.set_from_icon_name("media-playlist-repeat-song-symbolic")
            button.set_tooltip_text("Repetir una")
        else:
            self._player.set_repeat_mode(RepeatMode.NONE)
            button.set_active(False)
            if isinstance(img, Gtk.Image):
                img.set_from_icon_name("media-playlist-repeat-symbolic")
            button.set_tooltip_text("Modo repetición")

    def _on_shuffle_toggled(self, button):
        self._player.toggle_shuffle()

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
            self._play_button.set_tooltip_text("Pausar (Space)")
        elif state == PlayerState.PAUSED:
            self._play_button.set_icon_name("media-playback-start-symbolic")
            self._play_button.set_tooltip_text("Reproducir (Space)")
        else:
            self._play_button.set_icon_name("media-playback-start-symbolic")
            self._play_button.set_tooltip_text("Reproducir (Space)")
            self._progress_scale.set_progress(0.0)
            self._progress_scale.set_sensitive(False)

    def set_artwork_from_path(self, art_path: Optional[Path]):
        if art_path and art_path.exists():
            texture = Gdk.Texture.new_from_filename(str(art_path))
            self._art_image.set_paintable(texture)
            try:
                from soundwave.library.color_extract import get_theme_colors_from_art
                _, accent_hex, _ = get_theme_colors_from_art(art_path)
                r, g, b = hex_to_rgb(accent_hex)
                self._progress_scale.set_accent_color(r, g, b)
            except Exception:
                pass
        else:
            self._art_image.set_paintable(None)
            self._progress_scale.reset_colors()

    def _on_song_changed(self, song: Optional[Song]):
        if song is None:
            self._title_label.set_label("Sin reproducción")
            self._artist_label.set_label("")
            self._progress_scale.set_sensitive(False)
            self._progress_scale.set_waveform([])
            self._progress_scale.set_progress(0.0)
            self._art_image.set_paintable(None)
            return

        self._title_label.set_label(song.display_title)
        self._artist_label.set_label(song.display_artist)
        self._progress_scale.set_sensitive(True)
        self._progress_scale.set_progress(0.0)

        # Handle waveform display
        if song.waveform_data:
            try:
                wave = json.loads(song.waveform_data)
                self._progress_scale.set_waveform(wave)
            except Exception:
                self._progress_scale.set_waveform([])
                self._trigger_waveform_generation(song)
        else:
            self._progress_scale.set_waveform([])
            self._trigger_waveform_generation(song)

    def _trigger_waveform_generation(self, song: Song):
        if not self._db:
            return

        def run_generation():
            from soundwave.library.waveform_helper import generate_waveform_data
            wave = generate_waveform_data(song.filepath, num_points=150)
            if wave:
                try:
                    local_db = Database(self._db.db_path)
                    local_db.update_song_waveform(song.id, json.dumps(wave))
                    local_db.close()
                except Exception as e:
                    print(f"Error caching waveform to db: {e}")
                GLib.idle_add(self._on_waveform_generated, song.id, wave)

        threading.Thread(target=run_generation, daemon=True).start()

    def _on_waveform_generated(self, song_id: int, wave: list[float]):
        current_song = self._player.get_current_song()
        if current_song and current_song.id == song_id:
            self._progress_scale.set_waveform(wave)

    def _on_position_changed(self, pos: PlaybackPosition):
        self._time_label.set_label(self._format_time(pos.current))
        self._duration_label.set_label(self._format_time(pos.duration))
        if pos.duration > 0:
            self._progress_scale.set_progress(pos.current / pos.duration)

    # --- Callbacks ---
    def connect_toggle_mini(self, cb: ToggleMiniCallback):
        self._toggle_mini_cbs.append(cb)

    def connect_show_equalizer(self, cb: ShowEqualizerCallback):
        self._show_eq_cbs.append(cb)

    def connect_navigate_album(self, cb: NavigateAlbumCallback):
        self._navigate_album_cbs.append(cb)

    def connect_toggle_lyrics(self, cb: ToggleLyricsCallback):
        self._toggle_lyrics_cbs.append(cb)

    def connect_toggle_fullscreen(self, cb: Callable):
        self._toggle_fullscreen_cbs.append(cb)

    def connect_toggle_sidebar(self, cb: Callable):
        self._toggle_sidebar_cbs.append(cb)

    def _emit_navigate_album(self):
        for cb in self._navigate_album_cbs:
            cb()

    def _emit_toggle_mini(self):
        for cb in self._toggle_mini_cbs:
            cb()

    def _emit_show_equalizer(self):
        for cb in self._show_eq_cbs:
            cb()

    def _emit_toggle_lyrics(self):
        for cb in self._toggle_lyrics_cbs:
            cb()

    def _emit_toggle_fullscreen(self):
        for cb in self._toggle_fullscreen_cbs:
            cb()

    def _emit_toggle_sidebar(self):
        for cb in self._toggle_sidebar_cbs:
            cb()

    def set_fullscreen_state(self, fullscreen: bool):
        if fullscreen:
            self._fullscreen_button.set_icon_name("view-restore-symbolic")
            self._fullscreen_button.set_tooltip_text("Salir de pantalla completa (F11)")
        else:
            self._fullscreen_button.set_icon_name("view-fullscreen-symbolic")
            self._fullscreen_button.set_tooltip_text("Pantalla completa (F11)")

    def set_sidebar_state(self, shown: bool):
        if shown:
            self._sidebar_button.set_icon_name("sidebar-hide-symbolic")
            self._sidebar_button.set_tooltip_text("Colapsar barra lateral")
        else:
            self._sidebar_button.set_icon_name("sidebar-show-symbolic")
            self._sidebar_button.set_tooltip_text("Mostrar barra lateral")

    def add_toast(self, toast: Adw.Toast):
        pass
