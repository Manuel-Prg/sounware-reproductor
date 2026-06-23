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

def main():
    Gst.init(None)
    loop = GLib.MainLoop()

    player = Player()
    player._crossfade_duration = 2.0

    song1 = Song(id=1, filepath="/usr/share/sounds/sound-icons/xylofon.wav", title="Song 1", artist="Artist A")
    song2 = Song(id=2, filepath="/usr/share/sounds/sound-icons/cembalo-6.wav", title="Song 2", artist="Artist B")

    print(f"Setting queue with two songs...")
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
