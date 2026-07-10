import os
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from soundwave.library.database.database import Database, Song
from soundwave.library.metadata.metadata import is_music_file, read_metadata


ProgressCallback = Callable[[int, int, str], None]


class MusicScanner:
    def __init__(self, db: Database):
        self.db = db
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def scan_directories(self, directories: list[Path],
                         progress_cb: Optional[ProgressCallback] = None,
                         max_workers: int = 4) -> tuple[int, int]:
        self._cancelled = False
        all_files: list[Path] = []
        for directory in directories:
            if directory.exists():
                all_files.extend(self._walk_directory(directory))
            else:
                print(f"[Scanner] La carpeta no existe: {directory}")

        music_files = [f for f in all_files if is_music_file(f)]
        total = len(music_files)
        added = 0
        skipped = 0

        if total == 0:
            if progress_cb:
                progress_cb(0, 0, "No se encontraron archivos de música")
            return added, skipped

        if progress_cb:
            progress_cb(0, total, f"Escaneando {total} archivos...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            fut_to_path = {
                executor.submit(self._process_file, f): f
                for f in music_files
            }
            done_count = 0
            for future in as_completed(fut_to_path):
                if self._cancelled:
                    executor.shutdown(wait=False)
                    return added, skipped
                done_count += 1
                try:
                    result = future.result(timeout=120)
                except Exception as e:
                    print(f"[Scanner] Error procesando archivo: {e}")
                    result = "skipped"
                if isinstance(result, tuple) and result[0] == "added":
                    added += 1
                elif result == "added":
                    added += 1
                elif result == "skipped":
                    skipped += 1
                if progress_cb:
                    path = fut_to_path[future]
                    progress_cb(done_count, total, f"Procesando: {path.name}")

        if progress_cb:
            progress_cb(total, total, f"Completado: {added} añadidas, {skipped} omitidas")

        return added, skipped

    def scan_single_file(self, filepath: Path) -> Optional[Song]:
        if not is_music_file(filepath):
            return None
        song = read_metadata(str(filepath))
        if song is None:
            return None
        song_id = self.db.add_song(song)
        song.id = song_id
        try:
            from soundwave.library.metadata.album_art import get_art_path
            get_art_path(song_id, self.db)
        except Exception as e:
            print(f"Error pre-cacheando carátula para archivo único: {e}")
            
        # Waveform will be dynamically calculated when the song is played to prevent GUI lags
        return song

    def remove_missing_files(self) -> int:
        removed = 0
        for song in self.db.get_all_songs():
            if not Path(song.filepath).exists():
                self.db.remove_song(song.id)
                removed += 1
        return removed

    def _walk_directory(self, directory: Path, visited: Optional[set[Path]] = None) -> list[Path]:
        files = []
        if visited is None:
            visited = set()
        try:
            real = directory.resolve(strict=False)
            if real in visited:
                return files
            visited.add(real)
        except (OSError, RuntimeError):
            return files

        try:
            for entry in os.scandir(str(directory)):
                if self._cancelled:
                    break
                try:
                    if entry.is_file(follow_symlinks=False):
                        files.append(Path(entry.path))
                    elif entry.is_dir(follow_symlinks=False) and not entry.name.startswith("."):
                        files.extend(self._walk_directory(Path(entry.path), visited))
                except PermissionError:
                    continue
                except OSError:
                    continue
        except PermissionError:
            pass
        return files

    def _process_file(self, filepath: Path) -> str | tuple[str, int]:
        try:
            song = read_metadata(str(filepath))
            if song is None:
                return "skipped"
            song_id = self.db.add_song(song)
            try:
                from soundwave.library.metadata.album_art import get_art_path
                get_art_path(song_id, self.db)
            except Exception as e:
                print(f"Error pre-cacheando carátula en lote: {e}")
            
            # Return song_id for deferred waveform processing
            return ("added", song_id)
        except Exception:
            return "skipped"


