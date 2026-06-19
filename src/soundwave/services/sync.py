import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import requests

def export_library_to_dict(db) -> dict:
    """
    Exports song metadata (ratings, play counts, last played times) and playlists
    to a portable dictionary representation.
    """
    cursor = db.conn.execute(
        "SELECT filepath, title, artist, album, play_count, rating, last_played FROM songs"
    )
    songs = []
    for row in cursor.fetchall():
        songs.append({
            "filepath": row["filepath"],
            "title": row["title"],
            "artist": row["artist"],
            "album": row["album"],
            "play_count": row["play_count"],
            "rating": row["rating"],
            "last_played": row["last_played"]
        })
    
    playlists = db.get_playlists()
    exported_playlists = []
    for pl in playlists:
        pl_songs = []
        for sid in pl.song_ids:
            s_row = db.conn.execute(
                "SELECT title, artist, album FROM songs WHERE id = ?", (sid,)
            ).fetchone()
            if s_row:
                pl_songs.append({
                    "title": s_row["title"],
                    "artist": s_row["artist"],
                    "album": s_row["album"]
                })
        exported_playlists.append({
            "name": pl.name,
            "songs": pl_songs
        })

    return {
        "version": 1,
        "exported_at": __import__("time").time(),
        "songs": songs,
        "playlists": exported_playlists
    }


def import_library_from_dict(db, data: dict):
    """
    Imports and merges stats/playlists from a dictionary into the local SQLite database.
    """
    if not isinstance(data, dict) or "songs" not in data:
        return

    # Load all current songs into memory for fast O(N) lookup
    local_songs = db.conn.execute(
        "SELECT id, filepath, title, artist, album, play_count, rating, last_played FROM songs"
    ).fetchall()
    
    # Matching indexes
    match_map = {}
    path_map = {}
    for r in local_songs:
        title_clean = (r["title"] or "").lower().strip()
        artist_clean = (r["artist"] or "").lower().strip()
        album_clean = (r["album"] or "").lower().strip()
        
        # Only index by tag if we have at least title/artist
        if title_clean or artist_clean:
            match_map[(title_clean, artist_clean, album_clean)] = r
            
        # File name fallback
        if r["filepath"]:
            filename = Path(r["filepath"]).name.lower()
            path_map[filename] = r

    # Merge song stats
    for s in data.get("songs", []):
        title = s.get("title", "")
        artist = s.get("artist", "")
        album = s.get("album", "")
        rating = s.get("rating", 0)
        play_count = s.get("play_count", 0)
        last_played = s.get("last_played")
        filepath = s.get("filepath", "")

        key = (title.lower().strip(), artist.lower().strip(), album.lower().strip())
        matched_row = None
        
        if title or artist:
            matched_row = match_map.get(key)
        
        if not matched_row and filepath:
            filename = Path(filepath).name.lower()
            matched_row = path_map.get(filename)

        if matched_row:
            local_id = matched_row["id"]
            
            # Merge logic: max rating, max play count, latest last played
            new_rating = max(matched_row["rating"] or 0, rating or 0)
            new_play_count = max(matched_row["play_count"] or 0, play_count or 0)
            
            new_last_played = matched_row["last_played"]
            if last_played is not None:
                if new_last_played is None or last_played > new_last_played:
                    new_last_played = last_played

            db.conn.execute("""
                UPDATE songs
                SET rating = ?, play_count = ?, last_played = ?
                WHERE id = ?
            """, (new_rating, new_play_count, new_last_played, local_id))

    db.conn.commit()

    # Re-cache local songs mapping for playlists
    local_songs = db.conn.execute(
        "SELECT id, filepath, title, artist, album FROM songs"
    ).fetchall()
    match_map = {}
    path_map = {}
    for r in local_songs:
        title_clean = (r["title"] or "").lower().strip()
        artist_clean = (r["artist"] or "").lower().strip()
        album_clean = (r["album"] or "").lower().strip()
        if title_clean or artist_clean:
            match_map[(title_clean, artist_clean, album_clean)] = r
        if r["filepath"]:
            filename = Path(r["filepath"]).name.lower()
            path_map[filename] = r

    # Rebuild and merge playlists
    existing_playlists = {pl.name: pl for pl in db.get_playlists()}

    for pl in data.get("playlists", []):
        name = pl.get("name", "")
        if not name:
            continue
        
        resolved_ids = []
        for s_ref in pl.get("songs", []):
            s_title = s_ref.get("title", "")
            s_artist = s_ref.get("artist", "")
            s_album = s_ref.get("album", "")
            s_key = (s_title.lower().strip(), s_artist.lower().strip(), s_album.lower().strip())
            
            matched = match_map.get(s_key)
            if matched:
                resolved_ids.append(matched["id"])

        if not resolved_ids:
            continue

        if name in existing_playlists:
            pl_id = existing_playlists[name].id
            existing_song_ids = existing_playlists[name].song_ids
            # Merge preserving order
            merged_ids = list(existing_song_ids)
            for sid in resolved_ids:
                if sid not in merged_ids:
                    merged_ids.append(sid)
            db.reorder_playlist(pl_id, merged_ids)
        else:
            pl_id = db.create_playlist(name)
            for sid in resolved_ids:
                db.add_to_playlist(pl_id, sid)


