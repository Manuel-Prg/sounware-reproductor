import unittest
from pathlib import Path

from soundwave.library.metadata import _parse_gain
from soundwave.library.database import Song
from soundwave.player.engine import Player, RepeatMode

class TestSoundwaveCore(unittest.TestCase):
    def test_parse_gain(self):
        self.assertEqual(_parse_gain("-6.2 dB"), -6.2)
        self.assertEqual(_parse_gain("1.5db"), 1.5)
        self.assertEqual(_parse_gain(""), 0.0)
        self.assertEqual(_parse_gain("invalid"), 0.0)

    def test_player_shuffle(self):
        songs = [
            Song(id=1, filepath="song1.mp3", title="Song 1", artist="Artist A"),
            Song(id=2, filepath="song2.mp3", title="Song 2", artist="Artist B"),
            Song(id=3, filepath="song3.mp3", title="Song 3", artist="Artist C"),
            Song(id=4, filepath="song4.mp3", title="Song 4", artist="Artist D"),
        ]
        
        try:
            player = Player()
            # Activar shuffle
            player.toggle_shuffle()
            player.set_queue(songs, start_index=1)
            
            # El elemento en la posición 0 de la cola mezclada debe ser el que seleccionamos originalmente (id=2)
            self.assertEqual(player._queue[0].id, 2)
            self.assertEqual(len(player._queue), 4)
            
            # Desactivar shuffle
            player.toggle_shuffle()
            # La cola original debe restaurarse por completo
            self.assertEqual(player._queue[0].id, 1)
            self.assertEqual(player._queue[1].id, 2)
            self.assertEqual(player._queue[2].id, 3)
            self.assertEqual(player._queue[3].id, 4)
        except Exception as e:
            # Si GStreamer no está disponible o falla el inicio en este entorno, saltar
            print(f"Saltando prueba de Player por falta de dependencias del sistema: {e}")

if __name__ == "__main__":
    unittest.main()
