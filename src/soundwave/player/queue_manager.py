"""Gestor de cola de reproducción para Soundwave."""

from enum import Enum
from typing import Optional
import random
from soundwave.library.database.database import Song


class RepeatMode(Enum):
    NONE = "none"
    ALL  = "all"
    ONE  = "one"


class QueueManager:
    def __init__(self):
        self._queue: list[Song] = []
        self._original_queue: list[Song] = []
        self._current_index: int = -1
        self._repeat_mode = RepeatMode.NONE
        self._shuffle: bool = False

    @property
    def queue(self) -> list[Song]:
        return self._queue

    @property
    def original_queue(self) -> list[Song]:
        return self._original_queue

    @property
    def current_index(self) -> int:
        return self._current_index

    @current_index.setter
    def current_index(self, index: int):
        self._current_index = index

    @property
    def repeat_mode(self) -> RepeatMode:
        return self._repeat_mode

    @repeat_mode.setter
    def repeat_mode(self, mode: RepeatMode):
        self._repeat_mode = mode

    @property
    def shuffle(self) -> bool:
        return self._shuffle

    @shuffle.setter
    def shuffle(self, enabled: bool):
        self._shuffle = enabled

    def get_current_song(self) -> Optional[Song]:
        if 0 <= self._current_index < len(self._queue):
            return self._queue[self._current_index]
        return None

    def set_queue(self, songs: list[Song], start_index: int = 0) -> Optional[Song]:
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

        return self.get_current_song()

    def play_index(self, index: int) -> Optional[Song]:
        if 0 <= index < len(self._queue):
            self._current_index = index
            return self._queue[index]
        return None

    def add_to_queue(self, song: Song):
        self._original_queue.append(song)
        self._queue.append(song)
        if self._current_index < 0:
            self._current_index = 0

    def play_next(self, song: Song, current_song: Optional[Song]):
        if not self._queue:
            self.add_to_queue(song)
            return

        idx = self._current_index + 1
        self._queue.insert(idx, song)

        # Insert in original queue too
        if current_song and current_song in self._original_queue:
            try:
                orig_idx = self._original_queue.index(current_song) + 1
                self._original_queue.insert(orig_idx, song)
            except ValueError:
                self._original_queue.insert(idx, song)
        else:
            self._original_queue.insert(idx, song)

    def reorder_queue(self, songs: list[Song], current_song: Optional[Song]):
        self._queue = list(songs)
        if not self._shuffle:
            self._original_queue = list(songs)
        if current_song and current_song in self._queue:
            try:
                self._current_index = self._queue.index(current_song)
            except ValueError:
                self._current_index = -1
        else:
            self._current_index = -1

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

    def toggle_shuffle(self, current_song: Optional[Song]):
        self._shuffle = not self._shuffle
        if not self._queue:
            return

        if self._shuffle:
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
            if self._original_queue:
                self._queue = list(self._original_queue)
                if current_song and current_song in self._queue:
                    self._current_index = self._queue.index(current_song)
                else:
                    self._current_index = 0

    def get_next_index(self) -> int:
        if not self._queue:
            return -1
        next_idx = self._current_index + 1
        if next_idx >= len(self._queue):
            if self._repeat_mode == RepeatMode.ALL:
                return 0
            else:
                return -1
        return next_idx

    def get_previous_index(self) -> int:
        if not self._queue:
            return -1
        prev_idx = self._current_index - 1
        if prev_idx < 0:
            if self._repeat_mode == RepeatMode.ALL:
                return len(self._queue) - 1
            else:
                return 0
        return prev_idx
