import unittest
import tempfile
import shutil
import json
from pathlib import Path
from soundwave.library.database import Database
from soundwave.services.sync import (
    export_library_to_dict,
    import_library_from_dict,
    sync_with_local_folder
)


class TestLibrarySync(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = Database(self.db_path)
        
        # Populate initial database
        self.db.conn.executescript("""
            INSERT INTO songs (filepath, title, artist, album, play_count, rating, last_played)
            VALUES
            ('/music/song1.mp3', 'Song One', 'Artist A', 'Album X', 5, 3, 1000.0),
            ('/music/song2.mp3', 'Song Two', 'Artist B', 'Album Y', 2, 4, 2000.0);
        """)
        self.db.conn.commit()

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.temp_dir)

    def test_export_library(self):
        data = export_library_to_dict(self.db)
        self.assertEqual(data["version"], 1)
        self.assertEqual(len(data["songs"]), 2)
        
        # Validate song structure
        song1 = next(s for s in data["songs"] if s["title"] == "Song One")
        self.assertEqual(song1["artist"], "Artist A")
        self.assertEqual(song1["play_count"], 5)
        self.assertEqual(song1["rating"], 3)

    def test_import_and_merge_stats(self):
        # Create metadata to merge (higher rating, more play count, newer last_played for Song One)
        merge_data = {
            "version": 1,
            "songs": [
                {
                    "filepath": "/music/different_path/song1.mp3", # Path might be different
                    "title": "Song One",
                    "artist": "Artist A",
                    "album": "Album X",
                    "play_count": 10, # higher (should merge to 10)
                    "rating": 5,      # higher (should merge to 5)
                    "last_played": 3000.0 # newer (should merge to 3000.0)
                },
                {
                    "filepath": "/music/song2.mp3",
                    "title": "Song Two",
                    "artist": "Artist B",
                    "album": "Album Y",
                    "play_count": 1,  # lower (should keep local 2)
                    "rating": 2,      # lower (should keep local 4)
                    "last_played": 1500.0 # older (should keep local 2000.0)
                }
            ]
        }
        
        import_library_from_dict(self.db, merge_data)
        
        # Check Song One
        row1 = self.db.conn.execute("SELECT play_count, rating, last_played FROM songs WHERE title = 'Song One'").fetchone()
        self.assertEqual(row1["play_count"], 10)
        self.assertEqual(row1["rating"], 5)
        self.assertEqual(row1["last_played"], 3000.0)
        
        # Check Song Two
        row2 = self.db.conn.execute("SELECT play_count, rating, last_played FROM songs WHERE title = 'Song Two'").fetchone()
        self.assertEqual(row2["play_count"], 2)
        self.assertEqual(row2["rating"], 4)
        self.assertEqual(row2["last_played"], 2000.0)

    def test_import_and_merge_playlists(self):
        # Create a playlist in the DB first
        pl_id = self.db.create_playlist("Favorites")
        # Add Song One (id=1) to Favorites
        self.db.add_to_playlist(pl_id, 1)
        
        # Merge data containing Favorites playlist (adding Song Two) and a new playlist
        merge_data = {
            "version": 1,
            "songs": [],
            "playlists": [
                {
                    "name": "Favorites",
                    "songs": [
                        {"title": "Song One", "artist": "Artist A", "album": "Album X"},
                        {"title": "Song Two", "artist": "Artist B", "album": "Album Y"}
                    ]
                },
                {
                    "name": "Chill Vibes",
                    "songs": [
                        {"title": "Song Two", "artist": "Artist B", "album": "Album Y"}
                    ]
                }
            ]
        }
        
        import_library_from_dict(self.db, merge_data)
        
        # Check playlists
        playlists = self.db.get_playlists()
        self.assertEqual(len(playlists), 2)
        
        favorites = next(p for p in playlists if p.name == "Favorites")
        # Favorites should contain both song 1 and song 2
        self.assertEqual(favorites.song_ids, [1, 2])
        
        chill = next(p for p in playlists if p.name == "Chill Vibes")
        self.assertEqual(chill.song_ids, [2])

    def test_local_folder_sync(self):
        sync_dir = Path(self.temp_dir) / "sync_folder"
        sync_dir.mkdir()
        
        # First sync to folder (creates the file)
        success = sync_with_local_folder(self.db, str(sync_dir))
        self.assertTrue(success)
        
        sync_file = sync_dir / "soundwave_sync.json"
        self.assertTrue(sync_file.exists())
        
        # Modify the file manually
        data = json.loads(sync_file.read_text(encoding="utf-8"))
        data["songs"][0]["rating"] = 5
        sync_file.write_text(json.dumps(data), encoding="utf-8")
        
        # Sync again (imports changes)
        success = sync_with_local_folder(self.db, str(sync_dir))
        self.assertTrue(success)
        
        row = self.db.conn.execute("SELECT rating FROM songs WHERE title = 'Song One'").fetchone()
        self.assertEqual(row["rating"], 5)
