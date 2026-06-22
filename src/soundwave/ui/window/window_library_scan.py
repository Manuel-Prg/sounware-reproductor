"""Escaneo de biblioteca y arrastrar y soltar."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio, Gdk

from pathlib import Path


class WindowLibraryScanMixin:
    def _setup_drag_drop(self):
        drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop_target.connect("accept", self._on_drag_accept)
        drop_target.connect("drop", self._on_drag_drop)
        self.add_controller(drop_target)

    def _on_drag_accept(self, drop_target, drop):
        return True

    def _on_drag_drop(self, drop_target, value, x, y):
        file = value
        if not file:
            return False
        path = file.get_path()
        if not path:
            return False
        from pathlib import Path
        p = Path(path)
        if p.is_dir():
            self._start_scan(p)
        elif p.suffix.lower() in (".mp3", ".flac", ".ogg", ".m4a", ".wav", ".wma", ".opus"):
            self._start_scan(p.parent)
        return True

    def _check_library(self):
        stats = self.db.get_stats()
        if stats["total_songs"] == 0:
            self._show_welcome_dialog()
        else:
            self._refresh_library()

    def _show_welcome_dialog(self):
        dialog = Adw.AlertDialog(
            heading="¡Bienvenido a Soundwave!",
            body="Tu biblioteca está vacía. ¿Quieres escanear tu carpeta de música?",
        )
        dialog.add_response("cancel", "Ahora no")
        dialog.add_response("scan", "Escanear música")
        dialog.set_response_appearance("scan", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("scan")
        dialog.connect("response", self._on_welcome_response)
        dialog.present(self)

    def _on_welcome_response(self, dialog, response):
        if response == "scan":
            self._show_scan_dialog()

    def _show_scan_dialog(self):
        dialog = Adw.AlertDialog(
            heading="Seleccionar carpeta",
            body="Elige la carpeta donde tienes tu música.",
        )
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("browse", "Seleccionar carpeta")
        dialog.set_response_appearance("browse", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self._on_scan_response)
        dialog.present(self)

    def _on_scan_response(self, dialog, response):
        if response == "browse":
            self._open_folder_picker()

    def _open_folder_picker(self):
        if hasattr(Gtk, "FileDialog"):
            dialog = Gtk.FileDialog.new()
            dialog.set_title("Seleccionar carpeta de música")

            def on_folder_selected(dialog, result, *args):
                try:
                    file = dialog.select_folder_finish(result)
                    if file:
                        self._start_scan(Path(file.get_path()))
                except GLib.Error as e:
                    print("Selección de carpeta cancelada o fallida:", e)

            dialog.select_folder(self, None, on_folder_selected)
        else:
            dialog = Gtk.FileChooserNative.new(
                title="Seleccionar carpeta de música",
                parent=self,
                action=Gtk.FileChooserAction.SELECT_FOLDER,
                accept_label="Seleccionar",
                cancel_label="Cancelar"
            )
            self._file_chooser = dialog

            def on_response(dialog, response_id):
                if response_id == Gtk.ResponseType.ACCEPT:
                    file = dialog.get_file()
                    if file:
                        self._start_scan(Path(file.get_path()))
                self._file_chooser = None

            dialog.connect("response", on_response)
            dialog.show()

    def _start_scan(self, directory: Path):
        from soundwave.library.config.config import load_settings, save_setting
        settings = load_settings()
        dirs = settings.get("music_directories", [])
        try:
            dir_str = str(directory.resolve(strict=False))
        except Exception:
            dir_str = str(directory)
        if dir_str not in dirs:
            dirs.append(dir_str)
            save_setting("music_directories", dirs)

        self._scan_dialog = Adw.AlertDialog(
            heading="Escaneando...",
            body="Buscando archivos de música...",
        )
        self._scan_dialog.add_response("cancel", "Cancelar")
        self._scan_dialog.connect("response", lambda d, r: self.scanner.cancel())
        self._scan_dialog.present(self)

        def scan_task():
            try:
                added, skipped = self.scanner.scan_directories(
                    [directory],
                    progress_cb=lambda done, total, msg: GLib.idle_add(
                        lambda d=done, t=total, m=msg: self._update_scan_progress(d, t, m)
                    )
                )
                GLib.idle_add(lambda: self._on_scan_complete(added, skipped))
            except Exception as e:
                print(f"[Scan] Error: {e}")
                GLib.idle_add(lambda: self._on_scan_error(str(e)))

        import threading
        thread = threading.Thread(target=scan_task, daemon=True)
        thread.start()

    def _update_scan_progress(self, done: int, total: int, msg: str):
        if done < total and self._scan_dialog:
            try:
                self._scan_dialog.set_body(f"{done}/{total} - {msg}")
            except Exception:
                pass
        return False

    def _on_scan_complete(self, added: int, skipped: int):
        if self._scan_dialog:
            try:
                self._scan_dialog.close()
                self._scan_dialog = None
            except Exception:
                pass
        toast = Adw.Toast.new(f"Escaneo completo: {added} canciones añadidas")
        toast.set_timeout(3)
        self._refresh_library()
        self._show_stats_notification(added)
        self._start_folder_watcher()

    def _on_scan_error(self, error_msg: str):
        if self._scan_dialog:
            try:
                self._scan_dialog.close()
                self._scan_dialog = None
            except Exception:
                pass
        toast = Adw.Toast.new(f"Error al escanear: {error_msg}")
        toast.set_timeout(5)

    def _show_stats_notification(self, added: int):
        stats = self.db.get_stats()
        msg = f"{stats['total_songs']} canciones, {stats['total_artists']} artistas, {stats['total_albums']} álbumes"
        toast = Adw.Toast.new(msg)
        toast.set_timeout(3)
        self._player_bar.add_toast(toast)

