import os
import urllib.parse
import requests
from pathlib import Path
from typing import Optional
import io
import sqlite3

from soundwave.library.database.database import Database
from soundwave.library.metadata.metadata import (
    extract_embedded_art, find_external_cover, get_art_mime_type
)

CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "soundwave" / "album_art"
TMP_ART_DIR = Path("/tmp/soundwave_art")
MAX_TMP_FILES = 500


def _validate_image_data(data: bytes) -> bool:
    """Validate that image data is valid and can be processed."""
    if not data or len(data) < 8:
        return False
    
    # Check for common image signatures
    if data.startswith(b'\x89PNG'):
        return True  # PNG
    elif data.startswith(b'\xff\xd8\xff'):
        return True  # JPEG
    elif data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return True  # WebP
    elif data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
        return True  # GIF
    elif data.startswith(b'BM'):
        return True  # BMP
    
    return False


def _export_art_to_tmp(song_id: int, source_path: Path):
    try:
        TMP_ART_DIR.mkdir(parents=True, exist_ok=True)
        tmp_file = TMP_ART_DIR / f"{song_id}.jpg"
        
        # Validate image data before copying
        image_data = source_path.read_bytes()
        if not _validate_image_data(image_data):
            print(f"Invalid image data for song {song_id}, skipping")
            return
            
        tmp_file.write_bytes(image_data)
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
    try:
        # Validate song_id
        if song_id is None or song_id == 0:
            return None
        
        song = db.get_song(song_id)
        if song is None:
            return None

        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Return cached file if exists
        cached = CACHE_DIR / f"{song_id}.jpg"
        if cached.exists():
            return cached

        cached_png = CACHE_DIR / f"{song_id}.png"
        if cached_png.exists():
            return cached_png

        # Try embedded art first
        try:
            art_data = extract_embedded_art(song.filepath)
            if art_data and _validate_image_data(art_data):
                ext = ".png" if song.art_mime == "image/png" else ".jpg"
                out_path = CACHE_DIR / f"{song_id}{ext}"
                out_path.write_bytes(art_data)
                return out_path
        except Exception as e:
            print(f"Error extracting embedded art for song {song_id}: {type(e).__name__}: {e}")

        # Try external cover in the song's directory
        try:
            song_path = Path(song.filepath)
            ext_cover = find_external_cover(song_path.parent)
            if ext_cover:
                cover_data = ext_cover.read_bytes()
                if _validate_image_data(cover_data):
                    out_path = CACHE_DIR / f"{song_id}{ext_cover.suffix}"
                    out_path.write_bytes(cover_data)
                    return out_path
        except Exception as e:
            print(f"Error reading external cover for song {song_id}: {type(e).__name__}: {e}")

        # Try album-level art from another song with same album
        if song.album:
            try:
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
                    try:
                        other_art = extract_embedded_art(other.filepath)
                        if other_art and _validate_image_data(other_art):
                            mime = other.art_mime
                            ext = ".png" if mime == "image/png" else ".jpg"
                            out_path = CACHE_DIR / f"{song_id}{ext}"
                            out_path.write_bytes(other_art)
                            return out_path
                    except Exception as e:
                        print(f"Error extracting other embedded art for song {song_id}: {type(e).__name__}: {e}")
                    try:
                        other_ext = find_external_cover(Path(other.filepath).parent)
                        if other_ext:
                            other_cover_data = other_ext.read_bytes()
                            if _validate_image_data(other_cover_data):
                                out_path = CACHE_DIR / f"{song_id}{other_ext.suffix}"
                                out_path.write_bytes(other_cover_data)
                                return out_path
                    except Exception as e:
                        print(f"Error reading other cover for song {song_id}: {type(e).__name__}: {e}")
            except Exception as e:
                print(f"Error processing album art for song {song_id}: {type(e).__name__}: {e}")
    except sqlite3.InterfaceError as e:
        # SQLite threading error - return None and continue
        return None
    except Exception as e:
        print(f"Error in get_art_path for song {song_id}: {type(e).__name__}: {e}")

    return None


def download_and_cache_album_art(song_id: int, db: Database) -> Optional[Path]:
    song = db.get_song(song_id)
    if not song or not song.artist or not song.album:
        return None

    query = f"{song.artist} {song.album}"
    url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&entity=album&limit=1"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data.get("results"):
                art_url = data["results"][0].get("artworkUrl100")
                if art_url:
                    art_url = art_url.replace("100x100bb.jpg", "600x600bb.jpg")
                    img_data = requests.get(art_url, timeout=10).content
                    if _validate_image_data(img_data):
                        CACHE_DIR.mkdir(parents=True, exist_ok=True)
                        out_path = CACHE_DIR / f"{song_id}.jpg"
                        out_path.write_bytes(img_data)
                        return out_path
    except Exception as e:
        print(f"Error descargando carátula para canción {song_id}: {e}")
    return None


def clear_cache():
    if CACHE_DIR.exists():
        for f in CACHE_DIR.iterdir():
            if f.is_file():
                f.unlink()
