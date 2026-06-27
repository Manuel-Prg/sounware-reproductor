import os
from pathlib import Path

# Temporarily override XDG_CONFIG_HOME during GTK initialization to bypass
# global custom GTK themes (like Orchis-Grey-Dark) that override Adwaita and block light/dark switching.
original_xdg_config = os.environ.get("XDG_CONFIG_HOME")
os.environ["XDG_CONFIG_HOME"] = "/nonexistent_dummy_path"

import gi
gi.require_version("cairo", "1.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Adw, GLib, Gio, Gdk
import gi.repository.cairo

# Restore original XDG_CONFIG_HOME so other modules (like config.py) can resolve user configuration paths.
if original_xdg_config is not None:
    os.environ["XDG_CONFIG_HOME"] = original_xdg_config
else:
    os.environ.pop("XDG_CONFIG_HOME", None)

import sys

from typing import Optional

from soundwave.library.config.config import load_settings, apply_theme
from soundwave.library.database.database import Database
from soundwave.library.services.lastfm import LastFmScrobbler
from soundwave.player.engine import Player, PlayerState
from soundwave.ui.window.window import SoundwaveWindow
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

        # Load and apply theme settings on startup (fast operation)
        settings = load_settings()
        theme = settings.get("theme", "system")
        apply_theme(theme)

        # Force icon theme to Adwaita and lock it to prevent KDE Plasma from overriding it
        try:
            gtk_settings = Gtk.Settings.get_default()
            if gtk_settings:
                gtk_settings.set_property("gtk-icon-theme-name", "Adwaita")
                gtk_settings.connect("notify::gtk-icon-theme-name", lambda s, p: s.set_property("gtk-icon-theme-name", "Adwaita"))
        except Exception as e:
            print(f"Error locking icon theme: {e}")

        # Add custom icon search path to ensure we have our bundled icons across all distributions
        try:
            icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            resources_dir = os.path.join(os.path.dirname(__file__), "resources", "icons")
            if os.path.exists(resources_dir):
                icon_theme.add_search_path(resources_dir)
        except Exception as e:
            print(f"Error loading custom icons: {e}")

        # Initialize core components synchronously
        self._db = Database()
        self._player = Player()
        self._lastfm = LastFmScrobbler()

        # Create window immediately
        self._window = SoundwaveWindow(self, self._db, self._player)
        self._window.set_lastfm(self._lastfm)

        # Present window first for fast startup
        self._window.present()

        # Defer heavy initialization to after window is shown
        GLib.idle_add(self._initialize_deferred)

    def _initialize_deferred(self):
        """Initialize heavy components after window is shown"""
        assert self._player is not None
        assert self._window is not None

        # Initialize and load plugins (deferred)
        self._plugin_manager = PluginManager(self, self._player, self._db, self._window)
        self._plugin_manager.load_plugins()

        # Start MPRIS (deferred)
        try:
            from soundwave.player.mpris import MprisService
            self._mpris = MprisService(self._player, raise_callback=lambda: self._window.present())
        except Exception as e:
            print(f"MPRIS no disponible: {e}", file=sys.stderr)

        # GLib timeout for scrobbling (deferred)
        GLib.timeout_add_seconds(30, self._check_scrobble)

        return False  # Don't call again

    def do_command_line(self, command_line: Gio.ApplicationCommandLine):
        options = command_line.get_options_dict()
        self.activate()
        return 0

    def _check_scrobble(self) -> bool:
        if not self._lastfm or not self._lastfm.connected:
            return True
        # pyrefly: ignore [missing-attribute]
        song = self._player.get_current_song()
        # pyrefly: ignore [missing-attribute]
        state = self._player.get_state()
        if song and state == PlayerState.PLAYING:
            # pyrefly: ignore [missing-attribute]
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
