import time
from pathlib import Path
from typing import Optional
from soundwave.library.database.database import Database, Song
from soundwave.library.metadata.metadata import read_metadata

def import_playlist_from_m3u8(db: Database, m3u8_path: Path) -> str:
    """
    Parses an M3U8/M3U file, resolves relative/absolute filepaths,
    scans songs if they are missing from the database, and adds them
    to a new playlist named after the file.
    """
    if not m3u8_path.exists():
        raise FileNotFoundError(f"El archivo {m3u8_path} no existe.")

    # Read lines of the file
    content = m3u8_path.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()

    song_ids = []
    parent_dir = m3u8_path.parent

    # Pre-load configured music directories
    from soundwave.library.config.config import load_settings
    settings = load_settings()
    music_dirs = [Path(d) for d in settings.get("music_directories", []) if Path(d).exists()]

    # Pre-cache all songs by filename for fast fallback matching
    all_songs = db.get_all_songs()
    by_filename = {}
    for s in all_songs:
        fn = Path(s.filepath).name.lower()
        if fn not in by_filename:
            by_filename[fn] = []
        by_filename[fn].append(s)

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        # Replace backslashes for cross-platform compatibility
        line = line.replace('\\', '/')
        p = Path(line)
        
        matched_song = None

        # 1. Try to find the song by exact paths
        paths_to_try = []
        if p.is_absolute():
            paths_to_try.append(p)
            try:
                paths_to_try.append(p.resolve(strict=False))
            except Exception:
                pass
        else:
            # Relative to playlist directory
            paths_to_try.append(parent_dir / p)
            try:
                paths_to_try.append((parent_dir / p).resolve(strict=False))
            except Exception:
                pass
            
            # Relative to each music directory
            for md in music_dirs:
                paths_to_try.append(md / p)
                try:
                    paths_to_try.append((md / p).resolve(strict=False))
                except Exception:
                    pass

        # De-duplicate paths to try while preserving order
        seen_paths = []
        for path in paths_to_try:
            try:
                path_str = str(path.resolve(strict=False))
            except Exception:
                path_str = str(path)
            if path_str not in seen_paths:
                seen_paths.append(path_str)

        # Check in DB first
        for path_str in seen_paths:
            song = db.get_song_by_path(path_str)
            if song:
                matched_song = song
                break

        # 2. If not found in DB by path, check if it exists on disk at any of those paths
        if not matched_song:
            for path_str in seen_paths:
                path_obj = Path(path_str)
                if path_obj.exists() and path_obj.is_file():
                    try:
                        meta_song = read_metadata(path_str)
                        if meta_song:
                            song_id = db.add_song(meta_song)
                            meta_song.id = song_id
                            matched_song = meta_song
                            break
                    except Exception as e:
                        print(f"[M3U8 Import] Error al procesar archivo nuevo {path_str}: {e}")

        # 3. Fallback: match by filename
        if not matched_song:
            filename = p.name.lower()
            if filename in by_filename:
                candidates = by_filename[filename]
                # Try to find the one whose path matches the most suffix parts
                best_match = candidates[0]
                if len(p.parts) > 1:
                    for cand in candidates:
                        cand_parts = Path(cand.filepath).parts
                        # Match last few parts
                        match_len = min(len(p.parts), len(cand_parts))
                        if all(p.parts[-i].lower() == cand_parts[-i].lower() for i in range(1, match_len + 1)):
                            best_match = cand
                            break
                matched_song = best_match

        if matched_song and matched_song.id is not None:
            song_ids.append(matched_song.id)

    # Generate unique name
    base_name = m3u8_path.stem
    name = base_name
    counter = 1
    existing_playlists = {pl.name for pl in db.get_playlists()}
    while name in existing_playlists:
        name = f"{base_name} ({counter})"
        counter += 1

    # Create playlist
    playlist_id = db.create_playlist(name)
    for sid in song_ids:
        db.add_to_playlist(playlist_id, sid)

    return name

def export_playlist_to_m3u8(db: Database, playlist_id: int, target_path: Path, also_export_file_based: bool = False):
    """
    Exports a playlist to M3U8 format. If also_export_file_based is True,
    also exports a .pls file with the same base name.
    """
    # Find the playlist
    playlists = db.get_playlists()
    playlist = next((pl for pl in playlists if pl.id == playlist_id), None)
    if not playlist:
        raise ValueError(f"Playlist ID {playlist_id} no encontrada en la base de datos.")

    # Retrieve all song records
    songs = []
    for sid in playlist.song_ids:
        song = db.get_song(sid)
        if song:
            songs.append(song)

    # 1. Export M3U8
    m3u8_lines = ["#EXTM3U"]
    for song in songs:
        duration = int(song.duration) if song.duration else -1
        artist = song.artist or "Artista Desconocido"
        title = song.title or "Título Desconocido"
        m3u8_lines.append(f"#EXTINF:{duration},{artist} - {title}")
        m3u8_lines.append(song.filepath)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("\n".join(m3u8_lines) + "\n", encoding="utf-8")

    # 2. Export PLS (if also_export_file_based is True)
    if also_export_file_based:
        pls_path = target_path.with_suffix(".pls")
        pls_lines = ["[playlist]"]
        pls_lines.append(f"NumberOfEntries={len(songs)}")
        for idx, song in enumerate(songs, 1):
            duration = int(song.duration) if song.duration else -1
            artist = song.artist or "Artista Desconocido"
            title = song.title or "Título Desconocido"
            pls_lines.append(f"File{idx}={song.filepath}")
            pls_lines.append(f"Title{idx}={artist} - {title}")
            pls_lines.append(f"Length{idx}={duration}")
        pls_lines.append("Version=2")
        
        pls_path.write_text("\n".join(pls_lines) + "\n", encoding="utf-8")
