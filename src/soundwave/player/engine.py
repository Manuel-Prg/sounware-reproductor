import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

from typing import Optional, Callable
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import random

from soundwave.library.database import Song


class PlayerState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED  = "paused"


class RepeatMode(Enum):
    NONE = "none"
    ALL  = "all"
    ONE  = "one"


@dataclass
class PlaybackPosition:
    current:  int  # nanosegundos
    duration: int  # nanosegundos

    @property
    def current_seconds(self) -> float:
        return self.current / 1e9

    @property
    def duration_seconds(self) -> float:
        return self.duration / 1e9

    @property
    def progress(self) -> float:
        if self.duration == 0:
            return 0.0
        return min(1.0, self.current / self.duration)


StateChangeCallback = Callable[[PlayerState], None]
SongChangeCallback  = Callable[[Optional[Song]], None]
PositionCallback    = Callable[[PlaybackPosition], None]
EosCallback         = Callable[[], None]


class Player:
    def __init__(self):
        Gst.init(None)
        self._playbin:   Optional[Gst.Element] = None
        self._state      = PlayerState.STOPPED
        self._current_song: Optional[Song] = None
        self._queue:     list[Song] = []
        self._original_queue: list[Song] = []
        self._current_index: int    = -1
        self._volume:    float      = 1.0
        self._repeat_mode            = RepeatMode.NONE
        self._shuffle:   bool       = False
        self._equalizer: Optional[Gst.Element] = None
        
        # Cargar configuración del ecualizador y ReplayGain
        from soundwave.library.config import load_settings
        settings = load_settings()
        self._equalizer_bands: list[float]     = settings.get("equalizer_bands", [0.0] * 10)
        self._equalizer_enabled: bool          = settings.get("equalizer_enabled", True)
        self._replaygain_mode: str             = settings.get("replaygain_mode", "track")

        self._state_callbacks:    list[StateChangeCallback] = []
        self._song_callbacks:     list[SongChangeCallback]  = []
        self._position_callbacks: list[PositionCallback]    = []
        self._eos_callbacks:      list[EosCallback]         = []
        self._spectrum_callbacks: list[Callable[[list[float]], None]] = []

        self._position_timer: Optional[int] = None

        # Construir el pipeline UNA sola vez al inicio
        self._build_pipeline()

    # --- Pipeline (construir una sola vez) ---

    def _build_pipeline(self):
        """
        FIX: antes se destruía y recreaba el pipeline en cada play_file().
        Ahora se construye una vez. Para cambiar de canción basta con:
          1. set_state(NULL)  → libera el recurso actual
          2. set_property("uri", nuevo_uri)
          3. set_state(PLAYING)
        Esto elimina el glitch de audio entre canciones y es más eficiente.
        """
        self._playbin = Gst.ElementFactory.make("playbin3", "playbin")
        if self._playbin is None:
            # playbin3 no disponible (GStreamer < 1.18), usar playbin
            self._playbin = Gst.ElementFactory.make("playbin", "playbin")

        if self._playbin is None:
            raise RuntimeError("No se pudo crear playbin/playbin3. Verifica gstreamer1.0-plugins-base.")

        self._playbin.set_property("volume", self._volume)
        self._playbin.set_property("buffer-size", 4096)

        bus = self._playbin.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)

        self._playbin.connect("about-to-finish", self._on_about_to_finish)

        # Adjuntar e inicializar el ecualizador en el pipeline
        self._attach_equalizer()

    def _attach_equalizer(self):
        """Inserta el ecualizador y el espectro en el pipeline (llamar antes del primer play)."""
        if self._equalizer or not self._playbin:
            return
        eq = Gst.ElementFactory.make("equalizer-10bands", "equalizer")
        spec = Gst.ElementFactory.make("spectrum", "spectrum")

        if eq and spec:
            self._equalizer = eq
            self._spectrum = spec

            # Configure spectrum element
            spec.set_property("bands", 64)
            spec.set_property("threshold", -60)
            spec.set_property("post-messages", True)
            spec.set_property("message-magnitude", True)

            # Create filter bin to hold equalizer and spectrum
            filt_bin = Gst.Bin.new("audio-filter-bin")
            filt_bin.add(eq)
            filt_bin.add(spec)
            eq.link(spec)

            # Add ghost pads
            sink_pad = Gst.GhostPad.new("sink", eq.get_static_pad("sink"))
            filt_bin.add_pad(sink_pad)

            src_pad = Gst.GhostPad.new("src", spec.get_static_pad("src"))
            filt_bin.add_pad(src_pad)

            self._playbin.set_property("audio-filter", filt_bin)

            # Aplicar bandas iniciales teniendo en cuenta si está activado
            bands_to_apply = self._equalizer_bands if self._equalizer_enabled else [0.0] * 10
            for i, val in enumerate(bands_to_apply):
                try:
                    self._equalizer.set_property(f"band{i}", val)
                except Exception as e:
                    print(f"Error al aplicar banda {i}: {e}")
        elif eq:
            self._equalizer = eq
            self._playbin.set_property("audio-filter", self._equalizer)
            # Aplicar bandas iniciales teniendo en cuenta si está activado
            bands_to_apply = self._equalizer_bands if self._equalizer_enabled else [0.0] * 10
            for i, val in enumerate(bands_to_apply):
                try:
                    self._equalizer.set_property(f"band{i}", val)
                except Exception as e:
                    print(f"Error al aplicar banda {i}: {e}")

    # --- Public API ---

    def play_file(self, song: Song):
        """
        FIX: reutiliza el mismo playbin. Proceso correcto para cambiar URI:
          NULL → set uri → PLAYING
        """
        self._stop_position_timer()

        # Llevar a NULL libera el decoder anterior limpiamente
        self._playbin.set_state(Gst.State.NULL)
        self._playbin.set_property("uri", Path(song.filepath).resolve().as_uri())
        self._current_song = song

        # Aplicar ganancia de ReplayGain antes de reproducir
        self._apply_volume_with_gain()

        self._playbin.set_state(Gst.State.PLAYING)
        # No llamamos _set_state(PLAYING) aquí; lo hace _on_bus_message
        # cuando GStreamer confirma STATE_CHANGED → PLAYING, evitando doble emisión.

        self._start_position_timer()
        self._emit_song()

    def play_pause(self):
        if self._state == PlayerState.STOPPED and self._queue:
            self.play_index(self._current_index if self._current_index >= 0 else 0)
            return
        if self._state == PlayerState.PLAYING:
            self._playbin.set_state(Gst.State.PAUSED)
        elif self._state == PlayerState.PAUSED:
            self._playbin.set_state(Gst.State.PLAYING)

    def stop(self):
        self._stop_position_timer()
        if self._playbin:
            self._playbin.set_state(Gst.State.NULL)
        self._set_state(PlayerState.STOPPED)
        self._emit_position(PlaybackPosition(0, 0))

    def next(self):
        if not self._queue:
            return
        if self._repeat_mode == RepeatMode.ONE and self._current_song:
            self.play_file(self._current_song)
            return
        next_idx = self._current_index + 1
        if next_idx >= len(self._queue):
            if self._repeat_mode == RepeatMode.ALL:
                next_idx = 0
            else:
                self.stop()
                return
        self.play_index(next_idx)

    def previous(self):
        if not self._queue:
            return
        pos = self.get_position()
        if pos and pos.current_seconds > 3:
            self.seek(0)
            return
        prev_idx = self._current_index - 1
        if prev_idx < 0:
            prev_idx = len(self._queue) - 1 if self._repeat_mode == RepeatMode.ALL else 0
        self.play_index(prev_idx)

    def seek(self, position_ns: int):
        if self._playbin and self._state != PlayerState.STOPPED:
            self._playbin.seek_simple(
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                position_ns,
            )

    def seek_seconds(self, seconds: float):
        self.seek(int(seconds * 1e9))

    def set_volume(self, volume: float):
        self._volume = max(0.0, min(1.0, volume))
        self._apply_volume_with_gain()

    def get_volume(self) -> float:
        return self._volume

    def _apply_volume_with_gain(self):
        if not self._playbin:
            return
        
        factor = 1.0
        if self._current_song:
            mode = self._replaygain_mode

            if mode == "track":
                gain = getattr(self._current_song, "replaygain_track_gain", 0.0)
                if gain != 0.0:
                    factor = 10 ** (gain / 20.0)
            elif mode == "album":
                gain = getattr(self._current_song, "replaygain_album_gain", 0.0)
                if gain == 0.0:
                    gain = getattr(self._current_song, "replaygain_track_gain", 0.0)
                if gain != 0.0:
                    factor = 10 ** (gain / 20.0)

        # GStreamer acepta factores lineales superiores a 1.0 para amplificación
        self._playbin.set_property("volume", self._volume * factor)

    # --- Queue ---

    def set_queue(self, songs: list[Song], start_index: int = 0):
        self._original_queue = list(songs)
        if self._shuffle:
            shuffled = list(songs)
            if shuffled and 0 <= start_index < len(shuffled):
                current_song = shuffled.pop(start_index)
                random.shuffle(shuffled)
                shuffled.insert(0, current_song)
                self._queue = shuffled
                self._current_index = 0
            else:
                self._queue = shuffled
                self._current_index = start_index if self._queue else -1
        else:
            self._queue = list(songs)
            self._current_index = start_index if self._queue else -1

        if self._queue and 0 <= self._current_index < len(self._queue):
            self.play_file(self._queue[self._current_index])

    def play_index(self, index: int):
        if 0 <= index < len(self._queue):
            self._current_index = index
            self.play_file(self._queue[index])

    def add_to_queue(self, song: Song):
        self._original_queue.append(song)
        self._queue.append(song)
        if self._current_index < 0:
            self._current_index = 0

    def remove_from_queue(self, index: int):
        if 0 <= index < len(self._queue):
            removed_song = self._queue.pop(index)
            if removed_song in self._original_queue:
                self._original_queue.remove(removed_song)
            if index <= self._current_index:
                self._current_index = max(-1, self._current_index - 1)

    def clear_queue(self):
        self._queue.clear()
        self._original_queue.clear()
        self._current_index = -1

    def get_queue(self) -> list[Song]:
        return list(self._queue)

    def get_current_index(self) -> int:
        return self._current_index

    # --- Repeat / Shuffle ---

    def set_repeat_mode(self, mode: RepeatMode):
        self._repeat_mode = mode

    def get_repeat_mode(self) -> RepeatMode:
        return self._repeat_mode

    def toggle_shuffle(self):
        self._shuffle = not self._shuffle
        if not self._queue:
            return
        
        import random
        current_song = self._current_song
        
        if self._shuffle:
            # Si se activa el shuffle, guardamos el estado actual como cola original
            if not self._original_queue:
                self._original_queue = list(self._queue)
            
            shuffled = list(self._queue)
            if current_song and current_song in shuffled:
                idx = shuffled.index(current_song)
                shuffled.pop(idx)
                random.shuffle(shuffled)
                shuffled.insert(0, current_song)
                self._current_index = 0
            else:
                random.shuffle(shuffled)
                self._current_index = 0 if shuffled else -1
            self._queue = shuffled
        else:
            # Si se desactiva, restauramos la cola original
            if self._original_queue:
                self._queue = list(self._original_queue)
                if current_song and current_song in self._queue:
                    self._current_index = self._queue.index(current_song)
                else:
                    self._current_index = 0

    def get_shuffle(self) -> bool:
        return self._shuffle

    # --- Equalizer ---

    def set_equalizer_bands(self, bands: list[float], n_bands: int = 10):
        """
        Apply bands to the GStreamer equalizer.
        bands: list of gain values (may be 3, 5, 10, 15 or 31 items).
        n_bands: the UI band mode that produced `bands`.
        """
        from soundwave.player.equalizer import gains_for_engine, BAND_MODES
        if n_bands not in BAND_MODES:
            n_bands = 10
        engine_bands = gains_for_engine(bands, n_bands)
        self._equalizer_bands = engine_bands
        from soundwave.library.config import save_setting
        save_setting("equalizer_bands", self._equalizer_bands)

        if self._equalizer and self._equalizer_enabled:
            for i, val in enumerate(engine_bands):
                try:
                    self._equalizer.set_property(f"band{i}", val)
                except Exception as e:
                    print(f"Error al aplicar banda {i}: {e}")

    def get_equalizer_bands(self) -> list[float]:
        return list(self._equalizer_bands)

    def set_equalizer_enabled(self, enabled: bool):
        self._equalizer_enabled = enabled
        from soundwave.library.config import save_setting
        save_setting("equalizer_enabled", enabled)

        if self._equalizer:
            bands_to_apply = self._equalizer_bands if enabled else [0.0] * 10
            for i, val in enumerate(bands_to_apply):
                try:
                    self._equalizer.set_property(f"band{i}", val)
                except Exception as e:
                    print(f"Error al aplicar banda {i}: {e}")

    def get_equalizer_enabled(self) -> bool:
        return self._equalizer_enabled

    # --- State queries ---

    def get_state(self) -> PlayerState:
        return self._state

    def get_current_song(self) -> Optional[Song]:
        return self._current_song

    def get_position(self) -> Optional[PlaybackPosition]:
        if not self._playbin or self._state == PlayerState.STOPPED:
            return None
        ok, current  = self._playbin.query_position(Gst.Format.TIME)
        _,  duration = self._playbin.query_duration(Gst.Format.TIME)
        if ok:
            return PlaybackPosition(current=current, duration=max(0, duration))
        return None

    # --- Callbacks ---

    def connect_state(self,    cb: StateChangeCallback): self._state_callbacks.append(cb)
    def connect_song(self,     cb: SongChangeCallback):  self._song_callbacks.append(cb)
    def connect_position(self, cb: PositionCallback):    self._position_callbacks.append(cb)
    def connect_eos(self,      cb: EosCallback):         self._eos_callbacks.append(cb)
    def connect_spectrum(self, cb: Callable[[list[float]], None]): self._spectrum_callbacks.append(cb)

    def disconnect_spectrum(self, cb: Callable[[list[float]], None]):
        if cb in self._spectrum_callbacks:
            self._spectrum_callbacks.remove(cb)

    def disconnect_song(self, cb: SongChangeCallback):
        if cb in self._song_callbacks:
            self._song_callbacks.remove(cb)

    def disconnect_all(self):
        self._state_callbacks.clear()
        self._song_callbacks.clear()
        self._position_callbacks.clear()
        self._eos_callbacks.clear()
        self._spectrum_callbacks.clear()

    # --- Internal ---

    def _on_about_to_finish(self, playbin):
        if self._repeat_mode == RepeatMode.ONE and self._current_song:
            GLib.idle_add(lambda: self.play_file(self._current_song))
            return
        next_idx = self._current_index + 1
        if next_idx >= len(self._queue):
            if self._repeat_mode == RepeatMode.ALL:
                next_idx = 0
            else:
                return
        song = self._queue[next_idx]
        self._current_index = next_idx
        self._current_song = song
        self._playbin.set_property("uri", Path(song.filepath).resolve().as_uri())
        self._apply_volume_with_gain()
        GLib.idle_add(lambda: self._emit_song())

    def _on_bus_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            self._on_eos()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"[GStreamer] Error: {err} — {debug}")
            self.next()
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self._playbin:
                _, new, _ = message.parse_state_changed()
                if new == Gst.State.PLAYING:
                    self._set_state(PlayerState.PLAYING)
                elif new == Gst.State.PAUSED:
                    self._set_state(PlayerState.PAUSED)
        elif t == Gst.MessageType.ELEMENT:
            struct = message.get_structure()
            if struct and struct.get_name() == "spectrum":
                try:
                    magnitudes = struct.get_value("magnitude")
                    if magnitudes:
                        if hasattr(magnitudes, "get_size"):
                            m_list = [magnitudes.get_nth(i) for i in range(magnitudes.get_size())]
                        else:
                            m_list = list(magnitudes)
                        self._emit_spectrum(m_list)
                except TypeError:
                    # GstValueList fallback: convert structure to string and parse values
                    struct_str = struct.to_string()
                    import re
                    match = re.search(r'magnitude=(?:\([a-zA-Z]+\))?{([^}]+)}', struct_str)
                    if not match:
                        match = re.search(r'magnitude=\(float\)([-0-9.]+)', struct_str)
                        if match:
                            try:
                                self._emit_spectrum([float(match.group(1))])
                            except Exception:
                                pass
                            return
                    if match:
                        try:
                            m_list = [float(x.strip()) for x in match.group(1).split(',') if x.strip()]
                            if m_list:
                                self._emit_spectrum(m_list)
                        except Exception:
                            pass
                except Exception:
                    pass

    def _on_eos(self):
        self._emit_eos()
        self.next()

    def _set_state(self, state: PlayerState):
        if self._state == state:
            return  # FIX: evita doble emisión de callbacks
        self._state = state
        for cb in self._state_callbacks:
            cb(state)

    def _emit_song(self):
        for cb in self._song_callbacks:
            cb(self._current_song)

    def _emit_position(self, pos: PlaybackPosition):
        for cb in self._position_callbacks:
            cb(pos)

    def _emit_eos(self):
        for cb in self._eos_callbacks:
            cb()

    def _emit_spectrum(self, magnitudes: list[float]):
        for cb in self._spectrum_callbacks:
            cb(magnitudes)

    def _start_position_timer(self):
        self._stop_position_timer()
        self._position_timer = GLib.timeout_add(250, self._poll_position)

    def _stop_position_timer(self):
        if self._position_timer:
            GLib.source_remove(self._position_timer)
            self._position_timer = None

    def _poll_position(self) -> bool:
        if self._state in (PlayerState.PLAYING, PlayerState.PAUSED):
            pos = self.get_position()
            if pos:
                self._emit_position(pos)
        return True  # mantener el timer vivo

    def destroy(self):
        self._stop_position_timer()
        if self._playbin:
            self._playbin.set_state(Gst.State.NULL)
        self.disconnect_all()