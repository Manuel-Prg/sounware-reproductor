import os
from pathlib import Path
from typing import Optional

from soundwave.library.database import Database
from soundwave.library.metadata import (
    extract_embedded_art, find_external_cover, get_art_mime_type
)

CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "soundwave" / "album_art"


def get_art_path(song_id: int, db: Database) -> Optional[Path]:
    song = db.get_song(song_id)
    if song is None:
        return None

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = CACHE_DIR / f"{song_id}.jpg"
    if cached.exists():
        return cached

    cached_png = CACHE_DIR / f"{song_id}.png"
    if cached_png.exists():
        return cached_png

    # Try embedded art first
    art_data = extract_embedded_art(song.filepath)
    if art_data:
        ext = ".png" if song.art_mime == "image/png" else ".jpg"
        out_path = CACHE_DIR / f"{song_id}{ext}"
        out_path.write_bytes(art_data)
        return out_path

    # Try external cover in the song's directory
    song_path = Path(song.filepath)
    ext_cover = find_external_cover(song_path.parent)
    if ext_cover:
        out_path = CACHE_DIR / f"{song_id}{ext_cover.suffix}"
        out_path.write_bytes(ext_cover.read_bytes())
        return out_path

    # Try album-level art from another song with same album
    if song.album:
        album_songs = db.get_songs_by_album(song.album, song.album_artist)
        for other in album_songs:
            if other.id == song.id:
                continue
            other_cached = CACHE_DIR / f"{other.id}.jpg"
            if other_cached.exists():
                return other_cached
            other_cached_png = CACHE_DIR / f"{other.id}.png"
            if other_cached_png.exists():
                return other_cached_png
            other_art = extract_embedded_art(other.filepath)
            if other_art:
                mime = other.art_mime
                ext = ".png" if mime == "image/png" else ".jpg"
                out_path = CACHE_DIR / f"{song_id}{ext}"
                out_path.write_bytes(other_art)
                return out_path
            other_ext = find_external_cover(Path(other.filepath).parent)
            if other_ext:
                out_path = CACHE_DIR / f"{song_id}{other_ext.suffix}"
                out_path.write_bytes(other_ext.read_bytes())
                return out_path

    return None


def clear_cache():
    if CACHE_DIR.exists():
        for f in CACHE_DIR.iterdir():
            f.unlink()
