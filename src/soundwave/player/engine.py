import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

from typing import Optional, Callable
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import random

from soundwave.library.database.database import Song


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
        self._playbin1: Optional[Gst.Element] = None
        self._playbin2: Optional[Gst.Element] = None
        self._playbin:  Optional[Gst.Element] = None
        self._eq1: Optional[Gst.Element] = None
        self._eq2: Optional[Gst.Element] = None
        self._spec1: Optional[Gst.Element] = None
        self._spec2: Optional[Gst.Element] = None
        self._state      = PlayerState.STOPPED
        self._current_song: Optional[Song] = None
        self._queue:     list[Song] = []
        self._original_queue: list[Song] = []
        self._current_index: int    = -1
        self._volume:    float      = 1.0
        self._repeat_mode            = RepeatMode.NONE
        self._shuffle:   bool       = False
        self._equalizer: Optional[Gst.Element] = None
        self._spectrum:  Optional[Gst.Element] = None
        
        # Cargar configuración del ecualizador, ReplayGain y reproducción sin pausa
        from soundwave.library.config.config import load_settings
        from soundwave.player.equalizer import BAND_MODES
        settings = load_settings()
        self._equalizer_n_bands: int = settings.get("equalizer_n_bands", 10)
        # Fallback si el número de bandas guardado ya no es válido
        if self._equalizer_n_bands not in BAND_MODES:
            self._equalizer_n_bands = 10
        self._equalizer_bands: list[float] = settings.get("equalizer_bands", [0.0] * self._equalizer_n_bands)
        self._equalizer_enabled: bool = settings.get("equalizer_enabled", True)
        self._replaygain_mode: str = settings.get("replaygain_mode", "track")
        self._crossfade_duration: float = settings.get("crossfade_duration", 0)
        self._gapless_enabled: bool = settings.get("gapless_enabled", True)

        self._state_callbacks:    list[StateChangeCallback] = []
        self._song_callbacks:     list[SongChangeCallback]  = []
        self._position_callbacks: list[PositionCallback]    = []
        self._eos_callbacks:      list[EosCallback]         = []
        self._spectrum_callbacks: list[Callable[[list[float]], None]] = []
        self._queue_callbacks:    list[Callable[[list[Song]], None]] = []

        self._position_timer: Optional[int] = None
        self._crossfade_timer_id: Optional[int] = None
        self._crossfade_fade_out_timer: Optional[int] = None
        self._crossfade_fade_in_timer: Optional[int] = None
        self._crossfade_volume_step: float = 0.0
        self._crossfade_steps_remaining: int = 0
        self._crossfade_target_volume: float = 1.0
        self._crossfade_triggered: bool = False
        self._next_song: Optional[Song] = None
        # Flag para evitar doble avance: True cuando _on_about_to_finish
        # ya actualizó el índice/URI, así _on_eos no llama a next() de nuevo.
        self._gapless_advanced: bool = False

        # Construir el pipeline UNA sola vez al inicio
        self._build_pipeline()

    # --- Pipeline (construir una sola vez) ---

    def _create_playbin(self, name: str) -> Gst.Element:
        # Preferimos playbin clásico para evitar problemas de buffering/latencia conocidos de playbin3 en archivos locales
        playbin = Gst.ElementFactory.make("playbin", name)
        if playbin is None:
            playbin = Gst.ElementFactory.make("playbin3", name)
        if playbin is None:
            raise RuntimeError(f"No se pudo crear {name}. Verifica gstreamer1.0-plugins-base.")
        
        playbin.set_property("volume", self._volume)
        playbin.set_property("buffer-size", 2 * 1024 * 1024)
        
        # Ignorar pistas de video y subtítulos para optimizar la decodificación de audio (sólo audio = 2)
        try:
            playbin.set_property("flags", 2)
        except Exception:
            pass
            
        bus = playbin.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)
        
        playbin.connect("about-to-finish", self._on_about_to_finish)
        return playbin

    def _build_pipeline(self):
        self._playbin1 = self._create_playbin("playbin1")
        self._playbin2 = self._create_playbin("playbin2")
        self._playbin = self._playbin1
        
        self._eq1, self._spec1 = self._attach_equalizer_to_playbin(self._playbin1, "equalizer1", "spectrum1")
        self._eq2, self._spec2 = self._attach_equalizer_to_playbin(self._playbin2, "equalizer2", "spectrum2")
        
        self._equalizer = self._eq1
        self._spectrum = self._spec1
        
        self._apply_equalizer_gains()

    def _attach_equalizer_to_playbin(self, playbin, eq_name, spec_name):
        eq = Gst.ElementFactory.make("equalizer-10bands", eq_name)
        spec = Gst.ElementFactory.make("spectrum", spec_name)
        if eq and spec:
            spec.set_property("bands", 64)
            spec.set_property("threshold", -75)
            spec.set_property("post-messages", True)
            spec.set_property("message-magnitude", True)
            spec.set_property("interval", 33 * Gst.MSECOND)

            filt_bin = Gst.Bin.new(f"audio-filter-bin-{eq_name}")
            filt_bin.add(eq)
            filt_bin.add(spec)
            eq.link(spec)

            sink_pad = Gst.GhostPad.new("sink", eq.get_static_pad("sink"))
            filt_bin.add_pad(sink_pad)

            src_pad = Gst.GhostPad.new("src", spec.get_static_pad("src"))
            filt_bin.add_pad(src_pad)

            playbin.set_property("audio-filter", filt_bin)
            return eq, spec
        elif eq:
            playbin.set_property("audio-filter", eq)
            return eq, None
        return None, None

    def _apply_equalizer_gains(self):
        from soundwave.player.equalizer import gains_for_engine
        n_bands = self._equalizer_n_bands
        if len(self._equalizer_bands) != n_bands:
            self._equalizer_bands = list(self._equalizer_bands) + [0.0] * (n_bands - len(self._equalizer_bands))
            self._equalizer_bands = self._equalizer_bands[:n_bands]
        
        engine_bands = gains_for_engine(self._equalizer_bands, n_bands)
        bands_to_apply = engine_bands if self._equalizer_enabled else [0.0] * 10
        
        for eq in (self._eq1, self._eq2):
            if eq:
                for i, val in enumerate(bands_to_apply):
                    try:
                        eq.set_property(f"band{i}", val)
                    except Exception as e:
                        print(f"Error al aplicar banda {i}: {e}")

    # --- Public API ---

    def play_file(self, song: Song):
        """
        FIX: reutiliza el mismo playbin. Proceso correcto para cambiar URI:
          NULL → set uri → PLAYING
        """
        self._stop_position_timer()
        # Resetear el flag de avance gapless al iniciar una nueva canción manualmente
        self._gapless_advanced = False
        # Cancelar cualquier fade de crossfade en curso y restablecer estado
        self._reset_crossfade_state()
        self._next_song = None

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
            self._finish_crossfade_immediately()
            self._playbin1.set_state(Gst.State.PAUSED)
            self._playbin2.set_state(Gst.State.PAUSED)
        elif self._state == PlayerState.PAUSED:
            self._playbin1.set_state(Gst.State.PLAYING)
            self._playbin2.set_state(Gst.State.PLAYING)

    def stop(self):
        self._stop_position_timer()
        self._reset_crossfade_state()
        if self._playbin1:
            self._playbin1.set_state(Gst.State.NULL)
        if self._playbin2:
            self._playbin2.set_state(Gst.State.NULL)
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
        if self._crossfade_timer_id is not None:
            self._finish_crossfade_immediately()
        else:
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
        self._emit_queue()

    def play_index(self, index: int):
        if 0 <= index < len(self._queue):
            self._current_index = index
            self.play_file(self._queue[index])

    def add_to_queue(self, song: Song):
        self._original_queue.append(song)
        self._queue.append(song)
        if self._current_index < 0:
            self._current_index = 0
        self._emit_queue()

    def play_next(self, song: Song):
        if not self._queue:
            self.add_to_queue(song)
            return

        idx = self._current_index + 1
        self._queue.insert(idx, song)

        # Insertar en la cola original también
        if self._current_song and self._current_song in self._original_queue:
            try:
                orig_idx = self._original_queue.index(self._current_song) + 1
                self._original_queue.insert(orig_idx, song)
            except ValueError:
                self._original_queue.insert(idx, song)
        else:
            self._original_queue.insert(idx, song)

        self._emit_queue()

    def reorder_queue(self, songs: list[Song]):
        self._queue = list(songs)
        if not self._shuffle:
            self._original_queue = list(songs)
        if self._current_song and self._current_song in self._queue:
            try:
                self._current_index = self._queue.index(self._current_song)
            except ValueError:
                self._current_index = -1
        else:
            self._current_index = -1
        self._emit_queue()

    def remove_from_queue(self, index: int):
        if 0 <= index < len(self._queue):
            removed_song = self._queue.pop(index)
            if removed_song in self._original_queue:
                self._original_queue.remove(removed_song)
            if index <= self._current_index:
                self._current_index = max(-1, self._current_index - 1)
            self._emit_queue()

    def clear_queue(self):
        self._queue.clear()
        self._original_queue.clear()
        self._current_index = -1
        self._emit_queue()

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
        self._emit_queue()

    def get_shuffle(self) -> bool:
        return self._shuffle

    # --- Equalizer ---

    def set_equalizer_bands(self, bands: list[float], n_bands: int = 10):
        """
        Apply bands to the GStreamer equalizer.
        bands: list of gain values (may be 3, 5, 10, 15 or 31 items).
        n_bands: the UI band mode that produced `bands`.
        """
        from soundwave.player.equalizer import BAND_MODES
        if n_bands not in BAND_MODES:
            n_bands = 10
        
        # Guardar el número de bandas actual y las bandas originales
        self._equalizer_n_bands = n_bands
        self._equalizer_bands = list(bands)
        
        from soundwave.library.config.config import save_setting
        save_setting("equalizer_bands", self._equalizer_bands)
        save_setting("equalizer_n_bands", self._equalizer_n_bands)

        self._apply_equalizer_gains()

    def get_equalizer_bands(self) -> list[float]:
        return list(self._equalizer_bands)

    def set_equalizer_enabled(self, enabled: bool):
        self._equalizer_enabled = enabled
        from soundwave.library.config.config import save_setting
        save_setting("equalizer_enabled", enabled)

        self._apply_equalizer_gains()

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
    def connect_queue(self,    cb: Callable[[list[Song]], None]): self._queue_callbacks.append(cb)

    def disconnect_spectrum(self, cb: Callable[[list[float]], None]):
        if cb in self._spectrum_callbacks:
            self._spectrum_callbacks.remove(cb)

    def disconnect_song(self, cb: SongChangeCallback):
        if cb in self._song_callbacks:
            self._song_callbacks.remove(cb)

    def disconnect_queue(self, cb: Callable[[list[Song]], None]):
        if cb in self._queue_callbacks:
            self._queue_callbacks.remove(cb)

    def disconnect_all(self):
        self._state_callbacks.clear()
        self._song_callbacks.clear()
        self._position_callbacks.clear()
        self._eos_callbacks.clear()
        self._spectrum_callbacks.clear()
        self._queue_callbacks.clear()

    # --- Internal ---

    def _get_target_volume_for_song(self, song: Optional[Song]) -> float:
        factor = 1.0
        if song:
            mode = self._replaygain_mode
            if mode == "track":
                gain = getattr(song, "replaygain_track_gain", 0.0)
                if gain != 0.0:
                    factor = 10 ** (gain / 20.0)
            elif mode == "album":
                gain = getattr(song, "replaygain_album_gain", 0.0)
                if gain == 0.0:
                    gain = getattr(song, "replaygain_track_gain", 0.0)
                if gain != 0.0:
                    factor = 10 ** (gain / 20.0)
        return self._volume * factor

    def set_gapless_enabled(self, enabled: bool):
        self._gapless_enabled = enabled
        from soundwave.library.config.config import save_setting
        save_setting("gapless_enabled", enabled)

    def get_gapless_enabled(self) -> bool:
        return self._gapless_enabled

    def _reset_crossfade_state(self):
        self._cancel_crossfade_timers()
        self._crossfade_triggered = False
        inactive_playbin = self._playbin2 if self._playbin == self._playbin1 else self._playbin1
        if inactive_playbin:
            inactive_playbin.set_state(Gst.State.NULL)
        if self._playbin:
            self._apply_volume_with_gain()

    def _finish_crossfade_immediately(self):
        self._cancel_crossfade_timers()
        if self._playbin:
            self._apply_volume_with_gain()
        inactive_playbin = self._playbin2 if self._playbin == self._playbin1 else self._playbin1
        if inactive_playbin:
            inactive_playbin.set_state(Gst.State.NULL)

    def _on_about_to_finish(self, playbin):
        if self._crossfade_duration > 0:
            return
            
        if not self._gapless_enabled:
            return
            
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
        self._next_song = song
        playbin.set_property("uri", Path(song.filepath).resolve().as_uri())
        self._gapless_advanced = True

    def _start_fade_out(self):
        pass

    def _fade_out_step(self) -> bool:
        return False

    def _on_stream_start(self):
        if self._next_song:
            self._current_song = self._next_song
            self._next_song = None
            GLib.idle_add(lambda: self._emit_song())
            self._apply_volume_with_gain()
        self._gapless_advanced = False

    def _start_fade_in(self, target_volume: float):
        pass

    def _fade_in_step(self) -> bool:
        return False

    def _cancel_crossfade_timers(self):
        if self._crossfade_timer_id is not None:
            GLib.source_remove(self._crossfade_timer_id)
            self._crossfade_timer_id = None
        if self._crossfade_fade_out_timer is not None:
            GLib.source_remove(self._crossfade_fade_out_timer)
            self._crossfade_fade_out_timer = None
        if self._crossfade_fade_in_timer is not None:
            GLib.source_remove(self._crossfade_fade_in_timer)
            self._crossfade_fade_in_timer = None

    def _trigger_crossfade_transition(self, duration: float):
        next_idx = self._current_index + 1
        if next_idx >= len(self._queue):
            if self._repeat_mode == RepeatMode.ALL:
                next_idx = 0
            else:
                return
                
        next_song = self._queue[next_idx]
        
        active_playbin = self._playbin
        inactive_playbin = self._playbin2 if active_playbin == self._playbin1 else self._playbin1
        
        inactive_playbin.set_state(Gst.State.NULL)
        inactive_playbin.set_property("uri", Path(next_song.filepath).resolve().as_uri())
        inactive_playbin.set_property("volume", 0.0)
        
        self._apply_equalizer_gains()
        
        inactive_playbin.set_state(Gst.State.PLAYING)
        
        self._playbin = inactive_playbin
        self._current_index = next_idx
        self._current_song = next_song
        self._emit_song()
        
        self._start_crossfade_timer(active_playbin, inactive_playbin, duration)

    def _start_crossfade_timer(self, fade_out_playbin, fade_in_playbin, duration: float):
        self._cancel_crossfade_timers()
        
        total_steps = int(duration * 10)
        if total_steps <= 0:
            fade_out_playbin.set_state(Gst.State.NULL)
            self._apply_volume_with_gain()
            return
            
        target_volume = self._get_target_volume_for_song(self._current_song)
        start_volume_out = fade_out_playbin.get_property("volume")
        
        step_out = start_volume_out / total_steps
        step_in = target_volume / total_steps
        
        steps_remaining = total_steps
        
        def crossfade_step():
            nonlocal steps_remaining
            steps_remaining -= 1
            
            if steps_remaining <= 0:
                fade_out_playbin.set_state(Gst.State.NULL)
                if self._playbin == fade_in_playbin:
                    fade_in_playbin.set_property("volume", target_volume)
                self._crossfade_timer_id = None
                return False
                
            vol_out = max(0.0, fade_out_playbin.get_property("volume") - step_out)
            fade_out_playbin.set_property("volume", vol_out)
            
            if self._playbin == fade_in_playbin:
                vol_in = min(target_volume, fade_in_playbin.get_property("volume") + step_in)
                fade_in_playbin.set_property("volume", vol_in)
                
            return True
            
        self._crossfade_timer_id = GLib.timeout_add(100, crossfade_step)

    def _on_bus_message(self, bus, message):
        t = message.type
        active_bus = self._playbin.get_bus() if self._playbin else None
        
        if bus == active_bus:
            if t == Gst.MessageType.EOS:
                self._on_eos()
            elif t == Gst.MessageType.STREAM_START:
                self._on_stream_start()
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
                        if self._crossfade_timer_id is None:
                            self._set_state(PlayerState.PAUSED)
            elif t == Gst.MessageType.ELEMENT:
                struct = message.get_structure()
                if struct and struct.get_name() == "spectrum":
                    if not self._spectrum_callbacks:
                        return
                    try:
                        magnitudes = struct.get_value("magnitude")
                        if magnitudes:
                            if hasattr(magnitudes, "get_size"):
                                m_list = [magnitudes.get_nth(i) for i in range(magnitudes.get_size())]
                            else:
                                m_list = list(magnitudes)
                            self._emit_spectrum(m_list)
                    except TypeError:
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
        else:
            if t == Gst.MessageType.EOS:
                message.src.set_state(Gst.State.NULL)

    def _on_eos(self):
        self._emit_eos()
        if self._gapless_advanced:
            self._gapless_advanced = False
        else:
            self.next()

    def _set_state(self, state: PlayerState):
        if self._state == state:
            return
        self._state = state
        if state in (PlayerState.STOPPED, PlayerState.PAUSED):
            self._cancel_crossfade_timers()
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

    def _emit_queue(self):
        q = self.get_queue()
        for cb in self._queue_callbacks:
            try:
                cb(q)
            except Exception as e:
                print(f"[Player] Error emitting queue: {e}")

    def _start_position_timer(self):
        self._stop_position_timer()
        self._position_timer = GLib.timeout_add(100, self._poll_position)

    def _stop_position_timer(self):
        if self._position_timer:
            GLib.source_remove(self._position_timer)
            self._position_timer = None

    def _poll_position(self) -> bool:
        if self._state == PlayerState.PLAYING:
            pos = self.get_position()
            if pos:
                self._emit_position(pos)
                
                # Comprobar si se dispara la transición de crossfade
                if (self._crossfade_duration > 0 and 
                        not self._crossfade_triggered and 
                        pos.duration_seconds > 0):
                    effective_crossfade = min(self._crossfade_duration, pos.duration_seconds / 2.0)
                    remaining_seconds = pos.duration_seconds - pos.current_seconds
                    if remaining_seconds <= effective_crossfade:
                        self._crossfade_triggered = True
                        self._trigger_crossfade_transition(effective_crossfade)
        elif self._state == PlayerState.PAUSED:
            pos = self.get_position()
            if pos:
                self._emit_position(pos)
        return True

    def destroy(self):
        self._stop_position_timer()
        self._cancel_crossfade_timers()
        if self._playbin1:
            self._playbin1.set_state(Gst.State.NULL)
        if self._playbin2:
            self._playbin2.set_state(Gst.State.NULL)
        self.disconnect_all()