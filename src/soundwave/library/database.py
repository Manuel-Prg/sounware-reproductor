import sqlite3
import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


DB_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "soundwave"
DB_PATH = DB_DIR / "library.db"


@dataclass
class Song:
    id: Optional[int] = None
    filepath: str = ""
    title: str = ""
    artist: str = ""
    album: str = ""
    album_artist: str = ""
    track_number: int = 0
    disc_number: int = 1
    duration: float = 0.0
    genre: str = ""
    year: int = 0
    composer: str = ""
    has_embedded_art: bool = False
    art_mime: str = ""
    file_size: int = 0
    modified_at: float = 0.0
    added_at: float = 0.0
    play_count: int = 0
    last_played: Optional[float] = None
    rating: int = 0

    @property
    def display_title(self) -> str:
        return self.title or Path(self.filepath).stem

    @property
    def display_artist(self) -> str:
        return self.artist or "Artista desconocido"

    @property
    def display_album(self) -> str:
        return self.album or "Álbum desconocido"

    def asdict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if k != "id"}


@dataclass
class Playlist:
    id: Optional[int] = None
    name: str = ""
    song_ids: list[int] = field(default_factory=list)
    created_at: float = 0.0
    modified_at: float = 0.0


class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        DB_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filepath TEXT UNIQUE NOT NULL,
                title TEXT DEFAULT '',
                artist TEXT DEFAULT '',
                album TEXT DEFAULT '',
                album_artist TEXT DEFAULT '',
                track_number INTEGER DEFAULT 0,
                disc_number INTEGER DEFAULT 1,
                duration REAL DEFAULT 0.0,
                genre TEXT DEFAULT '',
                year INTEGER DEFAULT 0,
                composer TEXT DEFAULT '',
                has_embedded_art INTEGER DEFAULT 0,
                art_mime TEXT DEFAULT '',
                file_size INTEGER DEFAULT 0,
                modified_at REAL DEFAULT 0.0,
                added_at REAL DEFAULT 0.0,
                play_count INTEGER DEFAULT 0,
                last_played REAL,
                rating INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                song_ids TEXT DEFAULT '[]',
                created_at REAL DEFAULT 0.0,
                modified_at REAL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS playlists_songs (
                playlist_id INTEGER NOT NULL,
                song_id INTEGER NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (playlist_id, song_id),
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_songs_artist ON songs(artist);
            CREATE INDEX IF NOT EXISTS idx_songs_album ON songs(album);
            CREATE INDEX IF NOT EXISTS idx_songs_genre ON songs(genre);
            CREATE INDEX IF NOT EXISTS idx_songs_filepath ON songs(filepath);
        """)
        self.conn.commit()

    # ---- Songs ----
    def add_song(self, song: Song) -> int:
        cur = self.conn.execute("""
            INSERT INTO songs (filepath,title,artist,album,album_artist,
                track_number,disc_number,duration,genre,year,composer,
                has_embedded_art,art_mime,file_size,modified_at,added_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(filepath) DO UPDATE SET
                title=excluded.title, artist=excluded.artist,
                album=excluded.album, album_artist=excluded.album_artist,
                track_number=excluded.track_number, disc_number=excluded.disc_number,
                duration=excluded.duration, genre=excluded.genre,
                year=excluded.year, composer=excluded.composer,
                has_embedded_art=excluded.has_embedded_art,
                art_mime=excluded.art_mime, file_size=excluded.file_size,
                modified_at=excluded.modified_at
            RETURNING id
        """, (
            song.filepath, song.title, song.artist, song.album,
            song.album_artist, song.track_number, song.disc_number,
            song.duration, song.genre, song.year, song.composer,
            int(song.has_embedded_art), song.art_mime,
            song.file_size, song.modified_at, song.added_at
        ))
        self.conn.commit()
        return cur.fetchone()[0]

    def remove_song(self, song_id: int):
        self.conn.execute("DELETE FROM songs WHERE id = ?", (song_id,))
        self.conn.commit()

    def remove_song_by_path(self, filepath: str):
        self.conn.execute("DELETE FROM songs WHERE filepath = ?", (filepath,))
        self.conn.commit()

    def get_song(self, song_id: int) -> Optional[Song]:
        row = self.conn.execute("SELECT * FROM songs WHERE id = ?", (song_id,)).fetchone()
        return self._row_to_song(row) if row else None

    def get_song_by_path(self, filepath: str) -> Optional[Song]:
        row = self.conn.execute("SELECT * FROM songs WHERE filepath = ?", (filepath,)).fetchone()
        return self._row_to_song(row) if row else None

    def get_all_songs(self) -> list[Song]:
        rows = self.conn.execute("SELECT * FROM songs ORDER BY artist, album, track_number").fetchall()
        return [self._row_to_song(r) for r in rows]

    def search_songs(self, query: str) -> list[Song]:
        q = f"%{query}%"
        rows = self.conn.execute("""
            SELECT * FROM songs WHERE
                title LIKE ? OR artist LIKE ? OR album LIKE ? OR genre LIKE ?
            ORDER BY artist, album, track_number
        """, (q, q, q, q)).fetchall()
        return [self._row_to_song(r) for r in rows]

    def get_albums(self) -> list[dict]:
        rows = self.conn.execute("""
            SELECT album, album_artist,
                   COUNT(*) as song_count,
                   SUM(duration) as total_duration,
                   MAX(has_embedded_art) as has_art
            FROM songs WHERE album != ''
            GROUP BY album, album_artist
            ORDER BY album_artist, album
        """).fetchall()
        return [dict(r) for r in rows]

    def get_artists(self) -> list[dict]:
        rows = self.conn.execute("""
            SELECT artist, COUNT(*) as song_count,
                   COUNT(DISTINCT album) as album_count
            FROM songs WHERE artist != ''
            GROUP BY artist
            ORDER BY artist
        """).fetchall()
        return [dict(r) for r in rows]

    def get_songs_by_album(self, album: str, album_artist: str = "") -> list[Song]:
        rows = self.conn.execute("""
            SELECT * FROM songs WHERE album = ? AND album_artist = ?
            ORDER BY disc_number, track_number
        """, (album, album_artist)).fetchall()
        return [self._row_to_song(r) for r in rows]

    def get_songs_by_artist(self, artist: str) -> list[Song]:
        rows = self.conn.execute("""
            SELECT * FROM songs WHERE artist = ?
            ORDER BY album, disc_number, track_number
        """, (artist,)).fetchall()
        return [self._row_to_song(r) for r in rows]

    def update_play_count(self, song_id: int):
        self.conn.execute("""
            UPDATE songs SET play_count = play_count + 1,
                last_played = ? WHERE id = ?
        """, (__import__("time").time(), song_id))
        self.conn.commit()

    def update_rating(self, song_id: int, rating: int):
        rating = max(0, min(5, rating))
        self.conn.execute("UPDATE songs SET rating = ? WHERE id = ?", (rating, song_id))
        self.conn.commit()

    # ---- Playlists ----
    def create_playlist(self, name: str) -> int:
        now = __import__("time").time()
        cur = self.conn.execute(
            "INSERT INTO playlists (name, created_at, modified_at) VALUES (?, ?, ?)",
            (name, now, now)
        )
        self.conn.commit()
        return cur.lastrowid

    def delete_playlist(self, playlist_id: int):
        self.conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        self.conn.commit()

    def get_playlists(self) -> list[Playlist]:
        rows = self.conn.execute("SELECT * FROM playlists ORDER BY name").fetchall()
        playlists = []
        for r in rows:
            pl = Playlist(id=r["id"], name=r["name"],
                          created_at=r["created_at"], modified_at=r["modified_at"])
            song_rows = self.conn.execute(
                "SELECT song_id FROM playlists_songs WHERE playlist_id = ? ORDER BY position",
                (pl.id,)
            ).fetchall()
            pl.song_ids = [s["song_id"] for s in song_rows]
            playlists.append(pl)
        return playlists

    def add_to_playlist(self, playlist_id: int, song_id: int):
        max_pos = self.conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 as pos FROM playlists_songs WHERE playlist_id = ?",
            (playlist_id,)
        ).fetchone()["pos"]
        self.conn.execute(
            "INSERT OR IGNORE INTO playlists_songs (playlist_id, song_id, position) VALUES (?, ?, ?)",
            (playlist_id, song_id, max_pos)
        )
        self.conn.execute("UPDATE playlists SET modified_at = ? WHERE id = ?",
                          (__import__("time").time(), playlist_id))
        self.conn.commit()

    def remove_from_playlist(self, playlist_id: int, song_id: int):
        self.conn.execute(
            "DELETE FROM playlists_songs WHERE playlist_id = ? AND song_id = ?",
            (playlist_id, song_id)
        )
        self.conn.execute("UPDATE playlists SET modified_at = ? WHERE id = ?",
                          (__import__("time").time(), playlist_id))
        self.conn.commit()

    def reorder_playlist(self, playlist_id: int, song_ids: list[int]):
        now = __import__("time").time()
        self.conn.execute("DELETE FROM playlists_songs WHERE playlist_id = ?", (playlist_id,))
        for i, sid in enumerate(song_ids):
            self.conn.execute(
                "INSERT INTO playlists_songs (playlist_id, song_id, position) VALUES (?, ?, ?)",
                (playlist_id, sid, i)
            )
        self.conn.execute("UPDATE playlists SET modified_at = ? WHERE id = ?", (now, playlist_id))
        self.conn.commit()

    # ---- Stats ----
    def get_stats(self) -> dict:
        stats = self.conn.execute("""
            SELECT COUNT(*) as total_songs,
                   COUNT(DISTINCT artist) as total_artists,
                   COUNT(DISTINCT album) as total_albums,
                   COALESCE(SUM(duration), 0) as total_duration
            FROM songs
        """).fetchone()
        return dict(stats)

    # ---- Helpers ----
    def _row_to_song(self, row: sqlite3.Row) -> Song:
        return Song(
            id=row["id"], filepath=row["filepath"],
            title=row["title"], artist=row["artist"],
            album=row["album"], album_artist=row["album_artist"],
            track_number=row["track_number"], disc_number=row["disc_number"],
            duration=row["duration"], genre=row["genre"],
            year=row["year"], composer=row["composer"],
            has_embedded_art=bool(row["has_embedded_art"]),
            art_mime=row["art_mime"], file_size=row["file_size"],
            modified_at=row["modified_at"], added_at=row["added_at"],
            play_count=row["play_count"], last_played=row["last_played"],
            rating=row["rating"]
        )

    def close(self):
        self.conn.close()
