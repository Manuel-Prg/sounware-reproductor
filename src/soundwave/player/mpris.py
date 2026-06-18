import dbus
import dbus.service
import dbus.mainloop.glib
from dbus.mainloop.glib import DBusGMainLoop

from gi.repository import GLib
from typing import Optional, Callable

from soundwave.player.engine import Player, PlayerState, PlaybackPosition


MPRIS_BUS_NAME = "org.mpris.MediaPlayer2.soundwave"
MPRIS_PLAYER_PATH = "/org/mpris/MediaPlayer2"
MPRIS_PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
MPRIS_ROOT_IFACE = "org.mpris.MediaPlayer2"


class MprisService(dbus.service.Object):
    def __init__(self, player: Player, raise_callback: Optional[Callable] = None):
        DBusGMainLoop(set_as_default=True)
        self._player = player
        # Callback para traer la ventana al frente cuando GNOME Shell lo pide
        self._raise_callback = raise_callback
        self._bus = dbus.SessionBus()

        bus_name = dbus.service.BusName(MPRIS_BUS_NAME, bus=self._bus)
        super().__init__(bus_name, MPRIS_PLAYER_PATH)

        self._properties = {
            MPRIS_ROOT_IFACE: {
                "CanQuit": True,
                "CanRaise": True,
                "HasTrackList": False,
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
                "Rate": dbus.Double(1.0),
                "Shuffle": False,
                "Metadata": dbus.Dictionary({}, signature="sv"),
                "Volume": dbus.Double(1.0),
                "Position": dbus.Int64(0),
                "MinimumRate": dbus.Double(1.0),
                "MaximumRate": dbus.Double(1.0),
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
        # FIX: antes era pass. Ahora llama al callback para traer la ventana al frente.
        # En window.py pasa: lambda: self.present()
        if self._raise_callback:
            GLib.idle_add(self._raise_callback)

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
        if state in (PlayerState.PAUSED, PlayerState.STOPPED):
            self._player.play_pause()

    @dbus.service.method(MPRIS_PLAYER_IFACE)
    def Seek(self, offset: dbus.Int64):
        pos = self._player.get_position()
        if pos:
            new_pos = max(0, pos.current + int(offset))
            self._player.seek(new_pos)
            # FIX: emitir Seeked para que GNOME Shell sincronice la barra de progreso
            self.Seeked(dbus.Int64(new_pos))

    @dbus.service.method(MPRIS_PLAYER_IFACE)
    def SetPosition(self, track_id: dbus.ObjectPath, position: dbus.Int64):
        pos_ns = int(position)
        self._player.seek(pos_ns)
        # FIX: igual aquí
        self.Seeked(dbus.Int64(pos_ns))

    @dbus.service.method(MPRIS_PLAYER_IFACE)
    def OpenUri(self, uri: str):
        pass

    # FIX: señal Seeked que faltaba completamente.
    # Sin esto, playerctld, GNOME Shell y KDE no sincronizan la posición tras seek.
    @dbus.service.signal(MPRIS_PLAYER_IFACE, signature="x")
    def Seeked(self, position: dbus.Int64):
        pass

    # --- Properties ---

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="ss", out_signature="v")
    def Get(self, interface: str, prop: str):
        if interface == MPRIS_PLAYER_IFACE:
            self._sync_player_properties()
        return self._properties.get(interface, {}).get(prop)

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface: str):
        if interface == MPRIS_PLAYER_IFACE:
            self._sync_player_properties()
        return self._properties.get(interface, {})

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="ssv")
    def Set(self, interface: str, prop: str, value):
        if interface != MPRIS_PLAYER_IFACE:
            return
        if prop == "Volume":
            v = max(0.0, min(1.0, float(value)))
            self._player.set_volume(v)
            self._properties[MPRIS_PLAYER_IFACE]["Volume"] = dbus.Double(v)
            self._emit_changed(MPRIS_PLAYER_IFACE, {"Volume": dbus.Double(v)})
        elif prop == "LoopStatus":
            from soundwave.player.engine import RepeatMode
            mode_map = {"None": RepeatMode.NONE, "Playlist": RepeatMode.ALL, "Track": RepeatMode.ONE}
            self._player.set_repeat_mode(mode_map.get(str(value), RepeatMode.NONE))
            self._properties[MPRIS_PLAYER_IFACE]["LoopStatus"] = value
            self._emit_changed(MPRIS_PLAYER_IFACE, {"LoopStatus": value})
        elif prop == "Shuffle":
            val = bool(value)
            # Sincronizar con el estado real en lugar de toggle ciego
            if self._player.get_shuffle() != val:
                self._player.toggle_shuffle()
            self._properties[MPRIS_PLAYER_IFACE]["Shuffle"] = val
            self._emit_changed(MPRIS_PLAYER_IFACE, {"Shuffle": val})

    @dbus.service.signal(dbus.PROPERTIES_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass

    # --- Internal ---

    def _sync_player_properties(self):
        """Sincroniza el dict interno con el estado real del player."""
        props = self._properties[MPRIS_PLAYER_IFACE]

        state = self._player.get_state()
        props["PlaybackStatus"] = {
            PlayerState.PLAYING: "Playing",
            PlayerState.PAUSED:  "Paused",
            PlayerState.STOPPED: "Stopped",
        }.get(state, "Stopped")

        from soundwave.player.engine import RepeatMode
        rm = self._player.get_repeat_mode()
        props["LoopStatus"] = {
            RepeatMode.NONE: "None",
            RepeatMode.ALL:  "Playlist",
            RepeatMode.ONE:  "Track",
        }.get(rm, "None")

        props["Shuffle"] = self._player.get_shuffle()
        props["Volume"]  = dbus.Double(self._player.get_volume())

        song = self._player.get_current_song()
        props["Metadata"] = self._song_to_metadata(song) if song else dbus.Dictionary({}, signature="sv")
        props["CanPlay"]  = True
        props["CanPause"] = True

        pos = self._player.get_position()
        if pos:
            props["Position"] = dbus.Int64(pos.current)

    def _song_to_metadata(self, song) -> dbus.Dictionary:
        meta = dbus.Dictionary(signature="sv")
        meta["mpris:trackid"] = dbus.ObjectPath(
            f"/org/mpris/MediaPlayer2/soundwave/track/{song.id or 0}"
        )
        meta["mpris:length"]   = dbus.Int64(int(song.duration * 1_000_000))  # FIX: era *1e9 (ns), MPRIS usa microsegundos
        meta["xesam:title"]    = dbus.String(song.display_title)
        meta["xesam:artist"]   = dbus.Array([song.display_artist], signature="s")
        meta["xesam:album"]    = dbus.String(song.display_album)
        if song.track_number:
            meta["xesam:trackNumber"] = dbus.Int32(song.track_number)
        if song.genre:
            meta["xesam:genre"] = dbus.Array([song.genre], signature="s")
        if song.year:
            meta["xesam:contentCreated"] = dbus.String(str(song.year))
        meta["xesam:url"] = dbus.String(song.filepath)

        # Carátula: busca imagen embebida exportada a /tmp, o carpeta del archivo
        art_url = self._resolve_art_url(song)
        if art_url:
            meta["mpris:artUrl"] = dbus.String(art_url)

        return meta

    def _resolve_art_url(self, song) -> Optional[str]:
        """
        Intenta localizar la carátula del álbum en este orden:
        1. /tmp/soundwave_art/<song_id>.jpg  (exportada por el scanner)
        2. cover.jpg / folder.jpg / artwork.jpg junto al archivo de audio
        3. Cualquier .jpg/.png en la misma carpeta
        """
        import os
        from pathlib import Path

        # 1. Carátula exportada por el library scanner
        cached = Path(f"/tmp/soundwave_art/{song.id}.jpg")
        if cached.exists():
            return cached.as_uri()

        # 2 y 3. Buscar en la carpeta del archivo
        audio_dir = Path(song.filepath).parent
        for name in ("cover.jpg", "cover.png", "folder.jpg", "folder.png",
                     "artwork.jpg", "artwork.png", "front.jpg", "front.png"):
            candidate = audio_dir / name
            if candidate.exists():
                return candidate.as_uri()

        # Cualquier imagen en la carpeta (primer resultado)
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            matches = list(audio_dir.glob(ext))
            if matches:
                return matches[0].as_uri()

        return None

    def _emit_changed(self, interface: str, changed: dict, invalidated: list = None):
        self.PropertiesChanged(interface, changed, invalidated or [])

    # --- Callbacks del player ---

    def _on_state_changed(self, state: PlayerState):
        status_map = {
            PlayerState.PLAYING: "Playing",
            PlayerState.PAUSED:  "Paused",
            PlayerState.STOPPED: "Stopped",
        }
        status = status_map.get(state, "Stopped")
        self._properties[MPRIS_PLAYER_IFACE]["PlaybackStatus"] = status
        self._emit_changed(MPRIS_PLAYER_IFACE, {"PlaybackStatus": status})

    def _on_song_changed(self, song):
        self._sync_player_properties()
        props = self._properties[MPRIS_PLAYER_IFACE]
        self._emit_changed(MPRIS_PLAYER_IFACE, {
            "Metadata":       props["Metadata"],
            "PlaybackStatus": props["PlaybackStatus"],
            "CanPlay":        True,
            "CanPause":       True,
        })

    def _on_position_changed(self, pos: PlaybackPosition):
        # Solo actualiza el dict local; no emite PropertiesChanged para Position
        # porque según la spec MPRIS2 Position NO debe enviarse por PropertiesChanged,
        # se obtiene vía Get("Position") o se notifica solo con la señal Seeked.
        self._properties[MPRIS_PLAYER_IFACE]["Position"] = dbus.Int64(pos.current)