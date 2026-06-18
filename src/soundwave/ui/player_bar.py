import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk, Pango

from pathlib import Path
from typing import Optional, Callable

from soundwave.player.engine import Player, PlayerState, RepeatMode, PlaybackPosition
from soundwave.library.database import Song


ToggleMiniCallback = Callable[[], None]
ShowEqualizerCallback = Callable[[], None]
ToggleLyricsCallback = Callable[[], None]
NavigateAlbumCallback = Callable[[], None]


class PlayerBar(Gtk.Box):
    def __init__(self, player: Player):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._player = player
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
        self._art_image.set_tooltip_text("Ir al álbum")
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

        self._progress_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0.0, 100.0, 0.1
        )
        self._progress_scale.set_size_request(300, -1)
        self._progress_scale.set_draw_value(False)
        self._progress_scale.set_hexpand(True)
        self._progress_scale.connect("change-value", self._on_seek)
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

    def _on_seek(self, scale, scroll, value):
        pos = self._player.get_position()
        if pos and pos.duration > 0:
            seek_ns = int((value / 100.0) * pos.duration)
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
            self._progress_scale.set_value(0)
            self._progress_scale.set_sensitive(False)

    def set_artwork_from_path(self, art_path: Optional[Path]):
        if art_path and art_path.exists():
            texture = Gdk.Texture.new_from_filename(str(art_path))
            self._art_image.set_paintable(texture)
        else:
            self._art_image.set_paintable(None)

    def _on_song_changed(self, song: Optional[Song]):
        if song is None:
            self._title_label.set_label("Sin reproducción")
            self._artist_label.set_label("")
            self._progress_scale.set_sensitive(False)
            self._art_image.set_paintable(None)
            return

        self._title_label.set_label(song.display_title)
        self._artist_label.set_label(song.display_artist)
        self._progress_scale.set_sensitive(True)

    def _on_position_changed(self, pos: PlaybackPosition):
        self._time_label.set_label(self._format_time(pos.current))
        self._duration_label.set_label(self._format_time(pos.duration))
        if pos.duration > 0:
            self._progress_scale.set_value((pos.current / pos.duration) * 100)

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
