import os
from pathlib import Path
from gi.repository import Gio, GLib
from typing import Callable

class FolderWatcher:
    def __init__(self, callback: Callable[[Path, str], None]):
        """
        callback recibe (filepath: Path, event: str)
        event puede ser: "created", "modified", "deleted"
        """
        self.callback = callback
        self.monitors = {}  # path -> (monitor, handler_id)

    def start_watching(self, paths: list[Path]):
        self.stop()
        for p in paths:
            self._watch_recursive(Path(p))

    def _watch_recursive(self, path: Path):
        path = path.resolve()
        if not path.exists() or not path.is_dir() or path in self.monitors:
            return

        try:
            gfile = Gio.File.new_for_path(str(path))
            # Crear monitor de directorio
            monitor = gfile.monitor_directory(Gio.FileMonitorFlags.NONE, None)
            handler_id = monitor.connect("changed", self._on_changed, path)
            self.monitors[path] = (monitor, handler_id)
            
            # Recorrer subdirectorios de manera recursiva
            for entry in os.scandir(str(path)):
                if entry.is_dir() and not entry.name.startswith("."):
                    self._watch_recursive(Path(entry.path))
        except Exception as e:
            print(f"Error al vigilar directorio {path}: {e}")

    def _on_changed(self, monitor, file, other_file, event_type, parent_path):
        filepath = Path(file.get_path()) if file else None
        if not filepath:
            return

        # Si se crea una nueva carpeta, vigilarla recursivamente
        if event_type == Gio.FileMonitorEvent.CREATED:
            if filepath.is_dir():
                # Esperar un instante para que el SO asiente la carpeta y registrarla
                GLib.idle_add(lambda: self._watch_recursive(filepath))
            else:
                self.callback(filepath, "created")

        elif event_type == Gio.FileMonitorEvent.DELETED:
            if filepath in self.monitors:
                # Limpiar el monitor del subdirectorio borrado
                mon, hid = self.monitors.pop(filepath)
                try:
                    mon.disconnect(hid)
                    mon.cancel()
                except Exception:
                    pass
            else:
                self.callback(filepath, "deleted")

        elif event_type in (Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.CHANGED):
            if not filepath.is_dir():
                self.callback(filepath, "modified")

    def stop(self):
        for path, (monitor, handler_id) in list(self.monitors.items()):
            try:
                monitor.disconnect(handler_id)
                monitor.cancel()
            except Exception:
                pass
        self.monitors.clear()
