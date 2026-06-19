import os
from pathlib import Path

# Temporarily override XDG_CONFIG_HOME during GTK initialization to bypass
# global custom GTK themes (like Orchis-Grey-Dark) that override Adwaita and block light/dark switching.
original_xdg_config = os.environ.get("XDG_CONFIG_HOME")
os.environ["XDG_CONFIG_HOME"] = "/nonexistent_dummy_path"

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Adw, GLib, Gio

# Restore original XDG_CONFIG_HOME so other modules (like config.py) can resolve user configuration paths.
if original_xdg_config is not None:
    os.environ["XDG_CONFIG_HOME"] = original_xdg_config
else:
    os.environ.pop("XDG_CONFIG_HOME", None)

import sys

from typing import Optional

from soundwave.library.config import load_settings, apply_theme
from soundwave.library.database import Database
from soundwave.library.lastfm import LastFmScrobbler
from soundwave.player.engine import Player, PlayerState
from soundwave.ui.window import SoundwaveWindow
from soundwave.core.plugin_manager import PluginManager

# Re-override XDG_CONFIG_HOME to a dummy path for the rest of the application lifetime
# so GTK never loads the custom gtk.css stylesheet during window realization or theme reloads.
os.environ["XDG_CONFIG_HOME"] = "/nonexistent_dummy_path"


APP_ID = "io.github.manuelprz.Soundwave"


class SoundwaveApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self._db: Optional[Database] = None
        self._player: Optional[Player] = None
        self._window: Optional[SoundwaveWindow] = None
        self._lastfm: Optional[LastFmScrobbler] = None
        self._mpris: Optional[object] = None
        self._plugin_manager: Optional[PluginManager] = None

    def do_activate(self):
        if self._window:
            self._window.present()
            return

        # Load and apply theme settings on startup
        settings = load_settings()
        theme = settings.get("theme", "system")
        apply_theme(theme)

        self._db = Database()
        self._player = Player()
        self._lastfm = LastFmScrobbler()

        self._window = SoundwaveWindow(self, self._db, self._player)
        self._window.set_lastfm(self._lastfm)

        # Initialize and load plugins
        self._plugin_manager = PluginManager(self, self._player, self._db, self._window)
        self._plugin_manager.load_plugins()

        # Start MPRIS
        try:
            from soundwave.player.mpris import MprisService
            self._mpris = MprisService(self._player, raise_callback=lambda: self._window.present())
        except Exception as e:
            print(f"MPRIS no disponible: {e}", file=sys.stderr)

        # GLib timeout for scrobbling
        GLib.timeout_add_seconds(30, self._check_scrobble)

        self._window.present()

    def do_command_line(self, command_line: Gio.ApplicationCommandLine):
        options = command_line.get_options_dict()
        self.activate()
        return 0

    def _check_scrobble(self) -> bool:
        if not self._lastfm or not self._lastfm.connected:
            return True
        song = self._player.get_current_song()
        state = self._player.get_state()
        if song and state == PlayerState.PLAYING:
            pos = self._player.get_position()
            if pos and pos.duration_seconds > 30:
                progress = pos.progress
                if progress >= 0.5:
                    self._lastfm.scrobble(
                        song.display_artist, song.display_title,
                        song.display_album, int(song.duration)
                    )
        return True

    def do_shutdown(self):
        if self._plugin_manager:
            self._plugin_manager.shutdown()
        if self._player:
            self._player.destroy()
        if self._db:
            self._db.close()
        Gio.Application.do_shutdown(self)


def main():
    app = SoundwaveApp()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)


if __name__ == "__main__":
    main()
