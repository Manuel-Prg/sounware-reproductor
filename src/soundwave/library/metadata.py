import os
import re
import mimetypes
from pathlib import Path
from typing import Optional

import mutagen
from mutagen import File as MutagenFile
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus
from mutagen.id3 import ID3, APIC

from soundwave.library.database import Song

MUSIC_EXTENSIONS = {
    ".mp3", ".flac", ".ogg", ".opus", ".m4a", ".mp4",
    ".wav", ".wma", ".aac", ".aiff", ".ape", ".dsf",
}

COVER_FILENAMES = {"cover.jpg", "cover.png", "front.jpg", "front.png",
                    "folder.jpg", "folder.png", "album.jpg", "album.png",
                    "cover.jpeg", "front.jpeg", "folder.jpeg"}


def is_music_file(path: Path) -> bool:
    return path.suffix.lower() in MUSIC_EXTENSIONS


def _detect_embedded_art(mfile, tags: dict) -> tuple[bool, str]:
    if isinstance(mfile, MP3):
        if _has_mp3_art(tags):
            return True, _get_mp3_art_mime(tags)
    elif isinstance(mfile, FLAC):
        if mfile.pictures:
            return True, mfile.pictures[0].mime
    elif isinstance(mfile, MP4):
        covr = tags.get("covr", [])
        if covr:
            mime_type = _mp4_covr_mime(covr[0])
            return True, mime_type
    elif isinstance(mfile, (OggVorbis, OggOpus)):
        pics = mfile.pictures if hasattr(mfile, "pictures") else []
        if not pics and hasattr(mfile, "get"):
            metadata_picture = mfile.get("metadata_block_picture")
            if metadata_picture:
                pics = [mutagen.flac.Picture(metadata_picture[0])]
        if pics:
            return True, pics[0].mime
    return False, ""


def read_metadata(filepath: str) -> Optional[Song]:
    path = Path(filepath)
    if not path.exists():
        return None

    try:
        mfile = MutagenFile(filepath)
        if mfile is None:
            return None
    except Exception:
        return None

    song = Song()
    song.filepath = str(path.resolve())
    song.file_size = path.stat().st_size
    song.modified_at = path.stat().st_mtime
    song.added_at = song.modified_at

    song.duration = int(getattr(mfile.info, "length", 0))

    tags = mfile.tags or {}

    song.has_embedded_art, song.art_mime = _detect_embedded_art(mfile, tags)

    title = _get_tag(mfile, "title")
    if title:
        song.title = title
    artist = _get_tag(mfile, "artist")
    if artist:
        song.artist = artist
    album = _get_tag(mfile, "album")
    if album:
        song.album = album
    album_artist = _get_tag(mfile, "albumartist", "album_artist")
    if album_artist:
        song.album_artist = album_artist

    track_str = _get_tag(mfile, "tracknumber", "track")
    song.track_number = _parse_track_number(track_str)

    disc_str = _get_tag(mfile, "discnumber", "disc")
    song.disc_number = _parse_int(disc_str, 1)

    genre = _get_tag(mfile, "genre")
    if genre:
        song.genre = genre

    year_str = _get_tag(mfile, "date", "year", "originaldate", "originalyear")
    song.year = _parse_int(year_str, 0)

    composer = _get_tag(mfile, "composer")
    if composer:
        song.composer = composer

    # Extraer etiquetas de ReplayGain
    track_gain_str = _get_tag(mfile, "replaygain_track_gain", "REPLAYGAIN_TRACK_GAIN")
    album_gain_str = _get_tag(mfile, "replaygain_album_gain", "REPLAYGAIN_ALBUM_GAIN")
    song.replaygain_track_gain = _parse_gain(track_gain_str)
    song.replaygain_album_gain = _parse_gain(album_gain_str)

    # Adivinar metadatos a partir del nombre del archivo y la jerarquía de carpetas
    if not song.title or not song.artist:
        stem = path.stem
        guessed_artist = ""
        guessed_title = ""
        if " - " in stem:
            parts = stem.split(" - ", 1)
            guessed_artist = parts[0].strip()
            guessed_title = parts[1].strip()
        elif "-" in stem:
            parts = stem.split("-", 1)
            guessed_artist = parts[0].strip()
            guessed_title = parts[1].strip()
        else:
            guessed_title = stem.strip()

        # Limpiar prefijo de número de pista si está en el título (ej: "01 Song Title" -> "Song Title")
        if guessed_title:
            guessed_title = re.sub(r"^\d+[\s._-]+", "", guessed_title).strip()

        if not song.title and guessed_title:
            song.title = guessed_title
        if not song.artist and guessed_artist:
            song.artist = guessed_artist

    if not song.artist:
        parent = path.parent
        grandparent = parent.parent if parent else None
        ignore_dirs = {"music", "musica", "downloads", "descargas", "documents", "documentos", "desktop", "escritorio", "temp", "tmp", "user", "home", "media", "mnt", "run"}
        
        parent_name = parent.name.strip() if parent else ""
        gparent_name = grandparent.name.strip() if grandparent else ""
        
        # Estructura: .../Artista/Álbum/Canción.mp3
        if gparent_name and gparent_name.lower() not in ignore_dirs and len(gparent_name) > 1:
            song.artist = gparent_name
            if not song.album and parent_name and parent_name.lower() not in ignore_dirs:
                song.album = parent_name
        # Estructura: .../Artista/Canción.mp3 o .../Artista - Álbum/Canción.mp3
        elif parent_name and parent_name.lower() not in ignore_dirs and len(parent_name) > 1:
            if " - " in parent_name:
                parts = parent_name.split(" - ", 1)
                song.artist = parts[0].strip()
                if not song.album:
                    song.album = parts[1].strip()
            else:
                song.artist = parent_name

    return song


