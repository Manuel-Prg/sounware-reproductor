import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk

from pathlib import Path
from typing import Optional, Callable

from soundwave.player.engine import Player, PlayerState, RepeatMode, PlaybackPosition
from soundwave.library.database.database import Song
from soundwave.library.metadata.color_extract import get_theme_colors_from_art
from soundwave.ui.components.utils import format_time

from soundwave.ui.player.mini_player.styles import load_base_css, update_theme_css, reset_theme
from soundwave.ui.player.mini_player.ui import build_mini_player_ui

RestoreWindowCallback = Callable[[], None]


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

        build_mini_player_ui(
            self,
            self._player,
            on_seek_callback=self._on_seek,
            on_repeat_callback=self._on_repeat_clicked,
            on_restore_callback=self._emit_restore
        )

        load_base_css(self.get_display())
        self._update_repeat_button_ui()

        self._player.connect_state(self._on_state_changed)
        self._player.connect_song(self._on_song_changed)
        self._player.connect_position(self._on_position_changed)

    def _on_seek(self, scale, scroll, value):
        pos = self._player.get_position()
        if pos and pos.duration > 0:
            seek_ns = int((value / 100.0) * pos.duration)
            self._player.seek(seek_ns)

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
            update_theme_css(self.get_display(), self._theme_provider, bg, accent, fg)
        else:
            self._art_image.set_paintable(None)
            reset_theme(self.get_display(), self._theme_provider)

    def _on_song_changed(self, song: Optional[Song]):
        self._update_repeat_button_ui()
        if song is None:
            self._title_label.set_label("Soundwave")
            self._artist_label.set_label("Sin reproducción")
            self._art_image.set_paintable(None)
            reset_theme(self.get_display(), self._theme_provider)
            return
        self._title_label.set_label(song.display_title)
        self._artist_label.set_label(song.display_artist)

    def _on_position_changed(self, pos: PlaybackPosition):
        self._time_label.set_label(format_time(pos.current))
        self._duration_label.set_label(format_time(pos.duration))
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
            self._repeat_btn.add_css_class("media-player-repeat-inactive" if hasattr(self, "_repeat_btn") else "mini-player-repeat-inactive")
            # Wait, in original code:
            # self._repeat_btn.add_css_class("mini-player-repeat-inactive")
            # Let's fix that.
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
