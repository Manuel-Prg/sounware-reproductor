import os
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from soundwave.library.database import Database, Song
from soundwave.library.metadata import is_music_file, read_metadata


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

        music_files = [f for f in all_files if is_music_file(f)]
        total = len(music_files)
        added = 0
        skipped = 0

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
                result = future.result()
                if result == "added":
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
        existing = self.db.get_song_by_path(str(filepath.resolve()))
        if existing:
            stat = filepath.stat()
            if stat.st_mtime <= existing.modified_at:
                return existing
        song = read_metadata(str(filepath))
        if song is None:
            return None
        song.id = self.db.add_song(song)
        return song

    def remove_missing_files(self) -> int:
        removed = 0
        for song in self.db.get_all_songs():
            if not Path(song.filepath).exists():
                self.db.remove_song(song.id)
                removed += 1
        return removed

    def _walk_directory(self, directory: Path) -> list[Path]:
        files = []
        try:
            for entry in os.scandir(str(directory)):
                if self._cancelled:
                    break
                try:
                    if entry.is_file():
                        files.append(Path(entry.path))
                    elif entry.is_dir() and not entry.name.startswith("."):
                        files.extend(self._walk_directory(Path(entry.path)))
                except PermissionError:
                    continue
                except OSError:
                    continue
        except PermissionError:
            pass
        return files

    def _process_file(self, filepath: Path) -> str:
        try:
            existing = self.db.get_song_by_path(str(filepath.resolve()))
            if existing:
                stat = filepath.stat()
                if stat.st_mtime <= existing.modified_at:
                    return "skipped"
            song = read_metadata(str(filepath))
            if song is None:
                return "skipped"
            self.db.add_song(song)
            return "added"
        except Exception:
            return "skipped"
