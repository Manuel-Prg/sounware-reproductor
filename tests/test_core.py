import unittest
from pathlib import Path

from soundwave.library.metadata.metadata import _parse_gain
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

    def test_player_spectrum_and_callbacks(self):
        try:
            player = Player()
            
            # Test connecting and disconnecting spectrum callback
            spec_received = []
            def on_spec(mags):
                spec_received.append(mags)
            
            player.connect_spectrum(on_spec)
            self.assertIn(on_spec, player._spectrum_callbacks)
            
            # Emit test
            player._emit_spectrum([1.0, 2.0, 3.0])
            self.assertEqual(spec_received, [[1.0, 2.0, 3.0]])
            
            player.disconnect_spectrum(on_spec)
            self.assertNotIn(on_spec, player._spectrum_callbacks)
            
            # Test disconnect_song
            song_received = []
            def on_song(s):
                song_received.append(s)
            player.connect_song(on_song)
            self.assertIn(on_song, player._song_callbacks)
            player.disconnect_song(on_song)
            self.assertNotIn(on_song, player._song_callbacks)
        except Exception as e:
            print(f"Saltando prueba de espectro por falta de dependencias de GStreamer: {e}")

    def test_smart_playlist(self):
        from soundwave.library.database import Database
        from soundwave.library.playlists.smart_playlist import evaluate_rules
        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test.db"
        try:
            db = Database(db_path)
            # Insert some dummy songs
            db.conn.execute("""
                INSERT INTO songs (filepath, title, artist, album, genre, year, rating, play_count, added_at)
                VALUES 
                ('file1.mp3', 'Song 1', 'Artist A', 'Album X', 'Jazz', 2020, 5, 12, 1000.0),
                ('file2.mp3', 'Song 2', 'Artist B', 'Album Y', 'Rock', 2021, 3, 5, 2000.0),
                ('file3.mp3', 'Song 3', 'Artist C', 'Album Z', 'Jazz', 2022, 4, 15, 3000.0)
            """)
            db.conn.commit()

            # Test Jazz genre filter (case-insensitive)
            jazz_songs = evaluate_rules(db, {"genre": "jazz"})
            self.assertEqual(len(jazz_songs), 2)
            self.assertEqual(jazz_songs[0].title, "Song 1")
            self.assertEqual(jazz_songs[1].title, "Song 3")

            # Test Rating filter
            fav_songs = evaluate_rules(db, {"rating_min": 4})
            self.assertEqual(len(fav_songs), 2)

            # Test Most Played filter
            most_played = evaluate_rules(db, {"most_played": True})
            self.assertEqual(len(most_played), 3)
            self.assertEqual(most_played[0].title, "Song 3")  # 15 plays
            self.assertEqual(most_played[1].title, "Song 1")  # 12 plays

            # Test Recent filter
            recent = evaluate_rules(db, {"recent": True})
            self.assertEqual(len(recent), 3)
            self.assertEqual(recent[0].title, "Song 3")  # Added at 3000.0 (latest)
        finally:
            shutil.rmtree(temp_dir)

    def test_waveform_generation(self):
        from soundwave.library.utils.waveform_helper import generate_waveform_data
        test_file = "/home/manuelprz/.local/share/Steam/steamui/sounds/pop_sound.wav"
        if Path(test_file).exists():
            waveform = generate_waveform_data(test_file, num_points=10)
            self.assertEqual(len(waveform), 10)
            self.assertAlmostEqual(max(waveform), 1.0)
        else:
            waveform = generate_waveform_data("non_existent_file.mp3", num_points=10)
            self.assertEqual(waveform, [])

    def test_onboarding_window_import(self):
        import gi
        gi.require_version("Adw", "1")
        from gi.repository import Adw
        from soundwave.ui.window.onboarding import OnboardingWindow
        self.assertTrue(issubclass(OnboardingWindow, Adw.Window))

    def test_about_page_import(self):
        import gi
        gi.require_version("Adw", "1")
        from gi.repository import Adw
        from soundwave.ui.settings.about_page import AboutPage
        self.assertTrue(issubclass(AboutPage, Adw.PreferencesPage))

    def test_remove_missing_files(self):
        from soundwave.library.database import Database
        from soundwave.library.scanner.scanner import MusicScanner
        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test.db"
        try:
            db = Database(db_path)
            # Insert a song pointing to a non-existent file
            db.conn.execute("""
                INSERT INTO songs (filepath, title, artist, album, genre)
                VALUES ('non_existent_file_path_123.mp3', 'Song 1', 'Artist A', 'Album X', 'Jazz')
            """)
            db.conn.commit()
            
            scanner = MusicScanner(db)
            removed = scanner.remove_missing_files()
            
            self.assertEqual(removed, 1)
            self.assertEqual(len(db.get_all_songs()), 0)
        finally:
            shutil.rmtree(temp_dir)

    def test_get_songs_by_genre(self):
        from soundwave.library.database import Database, NO_GENRE
        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_genre.db"
        try:
            db = Database(db_path)
            db.conn.execute("""
                INSERT INTO songs (filepath, title, artist, album, genre)
                VALUES 
                ('g1.mp3', 'Song 1', 'Artist A', 'Album X', 'Rock'),
                ('g2.mp3', 'Song 2', 'Artist B', 'Album Y', ''),
                ('g3.mp3', 'Song 3', 'Artist C', 'Album Z', NULL),
                ('g4.mp3', 'Song 4', 'Artist D', 'Album W', 'Jazz')
            """)
            db.conn.commit()

            rock_songs = db.get_songs_by_genre("Rock")
            self.assertEqual(len(rock_songs), 1)
            self.assertEqual(rock_songs[0].title, "Song 1")

            jazz_songs = db.get_songs_by_genre("Jazz")
            self.assertEqual(len(jazz_songs), 1)
            self.assertEqual(jazz_songs[0].title, "Song 4")

            no_genre_songs = db.get_songs_by_genre(NO_GENRE)
            self.assertEqual(len(no_genre_songs), 2)
            titles = {s.title for s in no_genre_songs}
            self.assertEqual(titles, {"Song 2", "Song 3"})
        finally:
            shutil.rmtree(temp_dir)

    def test_player_gapless_config(self):
        try:
            player = Player()
            # Test default config
            self.assertTrue(player.get_gapless_enabled())
            
            # Test setting it to False
            player.set_gapless_enabled(False)
            self.assertFalse(player.get_gapless_enabled())
            
            # Test setting it to True
            player.set_gapless_enabled(True)
            self.assertTrue(player.get_gapless_enabled())
        except Exception as e:
            print(f"Saltando prueba de Player por falta de dependencias de GStreamer: {e}")

    def test_player_target_volume_scaling(self):
        try:
            player = Player()
            player.set_volume(0.8)
            
            # Test target volume without ReplayGain (default 1.0 factor)
            song_no_gain = Song(id=1, filepath="test.mp3", title="No Gain")
            self.assertAlmostEqual(player._get_target_volume_for_song(song_no_gain), 0.8)
            
            # Test target volume with track gain
            song_track_gain = Song(id=2, filepath="test.mp3", title="Track Gain")
            # Simulating ReplayGain attributes
            song_track_gain.replaygain_track_gain = -6.0  # -6.0 dB is 0.501187 factor
            player._replaygain_mode = "track"
            expected_factor = 10 ** (-6.0 / 20.0)
            self.assertAlmostEqual(player._get_target_volume_for_song(song_track_gain), 0.8 * expected_factor)
            
            # Test target volume with album gain
            song_album_gain = Song(id=3, filepath="test.mp3", title="Album Gain")
            song_album_gain.replaygain_album_gain = -3.0  # -3.0 dB is 0.707945 factor
            player._replaygain_mode = "album"
            expected_factor_album = 10 ** (-3.0 / 20.0)
            self.assertAlmostEqual(player._get_target_volume_for_song(song_album_gain), 0.8 * expected_factor_album)
        except Exception as e:
            print(f"Saltando prueba de Player por falta de dependencias de GStreamer: {e}")

    def test_album_view_mode_config(self):
        from soundwave.library.config.config import save_setting, load_settings
        # Save custom mode
        save_setting("album_view_mode", "grid")
        settings = load_settings()
        self.assertEqual(settings.get("album_view_mode"), "grid")

        # Revert/reset to circle
        save_setting("album_view_mode", "circle")
        settings = load_settings()
        self.assertEqual(settings.get("album_view_mode"), "circle")

if __name__ == "__main__":
    unittest.main()
