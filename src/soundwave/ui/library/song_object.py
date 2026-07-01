"""SongObject — GObject wrapper around Song for use with Gio.ListStore / Gtk.ListView."""

import gi
gi.require_version("GObject", "2.0")
from gi.repository import GObject

from soundwave.library.database.database import Song


class SongObject(GObject.Object):
    """Thin GObject wrapper so Song instances can be stored in Gio.ListStore."""

    __gtype_name__ = "SoundwaveSongObject"

    def __init__(self, song: Song):
        super().__init__()
        self.song: Song = song