def extract_embedded_art(filepath: str) -> Optional[bytes]:
    try:
        mfile = MutagenFile(filepath)
        if mfile is None:
            return None
    except Exception:
        return None

    tags = mfile.tags or {}

    if isinstance(mfile, MP3):
        if "APIC:" in tags:
            return tags["APIC:"].data
        for key in tags:
            if isinstance(tags[key], APIC):
                return tags[key].data

    elif isinstance(mfile, FLAC):
        pics = mfile.pictures
        if pics:
            return pics[0].data

    elif isinstance(mfile, MP4):
        covr = tags.get("covr", [])
        if covr:
            return bytes(covr[0])

    elif isinstance(mfile, (OggVorbis, OggOpus)):
        pics = mfile.pictures if hasattr(mfile, "pictures") else []
        if pics:
            return pics[0].data
        metadata_picture = mfile.get("metadata_block_picture")
        if metadata_picture:
            pic = mutagen.flac.Picture(metadata_picture[0])
            return pic.data

    return None


def find_external_cover(dirpath: Path) -> Optional[Path]:
    if not dirpath.exists() or not dirpath.is_dir():
        return None
    for fname in COVER_FILENAMES:
        candidate = dirpath / fname
        if candidate.exists():
            return candidate
    try:
        for f in dirpath.iterdir():
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                lower = f.stem.lower()
                if "cover" in lower or "front" in lower or "folder" in lower or "album" in lower:
                    return f
    except Exception:
        pass
    return None


def get_art_mime_type(filepath: Path) -> str:
    mime, _ = mimetypes.guess_type(str(filepath))
    return mime or "image/jpeg"


def _has_mp3_art(tags) -> bool:
    if isinstance(tags, ID3):
        for key in tags:
            if isinstance(tags[key], APIC):
                return True
    return "APIC:" in tags


def _get_mp3_art_mime(tags) -> str:
    if "APIC:" in tags:
        return tags["APIC:"].mime
    if isinstance(tags, ID3):
        for key in tags:
            if isinstance(tags[key], APIC):
                return tags[key].mime
    return "image/jpeg"


def _mp4_covr_mime(covr_data) -> str:
    if isinstance(covr_data, bytes) and len(covr_data) > 0:
        if covr_data[0] == 0x89:
            return "image/png"
    return "image/jpeg"


def _get_tag(mfile, *names):
    tags = mfile.tags or {}
    
    # MP3 (ID3 tags)
    if isinstance(mfile, MP3):
        # Map logical names to ID3 frame IDs
        id3_map = {
            "title": ["TIT2"],
            "artist": ["TPE1"],
            "album": ["TALB"],
            "albumartist": ["TPE2"],
            "album_artist": ["TPE2"],
            "tracknumber": ["TRCK"],
            "track": ["TRCK"],
            "discnumber": ["TPOS"],
            "disc": ["TPOS"],
            "genre": ["TCON"],
            "date": ["TDRC", "TYER"],
            "year": ["TDRC", "TYER"],
            "originaldate": ["TDOR"],
            "originalyear": ["TDOR"],
            "composer": ["TCOM"]
        }
        for name in names:
            frames = id3_map.get(name, [])
            for frame in frames:
                if frame in tags:
                    val = tags[frame]
                    if hasattr(val, "text") and val.text:
                        return str(val.text[0]).strip()
                    elif isinstance(val, list) and val:
                        return str(val[0]).strip()
                    elif val:
                        return str(val).strip()
        return ""

    # MP4 / M4A (iTunes tags)
    elif isinstance(mfile, MP4):
        mp4_map = {
            "title": ["\xa9nam"],
            "artist": ["\xa9ART"],
            "album": ["\xa9alb"],
            "albumartist": ["aART"],
            "album_artist": ["aART"],
            "tracknumber": ["trkn"],
            "track": ["trkn"],
            "discnumber": ["disk"],
            "disc": ["disk"],
            "genre": ["\xa9gen", "gnre"],
            "date": ["\xa9day"],
            "year": ["\xa9day"],
            "composer": ["\xa9wrt"]
        }
        for name in names:
            keys = mp4_map.get(name, [])
            for key in keys:
                if key in tags:
                    val = tags[key]
                    if isinstance(val, list) and val:
                        if key in ("trkn", "disk"):
                            val_first = val[0]
                            if isinstance(val_first, (tuple, list)) and val_first:
                                return str(val_first[0]).strip()
                            return str(val_first).strip()
                        return str(val[0]).strip()
                    elif val:
                        return str(val).strip()
        return ""

    # VorbisComments / standard case-insensitive
    # FLAC, OggVorbis, OggOpus, etc.
    for name in names:
        for key in (name, name.upper(), name.lower()):
            if key in tags:
                val = tags[key]
                if isinstance(val, list) and val:
                    return str(val[0]).strip()
                elif val:
                    return str(val).strip()

    # Fallback to direct key matching
    for name in names:
        val = tags.get(name)
        if val is not None:
            if isinstance(val, list) and val:
                return str(val[0]).strip()
            return str(val).strip()

    return ""


def _parse_track_number(raw: str) -> int:
    if not raw:
        return 0
    parts = raw.split("/")[0].strip()
    try:
        return int(parts)
    except ValueError:
        return 0


def _parse_int(raw: str, default: int = 0) -> int:
    if not raw:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _parse_gain(raw: str) -> float:
    if not raw:
        return 0.0
    cleaned = raw.lower().replace("db", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0
