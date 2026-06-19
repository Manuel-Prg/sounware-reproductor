import os
from pathlib import Path
from typing import Optional

from soundwave.library.database import Database
from soundwave.library.metadata import (
    extract_embedded_art, find_external_cover, get_art_mime_type
)

CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "soundwave" / "album_art"
TMP_ART_DIR = Path("/tmp/soundwave_art")
MAX_TMP_FILES = 500


def _export_art_to_tmp(song_id: int, source_path: Path):
    try:
        TMP_ART_DIR.mkdir(parents=True, exist_ok=True)
        tmp_file = TMP_ART_DIR / f"{song_id}.jpg"
        tmp_file.write_bytes(source_path.read_bytes())
    except Exception as e:
        print(f"Error al copiar carátula a /tmp/soundwave_art: {e}")


def _cleanup_tmp_art():
    try:
        if TMP_ART_DIR.exists():
            files = sorted(TMP_ART_DIR.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
            for f in files[MAX_TMP_FILES:]:
                f.unlink()
    except Exception:
        pass


def get_art_path(song_id: int, db: Database) -> Optional[Path]:
    song = db.get_song(song_id)
    if song is None:
        return None

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cleanup_tmp_art()

    cached = CACHE_DIR / f"{song_id}.jpg"
    if cached.exists():
        _export_art_to_tmp(song_id, cached)
        return cached

    cached_png = CACHE_DIR / f"{song_id}.png"
    if cached_png.exists():
        _export_art_to_tmp(song_id, cached_png)
        return cached_png

    # Try embedded art first
    art_data = extract_embedded_art(song.filepath)
    if art_data:
        ext = ".png" if song.art_mime == "image/png" else ".jpg"
        out_path = CACHE_DIR / f"{song_id}{ext}"
        out_path.write_bytes(art_data)
        _export_art_to_tmp(song_id, out_path)
        return out_path

    # Try external cover in the song's directory
    song_path = Path(song.filepath)
    ext_cover = find_external_cover(song_path.parent)
    if ext_cover:
        out_path = CACHE_DIR / f"{song_id}{ext_cover.suffix}"
        out_path.write_bytes(ext_cover.read_bytes())
        _export_art_to_tmp(song_id, out_path)
        return out_path

    # Try album-level art from another song with same album
    if song.album:
        album_songs = db.get_songs_by_album(song.album, song.album_artist)
        for other in album_songs:
            if other.id == song.id:
                continue
            other_cached = CACHE_DIR / f"{other.id}.jpg"
            if other_cached.exists():
                _export_art_to_tmp(song_id, other_cached)
                return other_cached
            other_cached_png = CACHE_DIR / f"{other.id}.png"
            if other_cached_png.exists():
                _export_art_to_tmp(song_id, other_cached_png)
                return other_cached_png
            other_art = extract_embedded_art(other.filepath)
            if other_art:
                mime = other.art_mime
                ext = ".png" if mime == "image/png" else ".jpg"
                out_path = CACHE_DIR / f"{song_id}{ext}"
                out_path.write_bytes(other_art)
                _export_art_to_tmp(song_id, out_path)
                return out_path
            other_ext = find_external_cover(Path(other.filepath).parent)
            if other_ext:
                out_path = CACHE_DIR / f"{song_id}{other_ext.suffix}"
                out_path.write_bytes(other_ext.read_bytes())
                _export_art_to_tmp(song_id, out_path)
                return out_path

    return None


def clear_cache():
    if CACHE_DIR.exists():
        for f in CACHE_DIR.iterdir():
            if f.is_file():
                f.unlink()
