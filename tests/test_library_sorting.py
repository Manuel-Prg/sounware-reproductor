import unittest
from pathlib import Path
import tempfile
import shutil

from soundwave.library.database.database import Database, Song

class TestLibrarySorting(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_sorting.db"
        self.db = Database(self.db_path)

        # Insert test songs with various fields to verify sorting
        self.db.conn.execute("""
            INSERT INTO songs (filepath, title, artist, album, album_artist, duration, genre, year, composer, added_at)
            VALUES 
            ('file1.mp3', 'Beta Song', 'Artist Zebra', 'Gamma Album', 'Zebra Artist', 120.0, 'Jazz', 2010, 'Composer Charlie', 1000.0),
            ('file2.mp3', 'Alpha Song', 'Artist Alpha', 'Alpha Album', 'Alpha Artist', 180.0, 'Rock', 2020, 'Composer Bravo', 3000.0),
            ('file3.mp3', 'Gamma Song', 'Artist Mike', 'Beta Album', 'Mike Artist', 240.0, 'Pop', 2015, 'Composer Alpha', 2000.0)
        """)
        self.db.conn.commit()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_get_albums_contains_aggregated_sorting_fields(self):
        albums = self.db.get_albums()
        self.assertEqual(len(albums), 3)
        
        # Verify that new sorting columns are present in query results
        for alb in albums:
            self.assertIn("year", alb)
            self.assertIn("added_at", alb)
            self.assertIn("artist", alb)
            self.assertIn("composer", alb)

    def test_song_sorting_logic(self):
        songs = self.db.get_all_songs()
        self.assertEqual(len(songs), 3)

        # Helper to sort songs by criteria and order
        def sort_songs(criteria, order):
            descending = (order == "desc")
            def sort_key(s: Song):
                if criteria == "title":
                    return (s.title or "").lower()
                elif criteria == "artist":
                    return (s.artist or "").lower()
                elif criteria == "album":
                    return (s.album or "").lower()
                elif criteria == "duration":
                    return s.duration or 0.0
                elif criteria == "year":
                    return s.year or 0
                elif criteria == "date":
                    return s.added_at or 0.0
                elif criteria == "composer":
                    return (s.composer or "").lower()
                return (s.title or "").lower()

            songs.sort(key=sort_key, reverse=descending)
            return [s.title for s in songs]

        # 1. Title Ascending
        self.assertEqual(sort_songs("title", "asc"), ["Alpha Song", "Beta Song", "Gamma Song"])
        # 2. Title Descending
        self.assertEqual(sort_songs("title", "desc"), ["Gamma Song", "Beta Song", "Alpha Song"])
        # 3. Artist Ascending
        self.assertEqual(sort_songs("artist", "asc"), ["Alpha Song", "Gamma Song", "Beta Song"])
        # 4. Duration Descending
        self.assertEqual(sort_songs("duration", "desc"), ["Gamma Song", "Alpha Song", "Beta Song"])
        # 5. Year Ascending
        self.assertEqual(sort_songs("year", "asc"), ["Beta Song", "Gamma Song", "Alpha Song"])
        # 6. Date Descending
        self.assertEqual(sort_songs("date", "desc"), ["Alpha Song", "Gamma Song", "Beta Song"])
        # 7. Composer Ascending
        self.assertEqual(sort_songs("composer", "asc"), ["Gamma Song", "Alpha Song", "Beta Song"])

    def test_album_sorting_logic(self):
        albums = self.db.get_albums()
        self.assertEqual(len(albums), 3)

        # Helper to sort albums by criteria and order
        def sort_albums(criteria, order):
            descending = (order == "desc")
            def sort_key(a: dict):
                if criteria == "album":
                    return (a.get("album") or "").lower()
                elif criteria == "song_count":
                    return a.get("song_count") or 0
                elif criteria == "total_duration":
                    return a.get("total_duration") or 0.0
                elif criteria == "year":
                    return a.get("year") or 0
                elif criteria == "date":
                    return a.get("added_at") or 0.0
                elif criteria == "artist":
                    return (a.get("artist") or "").lower()
                elif criteria == "album_artist":
                    return (a.get("album_artist") or "").lower()
                elif criteria == "composer":
                    return (a.get("composer") or "").lower()
                return (a.get("album") or "").lower()

            albums.sort(key=sort_key, reverse=descending)
            return [a["album"] for a in albums]

        # 1. Album Name Ascending
        self.assertEqual(sort_albums("album", "asc"), ["Alpha Album", "Beta Album", "Gamma Album"])
        # 2. Album Name Descending
        self.assertEqual(sort_albums("album", "desc"), ["Gamma Album", "Beta Album", "Alpha Album"])
        # 3. Year Ascending
        self.assertEqual(sort_albums("year", "asc"), ["Gamma Album", "Beta Album", "Alpha Album"])
        # 4. Total Duration Descending
        self.assertEqual(sort_albums("total_duration", "desc"), ["Beta Album", "Alpha Album", "Gamma Album"])

    def test_playlist_reordering_and_sorting(self):
        # 1. Create a playlist
        playlist_id = self.db.create_playlist("Test Playlist")
        
        # 2. Get song ids
        songs = self.db.get_all_songs()
        song_ids = [s.id for s in songs]
        
        # Add to playlist in that order
        self.db.add_to_playlist(playlist_id, song_ids[0])
        self.db.add_to_playlist(playlist_id, song_ids[1])
        self.db.add_to_playlist(playlist_id, song_ids[2])
        
        # 3. Reorder playlist
        new_order = [song_ids[2], song_ids[0], song_ids[1]]
        self.db.reorder_playlist(playlist_id, new_order)
        
        # 4. Retrieve playlist and check song_ids order
        playlists = self.db.get_playlists()
        my_pl = [p for p in playlists if p.id == playlist_id][0]
        self.assertEqual(my_pl.song_ids, new_order)
        
        # 5. Test sorting by "playlist"
        self._current_playlist_id = playlist_id
        self._song_sort_criteria = "playlist"
        self._song_sort_order = "asc"
        
        # Verify sort key logic
        def sort_key(s: Song):
            criteria = self._song_sort_criteria
            playlist_id = self._current_playlist_id
            if criteria == "playlist" and playlist_id is not None:
                if not hasattr(self, "_playlist_pos_cache") or getattr(self, "_playlist_pos_cache_id", None) != playlist_id:
                    rows = self.db.conn.execute(
                        "SELECT song_id, position FROM playlists_songs WHERE playlist_id = ? ORDER BY position",
                        (playlist_id,)
                    ).fetchall()
                    self._playlist_pos_cache = {r["song_id"]: r["position"] for r in rows}
                    self._playlist_pos_cache_id = playlist_id
                return self._playlist_pos_cache.get(s.id, 999999)
            return (s.title or "").lower()
            
        test_songs = list(songs)
        test_songs.sort(key=sort_key)
        
        sorted_ids = [s.id for s in test_songs]
        self.assertEqual(sorted_ids, new_order)

