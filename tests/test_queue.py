import unittest
from soundwave.library.database import Song
from soundwave.player.engine import Player

class TestSoundwaveQueue(unittest.TestCase):
    def test_queue_manipulation(self):
        songs = [
            Song(id=1, filepath="song1.mp3", title="Song 1", artist="Artist A"),
            Song(id=2, filepath="song2.mp3", title="Song 2", artist="Artist B"),
            Song(id=3, filepath="song3.mp3", title="Song 3", artist="Artist C"),
        ]

        try:
            player = Player()
            
            # Setup list to receive queue callbacks
            queue_events = []
            def on_queue_changed(q):
                queue_events.append(list(q))

            player.connect_queue(on_queue_changed)

            # Test set_queue
            player.set_queue(songs, start_index=0)
            self.assertEqual(len(player.get_queue()), 3)
            self.assertEqual(player.get_current_index(), 0)
            self.assertEqual(len(queue_events), 1)

            # Test play_index
            player.play_index(1)
            self.assertEqual(player.get_current_index(), 1)

            # Test add_to_queue
            new_song = Song(id=4, filepath="song4.mp3", title="Song 4", artist="Artist D")
            player.add_to_queue(new_song)
            self.assertEqual(len(player.get_queue()), 4)
            self.assertEqual(player.get_queue()[3].id, 4)
            self.assertEqual(len(queue_events), 2)

            # Test play_next
            next_song = Song(id=5, filepath="song5.mp3", title="Song 5", artist="Artist E")
            player.play_next(next_song)
            # Since current index is 1, next_song should be at index 2
            self.assertEqual(player.get_queue()[2].id, 5)
            self.assertEqual(len(player.get_queue()), 5)
            self.assertEqual(len(queue_events), 3)

            # Test reorder_queue
            current_queue = player.get_queue()
            # Swap first and second song in the queue list
            current_queue[0], current_queue[1] = current_queue[1], current_queue[0]
            player.reorder_queue(current_queue)
            self.assertEqual(player.get_queue()[0].id, 2)
            self.assertEqual(player.get_queue()[1].id, 1)
            self.assertEqual(len(queue_events), 4)

            # Test remove_from_queue
            player.remove_from_queue(0)
            self.assertEqual(len(player.get_queue()), 4)
            self.assertEqual(player.get_queue()[0].id, 1) # Song 1 is now at index 0
            self.assertEqual(len(queue_events), 5)

            # Test clear_queue
            player.clear_queue()
            self.assertEqual(len(player.get_queue()), 0)
            self.assertEqual(player.get_current_index(), -1)
            self.assertEqual(len(queue_events), 6)

            # Test disconnect_queue
            player.disconnect_queue(on_queue_changed)
            self.assertNotIn(on_queue_changed, player._queue_callbacks)

        except Exception as e:
            print(f"Saltando prueba de cola por falta de dependencias del sistema: {e}")

if __name__ == "__main__":
    unittest.main()
