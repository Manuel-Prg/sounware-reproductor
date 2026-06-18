import re
import json
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Optional


LRCLIB_BASE = "https://lrclib.net/api"

# BUG 2 FIX: User-Agent con URL de contacto, requerido por la política de LRCLIB.
# Sin esto devuelve 403 en producción.
_USER_AGENT = "Soundwave/1.0 (https://github.com/Manuel-Prg/soundwave)"

# Regex que acepta 2 O 3 dígitos en la parte de sub-segundos
# BUG 3 FIX: el grupo (\d+) captura cualquier cantidad de dígitos;
# la conversión a ms se hace normalizando a milisegundos con 10**(3-len(cs)).
_LRC_PATTERN = re.compile(r"\[(\d+):(\d+)\.(\d+)\](.*)")


class LyricsLine:
    def __init__(self, timestamp_ms: int, text: str):
        self.timestamp_ms = timestamp_ms
        self.text = text


# --- Parsing ---

def _centiseconds_to_ms(cs_str: str) -> int:
    """
    Convierte la parte fraccionaria de un timestamp LRC a milisegundos.
    LRC puede tener 2 dígitos (centisegundos) o 3 dígitos (milisegundos).
    BUG 3 FIX: antes era siempre int(cs) * 10, lo que daba valores 10x
    demasiado grandes para archivos con 3 dígitos (ej: .345 → 3450ms en vez de 345ms).
    """
    digits = len(cs_str)
    value = int(cs_str)
    if digits == 2:
        return value * 10       # centisegundos → ms
    elif digits == 3:
        return value            # ya son milisegundos
    else:
        # más de 3 dígitos: truncar a ms
        return int(cs_str[:3])


def _parse_lrc_text(text: str) -> Optional[list[LyricsLine]]:
    """Parsea texto en formato LRC (sincronizado o no)."""
    lines = []
    for line in text.splitlines():
        m = _LRC_PATTERN.match(line)
        if m:
            minutes, seconds, cs_str, lyric = m.groups()
            total_ms = (
                int(minutes) * 60_000
                + int(seconds) * 1_000
                + _centiseconds_to_ms(cs_str)
            )
            lyric = lyric.strip()
            if lyric:
                lines.append(LyricsLine(total_ms, lyric))

    if lines:
        return sorted(lines, key=lambda x: x.timestamp_ms)

    # BUG 4 FIX: si no hay timestamps, dividir en líneas individuales
    # en vez de devolver todo el bloque como un solo LyricsLine.
    # Antes: return [LyricsLine(0, text.strip())]
    # Ahora: una LyricsLine por línea no vacía, todas en timestamp 0.
    unsynced = []
    for line in text.splitlines():
        stripped = line.strip()
        # saltar líneas que parezcan tags LRC de metadatos: [ar:...], [ti:...], etc.
        if stripped and not re.match(r"\[\w+:", stripped):
            unsynced.append(LyricsLine(0, stripped))
    return unsynced if unsynced else None


def parse_lrc(filepath: Path) -> Optional[list[LyricsLine]]:
    if not filepath.exists():
        return None
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
        return _parse_lrc_text(text)
    except Exception:
        return None


def search_lrc_file(song_path: Path) -> Optional[list[LyricsLine]]:
    """Busca archivo .lrc junto al audio."""
    lrc_path = song_path.with_suffix(".lrc")
    if lrc_path.exists():
        return parse_lrc(lrc_path)
    parent = song_path.parent
    stem = song_path.stem
    for f in parent.iterdir():
        if f.suffix.lower() == ".lrc" and stem.lower() in f.stem.lower():
            return parse_lrc(f)
    return None


# --- LRCLIB ---

def _clean_query_field(value: str, fallback_filename: Optional[str] = None) -> str:
    """
    BUG 1 FIX: limpia valores de metadata antes de enviarlos a LRCLIB.
    - Elimina "Artista desconocido" / "Álbum desconocido" (placeholders internos)
    - Reemplaza guiones bajos por espacios (filenames usados como título)
    - Elimina extensiones si el título viene del nombre de archivo
    """
    PLACEHOLDERS = {
        "artista desconocido", "álbum desconocido", "unknown artist",
        "unknown album", "unknown", "",
    }
    if value.lower().strip() in PLACEHOLDERS:
        if fallback_filename:
            # usar el nombre de archivo limpiado como fallback
            return Path(fallback_filename).stem.replace("_", " ").replace("-", " ").strip()
        return ""
    return value.replace("_", " ").strip()


def search_lrclib(
    artist: str,
    title: str,
    album: str = "",
    duration: int = 0,
    song_path: Optional[Path] = None,
) -> Optional[list[LyricsLine]]:
    filename = str(song_path) if song_path else None

    # BUG 1 FIX: limpiar antes de construir la query
    clean_artist = _clean_query_field(artist)
    clean_title  = _clean_query_field(title, filename)
    clean_album  = _clean_query_field(album)

    if not clean_title:
        return None

    params: dict = {"track_name": clean_title}
    if clean_artist:
        params["artist_name"] = clean_artist
    if clean_album:
        params["album_name"] = clean_album
    if duration and duration > 0:
        params["duration"] = str(duration)

    url = f"{LRCLIB_BASE}/get?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})

    try:
        resp = urllib.request.urlopen(req, timeout=8)
        data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # No encontrado — intentar sin álbum ni duración
            return _search_lrclib_fallback(clean_artist, clean_title)
        return None
    except Exception:
        return None

    if not data or not isinstance(data, dict):
        return None

    # Preferir syncedLyrics; si no hay, usar plainLyrics
    raw = data.get("syncedLyrics") or data.get("plainLyrics")
    if not raw:
        return None
    return _parse_lrc_text(raw)


def _search_lrclib_fallback(artist: str, title: str) -> Optional[list[LyricsLine]]:
    """
    Segunda búsqueda sin álbum ni duración, más tolerante.
    Útil cuando los metadatos del archivo tienen duración incorrecta
    o el nombre del álbum no coincide exactamente con LRCLIB.
    """
    if not title:
        return None
    params: dict = {"track_name": title}
    if artist:
        params["artist_name"] = artist

    url = f"{LRCLIB_BASE}/get?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        resp = urllib.request.urlopen(req, timeout=8)
        data = json.loads(resp.read().decode())
        raw = data.get("syncedLyrics") or data.get("plainLyrics")
        return _parse_lrc_text(raw) if raw else None
    except Exception:
        return None


# --- Punto de entrada público ---

def get_lyrics(
    artist: str,
    title: str,
    album: str,
    duration: int,
    song_path: Optional[Path] = None,
) -> Optional[list[LyricsLine]]:
    """
    Orden de búsqueda:
    1. Archivo .lrc junto al audio (sin red, instantáneo)
    2. LRCLIB con metadatos completos
    3. LRCLIB sin álbum/duración (fallback tolerante)
    """
    # 1. Archivo local
    if song_path:
        result = search_lrc_file(song_path)
        if result:
            return result

    # 2 y 3. LRCLIB (el fallback ya está dentro de search_lrclib)
    try:
        return search_lrclib(artist, title, album, duration, song_path)
    except Exception:
        return None