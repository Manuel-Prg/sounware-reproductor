import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk, Pango

from pathlib import Path
from typing import Optional, Callable
import json
import threading

from soundwave.player.engine import Player, PlayerState, RepeatMode, PlaybackPosition
from soundwave.library.database.database import Song, Database
from soundwave.ui.components.utils import hex_to_rgb, format_time
from soundwave.ui.components.waveform_widgets import WaveformProgressBar, CAIRO_SUPPORTED


ToggleMiniCallback = Callable[[], None]
ShowEqualizerCallback = Callable[[], None]
ToggleLyricsCallback = Callable[[], None]
NavigateAlbumCallback = Callable[[], None]


class PlayerBar(Gtk.CenterBox):
    def __init__(self, player: Player, db: Optional[Database] = None, lastfm=None):
        super().__init__()
        self._player = player
        self._db = db
        self._lastfm = lastfm
        self._toggle_mini_cbs: list[ToggleMiniCallback] = []
        self._show_eq_cbs: list[ShowEqualizerCallback] = []
        self._toggle_lyrics_cbs: list[ToggleLyricsCallback] = []
        self._navigate_album_cbs: list[NavigateAlbumCallback] = []
        self._toggle_fullscreen_cbs: list[Callable] = []
        self._toggle_sidebar_cbs: list[Callable] = []
        self._is_loved = False

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
        left_box.set_valign(Gtk.Align.CENTER)

        self._art_image = Gtk.Image()
        self._art_image.set_pixel_size(56)
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
        self.set_start_widget(left_box)

        # Center: playback controls
        center_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        center_box.set_hexpand(True)
        center_box.set_halign(Gtk.Align.CENTER)
        center_box.set_valign(Gtk.Align.CENTER)

        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        controls_box.set_halign(Gtk.Align.CENTER)
        controls_box.set_valign(Gtk.Align.CENTER)

        self._prev_button = Gtk.Button.new_from_icon_name("media-skip-backward-symbolic")
        self._prev_button.set_css_classes(["flat", "circular"])
        self._prev_button.set_valign(Gtk.Align.CENTER)
        self._prev_button.connect("clicked", lambda b: self._player.previous())
        self._prev_button.set_tooltip_text("Anterior (Ctrl+Left)")
        controls_box.append(self._prev_button)

        self._play_button = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        self._play_button.set_css_classes(["play-button-main", "circular"])
        self._play_button.set_size_request(44, 44)
        self._play_button.set_valign(Gtk.Align.CENTER)
        self._play_button.connect("clicked", lambda b: self._on_play_pause())
        self._play_button.set_tooltip_text("Reproducir/Pausar (Space)")
        controls_box.append(self._play_button)

        self._next_button = Gtk.Button.new_from_icon_name("media-skip-forward-symbolic")
        self._next_button.set_css_classes(["flat", "circular"])
        self._next_button.set_valign(Gtk.Align.CENTER)
        self._next_button.connect("clicked", lambda b: self._player.next())
        self._next_button.set_tooltip_text("Siguiente (Ctrl+Right)")
        controls_box.append(self._next_button)

        center_box.append(controls_box)

        # Progress bar
        progress_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        progress_box.set_halign(Gtk.Align.CENTER)
        progress_box.set_valign(Gtk.Align.CENTER)
        progress_box.set_size_request(400, -1)

        self._time_label = Gtk.Label(label="0:00")
        self._time_label.add_css_class("caption")
        self._time_label.set_valign(Gtk.Align.CENTER)
        progress_box.append(self._time_label)

        self._progress_scale = WaveformProgressBar(seek_callback=self._on_waveform_seek)
        self._progress_scale.set_size_request(300, 24)
        self._progress_scale.set_hexpand(True)
        self._progress_scale.set_valign(Gtk.Align.CENTER)
        self._progress_scale.set_sensitive(False)
        progress_box.append(self._progress_scale)

        self._duration_label = Gtk.Label(label="0:00")
        self._duration_label.add_css_class("caption")
        self._duration_label.set_valign(Gtk.Align.CENTER)
        progress_box.append(self._duration_label)

        center_box.append(progress_box)
        self.set_center_widget(center_box)

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

        # Love button (Last.fm)
        self._love_button = Gtk.ToggleButton()
        self._love_button.set_child(Gtk.Image.new_from_icon_name("non-starred-symbolic"))
        self._love_button.set_css_classes(["flat", "circular"])
        self._love_button.set_tooltip_text("Favorito (Last.fm)")
        self._love_button.set_visible(False)  # Hidden until connected to Last.fm
        self._love_button.connect("toggled", self._on_love_toggled)
        right_box.append(self._love_button)

        # Equalizer button
        self._eq_button = Gtk.Button.new_from_icon_name("multimedia-equalizer-symbolic")
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

        self.set_end_widget(right_box)

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

    def _on_love_toggled(self, button):
        """Handle love/unlove track for Last.fm"""
        if not self._lastfm or not self._lastfm.connected:
            button.set_active(False)
            return

        song = self._player.get_current_song()
        if not song:
            button.set_active(False)
            return

        def toggle_love():
            if button.get_active():
                success = self._lastfm.love_track(song.display_artist, song.display_title)
                if success:
                    self._is_loved = True
                    GLib.idle_add(self._update_love_button_icon, True)
                    GLib.idle_add(self._show_love_toast, "Canción añadida a favoritos")
                else:
                    GLib.idle_add(button.set_active, False)
            else:
                success = self._lastfm.unlove_track(song.display_artist, song.display_title)
                if success:
                    self._is_loved = False
                    GLib.idle_add(self._update_love_button_icon, False)
                    GLib.idle_add(self._show_love_toast, "Canción eliminada de favoritos")
                else:
                    GLib.idle_add(button.set_active, True)

        import threading
        threading.Thread(target=toggle_love, daemon=True).start()

    def _update_love_button_icon(self, loved: bool):
        """Update the love button icon based on state"""
        img = self._love_button.get_child()
        if isinstance(img, Gtk.Image):
            if loved:
                img.set_from_icon_name("starred-symbolic")
                self._love_button.set_tooltip_text("Eliminar de favoritos")
            else:
                img.set_from_icon_name("non-starred-symbolic")
                self._love_button.set_tooltip_text("Añadir a favoritos")

    def _show_love_toast(self, message: str):
        """Show a toast message for love action"""
        # This would need to be connected to the window's toast overlay
        # For now, we'll just print it
        print(f"[Last.fm] {message}")

    def set_lastfm(self, lastfm):
        """Set the Last.fm instance and update UI"""
        self._lastfm = lastfm
        if lastfm and lastfm.connected:
            self._love_button.set_visible(True)
        else:
            self._love_button.set_visible(False)

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
            self._art_image.set_from_paintable(texture)
            try:
                from soundwave.library.metadata.color_extract import get_theme_colors_from_art
                _, accent_hex, _ = get_theme_colors_from_art(art_path)
                r, g, b = hex_to_rgb(accent_hex)
                self._progress_scale.set_accent_color(r, g, b)
            except Exception:
                pass
        else:
            self._art_image.set_from_paintable(None)
            self._progress_scale.reset_colors()

    def _on_song_changed(self, song: Optional[Song]):
        if song is None:
            self._title_label.set_label("Sin reproducción")
            self._artist_label.set_label("")
            self._progress_scale.set_sensitive(False)
            self._progress_scale.set_waveform([])
            self._progress_scale.set_progress(0.0)
            self._art_image.set_from_paintable(None)
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
            from soundwave.library.utils.waveform_helper import generate_waveform_data
            wave = generate_waveform_data(song.filepath, num_points=150)
            if wave:
                try:
                    local_db = Database(self._db.db_path)
                    # pyrefly: ignore [bad-argument-type]
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
        self._time_label.set_label(format_time(pos.current))
        self._duration_label.set_label(format_time(pos.duration))
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