def sync_with_local_folder(db, folder_path: str) -> bool:
    """
    Syncs the library database with a JSON file in a local folder (e.g. Syncthing).
    """
    path = Path(folder_path)
    if not path.exists() or not path.is_dir():
        print(f"[Sync] Carpeta local '{folder_path}' no existe o no es un directorio.", file=sys.stderr)
        return False
    
    sync_file = path / "soundwave_sync.json"
    
    # 1. Import
    if sync_file.exists():
        try:
            data = json.loads(sync_file.read_text(encoding="utf-8"))
            import_library_from_dict(db, data)
            print(f"[Sync] Datos importados exitosamente desde '{sync_file}'.")
        except Exception as e:
            print(f"[Sync] Error al importar desde '{sync_file}': {e}", file=sys.stderr)
            return False
            
    # 2. Export
    try:
        local_data = export_library_to_dict(db)
        sync_file.write_text(json.dumps(local_data, indent=2), encoding="utf-8")
        print(f"[Sync] Datos exportados exitosamente a '{sync_file}'.")
        return True
    except Exception as e:
        print(f"[Sync] Error al exportar a '{sync_file}': {e}", file=sys.stderr)
        return False


def sync_with_webdav(db, webdav_url: str, username: str, password: str, remote_filename: str = "soundwave_sync.json") -> bool:
    """
    Syncs the library database with a JSON file hosted on a WebDAV server.
    """
    url = webdav_url.rstrip("/") + "/" + remote_filename
    
    # 1. Download
    remote_data = None
    try:
        auth = (username, password) if username else None
        response = requests.get(url, auth=auth, timeout=15)
        if response.status_code == 200:
            remote_data = response.json()
            print(f"[Sync] Datos remotos descargados exitosamente desde WebDAV.")
        elif response.status_code == 404:
            print(f"[Sync] Archivo remoto no encontrado en WebDAV. Se creará en el paso de subida.")
        else:
            print(f"[Sync] Fallo en la descarga desde WebDAV con código de estado {response.status_code}.", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[Sync] Excepción al descargar de WebDAV: {e}", file=sys.stderr)
        return False

    # 2. Merge
    if remote_data:
        try:
            import_library_from_dict(db, remote_data)
            print(f"[Sync] Datos de WebDAV combinados con la biblioteca local.")
        except Exception as e:
            print(f"[Sync] Error al combinar datos de WebDAV: {e}", file=sys.stderr)
            return False

    # 3. Export & Upload
    try:
        local_data = export_library_to_dict(db)
        auth = (username, password) if username else None
        upload_response = requests.put(
            url, 
            data=json.dumps(local_data, indent=2).encode('utf-8'),
            headers={"Content-Type": "application/json"},
            auth=auth,
            timeout=15
        )
        if upload_response.status_code in (200, 201, 204):
            print(f"[Sync] Datos combinados subidos con éxito a WebDAV.")
            return True
        else:
            print(f"[Sync] Fallo al subir a WebDAV con código de estado {upload_response.status_code}.", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[Sync] Excepción al subir a WebDAV: {e}", file=sys.stderr)
        return False
