import dbus
import dbus.service
import dbus.mainloop.glib
from dbus.mainloop.glib import DBusGMainLoop

from gi.repository import GLib
from typing import Optional

from soundwave.player.engine import Player, PlayerState, PlaybackPosition


MPRIS_BUS_NAME = "org.mpris.MediaPlayer2.soundwave"
MPRIS_PLAYER_PATH = "/org/mpris/MediaPlayer2"
MPRIS_PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
MPRIS_ROOT_IFACE = "org.mpris.MediaPlayer2"
MPRIS_TRACKLIST_IFACE = "org.mpris.MediaPlayer2.TrackList"


class MprisService(dbus.service.Object):
    def __init__(self, player: Player):
        DBusGMainLoop(set_as_default=True)
        self._player = player
        self._bus = dbus.SessionBus()

        bus_name = dbus.service.BusName(MPRIS_BUS_NAME, bus=self._bus)

        super().__init__(bus_name, MPRIS_PLAYER_PATH)

        self._properties = {
            MPRIS_ROOT_IFACE: {
                "CanQuit": True,
                "CanRaise": True,
                "HasTrackList": True,
                "Identity": "Soundwave",
                "DesktopEntry": "soundwave",
                "SupportedUriSchemes": dbus.Array(["file"], signature="s"),
                "SupportedMimeTypes": dbus.Array(
                    ["audio/mpeg", "audio/flac", "audio/ogg", "audio/x-m4a",
                     "audio/wav", "audio/aac"],
                    signature="s"
                ),
            },
            MPRIS_PLAYER_IFACE: {
                "PlaybackStatus": "Stopped",
                "LoopStatus": "None",
                "Rate": 1.0,
                "Shuffle": False,
                "Metadata": dbus.Dictionary({}, signature="sv"),
                "Volume": 1.0,
                "Position": dbus.Int64(0),
                "MinimumRate": 1.0,
                "MaximumRate": 1.0,
                "CanGoNext": True,
                "CanGoPrevious": True,
                "CanPlay": True,
                "CanPause": True,
                "CanSeek": True,
                "CanControl": True,
            },
        }

        self._player.connect_state(self._on_state_changed)
        self._player.connect_song(self._on_song_changed)
        self._player.connect_position(self._on_position_changed)

    # --- org.mpris.MediaPlayer2 ---

    @dbus.service.method(MPRIS_ROOT_IFACE)
    def Quit(self):
        GLib.idle_add(lambda: self._player.destroy())

    @dbus.service.method(MPRIS_ROOT_IFACE)
    def Raise(self):
        pass

    # --- org.mpris.MediaPlayer2.Player ---

    @dbus.service.method(MPRIS_PLAYER_IFACE)
    def Next(self):
        self._player.next()

    @dbus.service.method(MPRIS_PLAYER_IFACE)
    def Previous(self):
        self._player.previous()

    @dbus.service.method(MPRIS_PLAYER_IFACE)
    def Pause(self):
        if self._player.get_state() == PlayerState.PLAYING:
            self._player.play_pause()

    @dbus.service.method(MPRIS_PLAYER_IFACE)
    def PlayPause(self):
        self._player.play_pause()

    @dbus.service.method(MPRIS_PLAYER_IFACE)
    def Stop(self):
        self._player.stop()

    @dbus.service.method(MPRIS_PLAYER_IFACE)
    def Play(self):
        state = self._player.get_state()
        if state == PlayerState.PAUSED:
            self._player.play_pause()
        elif state == PlayerState.STOPPED:
            self._player.play_pause()

    @dbus.service.method(MPRIS_PLAYER_IFACE)
    def Seek(self, offset: dbus.Int64):
        pos = self._player.get_position()
        if pos:
            new_pos = max(0, pos.current + int(offset))
            self._player.seek(new_pos)

    @dbus.service.method(MPRIS_PLAYER_IFACE)
    def SetPosition(self, track_id: dbus.ObjectPath, position: dbus.Int64):
        self._player.seek(int(position))

    @dbus.service.method(MPRIS_PLAYER_IFACE)
    def OpenUri(self, uri: str):
        pass

    # --- Properties ---

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="ss",
                          out_signature="v")
    def Get(self, interface: str, prop: str):
        return self._properties.get(interface, {}).get(prop)

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="s",
                          out_signature="a{sv}")
    def GetAll(self, interface: str):
        props = self._properties.get(interface, {})
        if interface == MPRIS_PLAYER_IFACE:
            self._update_player_properties()
        return props

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="ssv")
    def Set(self, interface: str, prop: str, value):
        if interface == MPRIS_PLAYER_IFACE:
            if prop == "Volume":
                self._player.set_volume(float(value))
                self._properties[MPRIS_PLAYER_IFACE]["Volume"] = value
                self._emit_properties_changed(MPRIS_PLAYER_IFACE, {prop: value}, [])
            elif prop == "LoopStatus":
                status_map = {"None": "none", "Playlist": "all", "Track": "one"}
                from soundwave.player.engine import RepeatMode
                mode_map = {"none": RepeatMode.NONE, "all": RepeatMode.ALL, "one": RepeatMode.ONE}
                self._player.set_repeat_mode(mode_map.get(str(value), RepeatMode.NONE))
                self._properties[MPRIS_PLAYER_IFACE][prop] = value
                self._emit_properties_changed(MPRIS_PLAYER_IFACE, {prop: value}, [])
            elif prop == "Shuffle":
                self._player.toggle_shuffle()
                val = bool(value)
                self._properties[MPRIS_PLAYER_IFACE][prop] = val
                self._emit_properties_changed(MPRIS_PLAYER_IFACE, {prop: val}, [])

    @dbus.service.signal(dbus.PROPERTIES_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass

    # --- Internal ---

    def _update_player_properties(self):
        props = self._properties[MPRIS_PLAYER_IFACE]
        state = self._player.get_state()
        props["PlaybackStatus"] = {
            PlayerState.PLAYING: "Playing",
            PlayerState.PAUSED: "Paused",
            PlayerState.STOPPED: "Stopped",
        }.get(state, "Stopped")

        from soundwave.player.engine import RepeatMode
        rm = self._player.get_repeat_mode()
        props["LoopStatus"] = {
            RepeatMode.NONE: "None",
            RepeatMode.ALL: "Playlist",
            RepeatMode.ONE: "Track",
        }.get(rm, "None")

        props["Shuffle"] = self._player.get_shuffle()
        props["Volume"] = dbus.Double(self._player.get_volume())

        song = self._player.get_current_song()
        if song:
            props["Metadata"] = self._song_to_metadata(song)
            props["CanPlay"] = True
            props["CanPause"] = True
        else:
            props["Metadata"] = dbus.Dictionary({}, signature="sv")

        pos = self._player.get_position()
        if pos:
            props["Position"] = dbus.Int64(pos.current)

    def _song_to_metadata(self, song) -> dbus.Dictionary:
        meta = dbus.Dictionary(signature="sv")
        meta["mpris:trackid"] = dbus.ObjectPath(
            f"/org/mpris/MediaPlayer2/soundwave/track/{song.id or 0}"
        )
        meta["mpris:length"] = dbus.Int64(int(song.duration * 1e9))
        meta["xesam:title"] = song.display_title
        meta["xesam:artist"] = dbus.Array([song.display_artist], signature="s")
        meta["xesam:album"] = song.display_album
        if song.track_number:
            meta["xesam:trackNumber"] = dbus.Int32(song.track_number)
        if song.genre:
            meta["xesam:genre"] = dbus.Array([song.genre], signature="s")
        if song.year:
            meta["xesam:contentCreated"] = str(song.year)
        meta["xesam:url"] = song.filepath
        return meta

    def _emit_properties_changed(self, interface, changed, invalidated):
        self.PropertiesChanged(interface, changed, invalidated)

    def _on_state_changed(self, state):
        self._update_player_properties()
        props = self._properties[MPRIS_PLAYER_IFACE]
        changed = {"PlaybackStatus": props["PlaybackStatus"]}
        self._emit_properties_changed(MPRIS_PLAYER_IFACE, changed, [])

    def _on_song_changed(self, song):
        self._update_player_properties()
        props = self._properties[MPRIS_PLAYER_IFACE]
        changed = {
            "Metadata": props["Metadata"],
            "PlaybackStatus": props["PlaybackStatus"],
        }
        self._emit_properties_changed(MPRIS_PLAYER_IFACE, changed, [])

    def _on_position_changed(self, pos: PlaybackPosition):
        self._properties[MPRIS_PLAYER_IFACE]["Position"] = dbus.Int64(pos.current)
