import unittest
import tempfile
import shutil
from pathlib import Path
from soundwave.library.database import Database
from soundwave.library.playlists.m3u8 import (
    import_playlist_from_m3u8,
    export_playlist_to_m3u8
)


class TestPlaylistsM3U8(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = Database(self.db_path)
        
        # Populate initial database
        self.db.conn.executescript("""
            INSERT INTO songs (id, filepath, title, artist, album, duration)
            VALUES
            (1, '/music/song1.mp3', 'Song One', 'Artist A', 'Album X', 180.0),
            (2, '/music/song2.mp3', 'Song Two', 'Artist B', 'Album Y', 240.0);
        """)
        self.db.conn.commit()

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.temp_dir)

    def test_import_playlist_m3u8_absolute_paths(self):
        playlist_content = (
            "#EXTM3U\n"
            "#EXTINF:180,Artist A - Song One\n"
            "/music/song1.mp3\n"
            "#EXTINF:240,Artist B - Song Two\n"
            "/music/song2.mp3\n"
        )
        
        playlist_path = Path(self.temp_dir) / "MisFavoritas.m3u8"
        playlist_path.write_text(playlist_content, encoding="utf-8")
        
        created_name = import_playlist_from_m3u8(self.db, playlist_path)
        self.assertEqual(created_name, "MisFavoritas")
        
        playlists = self.db.get_playlists()
        self.assertEqual(len(playlists), 1)
        self.assertEqual(playlists[0].name, "MisFavoritas")
        self.assertEqual(playlists[0].song_ids, [1, 2])

    def test_import_playlist_m3u8_relative_paths(self):
        # Place relative files relative to playlist_path
        # song1.mp3 is inside same folder as the playlist
        # song2.mp3 is inside subdir
        
        playlist_content = (
            "#EXTM3U\n"
            "song1.mp3\n"
            "subdir/song2.mp3\n"
        )
        
        playlist_dir = Path(self.temp_dir) / "playlists"
        playlist_dir.mkdir()
        playlist_path = playlist_dir / "RelativePlaylist.m3u8"
        playlist_path.write_text(playlist_content, encoding="utf-8")
        
        # Clean insert to use paths matching resolution
        resolved_path1 = (playlist_dir / "song1.mp3").resolve()
        resolved_path2 = (playlist_dir / "subdir/song2.mp3").resolve()
        
        self.db.conn.execute("DELETE FROM songs")
        self.db.conn.execute(
            "INSERT INTO songs (id, filepath, title, artist, album, duration) VALUES (?, ?, ?, ?, ?, ?)",
            (1, str(resolved_path1), "Song One", "Artist A", "Album X", 180.0)
        )
        self.db.conn.execute(
            "INSERT INTO songs (id, filepath, title, artist, album, duration) VALUES (?, ?, ?, ?, ?, ?)",
            (2, str(resolved_path2), "Song Two", "Artist B", "Album Y", 240.0)
        )
        self.db.conn.commit()
        
        created_name = import_playlist_from_m3u8(self.db, playlist_path)
        self.assertEqual(created_name, "RelativePlaylist")
        
        playlists = self.db.get_playlists()
        self.assertEqual(len(playlists), 1)
        self.assertEqual(playlists[0].song_ids, [1, 2])

    def test_import_playlist_deduplication(self):
        playlist_content = (
            "#EXTM3U\n"
            "/music/song1.mp3\n"
        )
        playlist_path = Path(self.temp_dir) / "Dupa.m3u"
        playlist_path.write_text(playlist_content, encoding="utf-8")
        
        name1 = import_playlist_from_m3u8(self.db, playlist_path)
        self.assertEqual(name1, "Dupa")
        
        name2 = import_playlist_from_m3u8(self.db, playlist_path)
        self.assertEqual(name2, "Dupa (1)")
        
        name3 = import_playlist_from_m3u8(self.db, playlist_path)
        self.assertEqual(name3, "Dupa (2)")

    def test_export_playlist_m3u8(self):
        playlist_id = self.db.create_playlist("Top Hits")
        self.db.add_to_playlist(playlist_id, 1)
        self.db.add_to_playlist(playlist_id, 2)
        
        export_path = Path(self.temp_dir) / "TopHits_Export.m3u8"
        export_playlist_to_m3u8(self.db, playlist_id, export_path, also_export_file_based=False)
        
        self.assertTrue(export_path.exists())
        content = export_path.read_text(encoding="utf-8")
        
        expected_lines = [
            "#EXTM3U",
            "#EXTINF:180,Artist A - Song One",
            "/music/song1.mp3",
            "#EXTINF:240,Artist B - Song Two",
            "/music/song2.mp3",
            ""
        ]
        self.assertEqual(content, "\n".join(expected_lines))

    def test_export_playlist_m3u8_and_pls(self):
        playlist_id = self.db.create_playlist("Top Hits")
        self.db.add_to_playlist(playlist_id, 1)
        self.db.add_to_playlist(playlist_id, 2)
        
        export_path = Path(self.temp_dir) / "TopHits_Export.m3u8"
        export_playlist_to_m3u8(self.db, playlist_id, export_path, also_export_file_based=True)
        
        self.assertTrue(export_path.exists())
        
        # Verify PLS file
        pls_path = export_path.with_suffix(".pls")
        self.assertTrue(pls_path.exists())
        pls_content = pls_path.read_text(encoding="utf-8")
        
        expected_lines = [
            "[playlist]",
            "NumberOfEntries=2",
            "File1=/music/song1.mp3",
            "Title1=Artist A - Song One",
            "Length1=180",
            "File2=/music/song2.mp3",
            "Title2=Artist B - Song Two",
            "Length2=240",
            "Version=2",
            ""
        ]
        self.assertEqual(pls_content, "\n".join(expected_lines))

    def test_import_playlist_fallback_lookups(self):
        # 1. Filename-only match fallback
        # Let's say the playlist references a file that has a completely different parent directory
        # but the filename matches a file in the DB
        playlist_content = (
            "#EXTM3U\n"
            "/wrong/path/to/song1.mp3\n"
        )
        playlist_path = Path(self.temp_dir) / "FallbackPlaylist.m3u8"
        playlist_path.write_text(playlist_content, encoding="utf-8")
        
        # In setUp, song1.mp3 was inserted with filepath '/music/song1.mp3'
        created_name = import_playlist_from_m3u8(self.db, playlist_path)
        self.assertEqual(created_name, "FallbackPlaylist")
        
        playlists = self.db.get_playlists()
        self.assertEqual(len(playlists), 1)
        self.assertEqual(playlists[0].song_ids, [1])
