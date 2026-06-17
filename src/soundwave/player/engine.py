import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

from typing import Optional, Callable
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from soundwave.library.database import Song


class PlayerState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class RepeatMode(Enum):
    NONE = "none"
    ALL = "all"
    ONE = "one"


@dataclass
class PlaybackPosition:
    current: int  # nanoseconds
    duration: int  # nanoseconds

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
SongChangeCallback = Callable[[Optional[Song]], None]
PositionCallback = Callable[[PlaybackPosition], None]
EosCallback = Callable[[], None]


class Player:
    def __init__(self):
        Gst.init(None)
        self._pipeline: Optional[Gst.Element] = None
        self._playbin: Optional[Gst.Element] = None
        self._state = PlayerState.STOPPED
        self._current_song: Optional[Song] = None
        self._queue: list[Song] = []
        self._current_index: int = -1
        self._volume: float = 1.0
        self._repeat_mode = RepeatMode.NONE
        self._shuffle: bool = False
        self._equalizer: Optional[Gst.Element] = None
        self._equalizer_bands: list[float] = [0.0] * 10

        self._state_callbacks: list[StateChangeCallback] = []
        self._song_callbacks: list[SongChangeCallback] = []
        self._position_callbacks: list[PositionCallback] = []
        self._eos_callbacks: list[EosCallback] = []

        self._position_timer: Optional[int] = None
        self._pending_seek: Optional[int] = None

    # --- Public API ---

    def play_file(self, song: Song):
        self._build_pipeline()
        self._playbin.set_property("uri", Path(song.filepath).as_uri())
        self._current_song = song
        self._set_state(PlayerState.PLAYING)
        self._playbin.set_state(Gst.State.PLAYING)
        self._start_position_timer()
        self._emit_song()

    def play_pause(self):
        if self._state == PlayerState.STOPPED and self._queue:
            self.play_index(self._current_index if self._current_index >= 0 else 0)
            return
        if self._state == PlayerState.PLAYING:
            self._playbin.set_state(Gst.State.PAUSED)
            self._set_state(PlayerState.PAUSED)
        elif self._state == PlayerState.PAUSED:
            self._playbin.set_state(Gst.State.PLAYING)
            self._set_state(PlayerState.PLAYING)

    def stop(self):
        if self._playbin:
            self._playbin.set_state(Gst.State.NULL)
        self._set_state(PlayerState.STOPPED)
        self._stop_position_timer()
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
            if self._repeat_mode == RepeatMode.ALL:
                prev_idx = len(self._queue) - 1
            else:
                prev_idx = 0
        self.play_index(prev_idx)

    def seek(self, position_ns: int):
        if self._playbin and self._state != PlayerState.STOPPED:
            self._playbin.seek_simple(
                Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, position_ns
            )

    def seek_seconds(self, seconds: float):
        self.seek(int(seconds * 1e9))

    def set_volume(self, volume: float):
        self._volume = max(0.0, min(1.0, volume))
        if self._playbin:
            self._playbin.set_property("volume", self._volume)

    def get_volume(self) -> float:
        return self._volume

    # --- Queue management ---

    def set_queue(self, songs: list[Song], start_index: int = 0):
        self._queue = list(songs)
        self._current_index = start_index if self._queue else -1
        if self._queue and 0 <= start_index < len(self._queue):
            self.play_file(self._queue[start_index])

    def play_index(self, index: int):
        if 0 <= index < len(self._queue):
            self._current_index = index
            self.play_file(self._queue[index])

    def add_to_queue(self, song: Song):
        self._queue.append(song)
        if self._current_index < 0:
            self._current_index = 0

    def remove_from_queue(self, index: int):
        if 0 <= index < len(self._queue):
            self._queue.pop(index)
            if index <= self._current_index:
                self._current_index = max(-1, self._current_index - 1)

    def clear_queue(self):
        self._queue.clear()
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

    def get_shuffle(self) -> bool:
        return self._shuffle

    # --- Equalizer ---

    def set_equalizer_bands(self, bands: list[float]):
        if len(bands) != 10:
            return
        self._equalizer_bands = list(bands)
        if self._equalizer:
            for i, val in enumerate(bands):
                band_name = f"band{i}"
                band = self._equalizer.get_child_by_name(band_name)
                if band:
                    band.set_property("gain", val)

    def get_equalizer_bands(self) -> list[float]:
        return list(self._equalizer_bands)

    # --- State queries ---

    def get_state(self) -> PlayerState:
        return self._state

    def get_current_song(self) -> Optional[Song]:
        return self._current_song

    def get_position(self) -> Optional[PlaybackPosition]:
        if not self._playbin or self._state == PlayerState.STOPPED:
            return None
        ok, current = self._playbin.query_position(Gst.Format.TIME)
        _, duration = self._playbin.query_duration(Gst.Format.TIME)
        if ok:
            return PlaybackPosition(current=current, duration=duration)
        return None

    # --- Callbacks ---

    def connect_state(self, cb: StateChangeCallback):
        self._state_callbacks.append(cb)

    def connect_song(self, cb: SongChangeCallback):
        self._song_callbacks.append(cb)

    def connect_position(self, cb: PositionCallback):
        self._position_callbacks.append(cb)

    def connect_eos(self, cb: EosCallback):
        self._eos_callbacks.append(cb)

    def disconnect_all(self):
        self._state_callbacks.clear()
        self._song_callbacks.clear()
        self._position_callbacks.clear()
        self._eos_callbacks.clear()

    # --- Internal ---

    def _build_pipeline(self):
        if self._playbin:
            self._playbin.set_state(Gst.State.NULL)
            self._playbin = None
            self._pipeline = None
            self._equalizer = None

        self._playbin = Gst.ElementFactory.make("playbin3", "playbin")
        if self._playbin is None:
            self._playbin = Gst.ElementFactory.make("playbin", "playbin")

        self._pipeline = self._playbin
        self._playbin.set_property("volume", self._volume)

        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)

    def _build_equalizer_pipeline(self):
        if self._playbin:
            self._playbin.set_state(Gst.State.NULL)
            self._playbin = None
            self._pipeline = None
            self._equalizer = None

        self._playbin = Gst.ElementFactory.make("playbin3", "playbin")
        if self._playbin is None:
            self._playbin = Gst.ElementFactory.make("playbin", "playbin")

        self._equalizer = Gst.ElementFactory.make("equalizer-10bands", "equalizer")
        if self._equalizer:
            self._playbin.set_property("audio-filter", self._equalizer)
            self.set_equalizer_bands(self._equalizer_bands)

        self._pipeline = self._playbin
        self._playbin.set_property("volume", self._volume)

        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)

    def _on_bus_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            self._on_eos()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"GStreamer error: {err} - {debug}")
            self.next()
        elif t == Gst.MessageType.STATE_CHANGED:
            old, new, pending = message.parse_state_changed()
            if message.src == self._playbin:
                if new == Gst.State.PLAYING:
                    self._set_state(PlayerState.PLAYING)
                elif new == Gst.State.PAUSED:
                    self._set_state(PlayerState.PAUSED)

    def _on_eos(self):
        self._emit_eos()
        self.next()

    def _set_state(self, state: PlayerState):
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

    def _start_position_timer(self):
        self._stop_position_timer()
        self._position_timer = GLib.timeout_add(250, self._poll_position)

    def _stop_position_timer(self):
        if self._position_timer:
            GLib.source_remove(self._position_timer)
            self._position_timer = None

    def _poll_position(self) -> bool:
        if self._state == PlayerState.PLAYING or self._state == PlayerState.PAUSED:
            pos = self.get_position()
            if pos:
                self._emit_position(pos)
        return True  # keep timer alive

    def destroy(self):
        self._stop_position_timer()
        if self._playbin:
            self._playbin.set_state(Gst.State.NULL)
        self.disconnect_all()
