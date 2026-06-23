import time
import sys
from pathlib import Path
import gi
gi.require_version("Gst", "1.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gst, GLib

# Add src/ to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from soundwave.library.database.database import Song
from soundwave.player.engine import Player, PlayerState

class FixedPlayer(Player):
    def __init__(self):
        super().__init__()
        self._crossfade_fade_in_timer = None
        self._next_song = None
        self._crossfade_target_volume = 1.0

    def _cancel_crossfade_timers(self):
        if self._crossfade_fade_out_timer is not None:
            GLib.source_remove(self._crossfade_fade_out_timer)
            self._crossfade_fade_out_timer = None
        if self._crossfade_fade_in_timer is not None:
            GLib.source_remove(self._crossfade_fade_in_timer)
            self._crossfade_fade_in_timer = None

    def play_file(self, song: Song):
        self._stop_position_timer()
        self._gapless_advanced = False
        self._cancel_crossfade_timers()

        # pyrefly: ignore [missing-attribute]
        self._playbin.set_state(Gst.State.NULL)
        # pyrefly: ignore [missing-attribute]
        self._playbin.set_property("uri", Path(song.filepath).resolve().as_uri())
        self._current_song = song
        self._next_song = None

        self._apply_volume_with_gain()

        # pyrefly: ignore [missing-attribute]
        self._playbin.set_state(Gst.State.PLAYING)
        self._start_position_timer()
        self._emit_song()

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
        
        # Save to next_song and don't update current_song / emit song yet!
        self._next_song = song
        # pyrefly: ignore [missing-attribute]
        self._playbin.set_property("uri", Path(song.filepath).resolve().as_uri())
        self._gapless_advanced = True

        # Crossfade: Start fade-out of current song
        if self._crossfade_duration > 0:
            self._start_fade_out()

    def _start_fade_out(self):
        self._cancel_crossfade_timers()
        total_steps = int(self._crossfade_duration * 10)  # 10 steps per second
        if total_steps <= 0:
            return
        
        current_volume = self._playbin.get_property("volume") if self._playbin else self._volume
        self._crossfade_volume_step = current_volume / total_steps
        self._crossfade_steps_remaining = total_steps
        self._crossfade_fade_out_timer = GLib.timeout_add(100, self._fade_out_step)

    def _fade_out_step(self) -> bool:
        if not self._playbin:
            self._crossfade_fade_out_timer = None
            return False
            
        self._crossfade_steps_remaining -= 1
        if self._crossfade_steps_remaining <= 0:
            self._playbin.set_property("volume", 0.0)
            self._crossfade_fade_out_timer = None
            return False
            
        current_volume = self._playbin.get_property("volume")
        new_volume = max(0.0, current_volume - self._crossfade_volume_step)
        self._playbin.set_property("volume", new_volume)
        return True

    def _on_stream_start(self):
        # Triggered when GStreamer actually transitions to the next song
        if self._next_song:
            self._current_song = self._next_song
            self._next_song = None
            GLib.idle_add(lambda: self._emit_song())
            
            # Determine target volume for new song with gain
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
            
            target_volume = self._volume * factor
            
            if self._crossfade_duration > 0:
                self._start_fade_in(target_volume)
            else:
                if self._playbin:
                    self._playbin.set_property("volume", target_volume)

    def _start_fade_in(self, target_volume: float):
        # Cancel any active timers
        if self._crossfade_fade_out_timer is not None:
            GLib.source_remove(self._crossfade_fade_out_timer)
            self._crossfade_fade_out_timer = None
        if self._crossfade_fade_in_timer is not None:
            GLib.source_remove(self._crossfade_fade_in_timer)
            self._crossfade_fade_in_timer = None

        total_steps = int(self._crossfade_duration * 10)
        if total_steps <= 0:
            if self._playbin:
                self._playbin.set_property("volume", target_volume)
            return

        current_volume = self._playbin.get_property("volume") if self._playbin else 0.0
        self._crossfade_volume_step = (target_volume - current_volume) / total_steps
        self._crossfade_steps_remaining = total_steps
        self._crossfade_target_volume = target_volume
        self._crossfade_fade_in_timer = GLib.timeout_add(100, self._fade_in_step)

    def _fade_in_step(self) -> bool:
        if not self._playbin:
            self._crossfade_fade_in_timer = None
            return False
            
        self._crossfade_steps_remaining -= 1
        if self._crossfade_steps_remaining <= 0:
            self._playbin.set_property("volume", self._crossfade_target_volume)
            self._crossfade_fade_in_timer = None
            return False
            
        current_volume = self._playbin.get_property("volume")
        new_volume = min(self._crossfade_target_volume, max(0.0, current_volume + self._crossfade_volume_step))
        self._playbin.set_property("volume", new_volume)
        return True

    def _on_bus_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.STREAM_START:
            self._on_stream_start()
        # Delegate other messages to the base class
        super()._on_bus_message(bus, message)

from soundwave.player.engine import RepeatMode

def main():
    Gst.init(None)
    loop = GLib.MainLoop()

    player = FixedPlayer()
    player._crossfade_duration = 2.0

    song1 = Song(id=1, filepath="/usr/share/sounds/sound-icons/xylofon.wav", title="Song 1", artist="Artist A")
    song2 = Song(id=2, filepath="/usr/share/sounds/sound-icons/cembalo-6.wav", title="Song 2", artist="Artist B")

    print(f"Setting queue...")
    player.set_queue([song1, song2], start_index=0)

    start_time = time.time()
    
    def monitor():
        elapsed = time.time() - start_time
        state = player.get_state()
        curr_song = player.get_current_song()
        vol = player._playbin.get_property("volume") if player._playbin else None
        pos = player.get_position()
        pos_str = f"{pos.current_seconds:.2f}/{pos.duration_seconds:.2f}" if pos else "N/A"
        
        print(f"[{elapsed:.2f}s] State: {state.value}, Song: {curr_song.title if curr_song else 'None'}, Vol: {vol}, Pos: {pos_str}, Fade-Out Timer: {player._crossfade_fade_out_timer}, Fade-In Timer: {player._crossfade_fade_in_timer}")
        
        if elapsed > 6.0:
            loop.quit()
            return False
        return True

    GLib.timeout_add(100, monitor)

    # Connect callbacks
    player.connect_song(lambda s: print(f"--> Callback: Song changed to: {s.title if s else 'None'}"))
    player.connect_state(lambda st: print(f"--> Callback: State changed to: {st.value}"))

    # Start playback
    print("Starting playback...")
    player.play_index(0)

    loop.run()

if __name__ == "__main__":
    main()
