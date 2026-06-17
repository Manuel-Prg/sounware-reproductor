import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Adw, GLib, Gio

import sys

from typing import Optional

from soundwave.library.database import Database
from soundwave.library.lastfm import LastFmScrobbler
from soundwave.player.engine import Player, PlayerState
from soundwave.ui.window import SoundwaveWindow


APP_ID = "io.github.soundwave.Soundwave"


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

    def do_activate(self):
        if self._window:
            self._window.present()
            return

        self._db = Database()
        self._player = Player()
        self._lastfm = LastFmScrobbler()

        self._window = SoundwaveWindow(self, self._db, self._player)
        self._window.set_lastfm(self._lastfm)

        # Start MPRIS
        try:
            from soundwave.player.mpris import MprisService
            self._mpris = MprisService(self._player)
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
