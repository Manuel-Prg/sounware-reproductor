import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from soundwave.library.config.config import load_settings, save_setting


class SyncPage(Adw.PreferencesPage):
    def __init__(self, parent_window, settings_dialog):
        super().__init__()
        self.parent_window = parent_window
        self.settings_dialog = settings_dialog

        self.set_title("Sincronización")
        self.set_icon_name("changes-prevent-symbolic")

        sync_group = Adw.PreferencesGroup()
        sync_group.set_title("Sincronización de Biblioteca")
        sync_group.set_description("Sincroniza tus valoraciones, reproducciones y listas de reproducción")
        self.add(sync_group)

        sync_mode_row = Adw.ComboRow()
        sync_mode_row.set_title("Modo de Sincronización")
        sync_mode_row.set_subtitle("Elige cómo sincronizar tus metadatos")
        sync_mode_model = Gtk.StringList.new(["Desactivado", "Carpeta Local (ej. Syncthing)", "Servidor WebDAV"])
        sync_mode_row.set_model(sync_mode_model)
        sync_group.add(sync_mode_row)

        # Local sync path row
        self.local_path_row = Adw.EntryRow()
        self.local_path_row.set_title("Ruta de la carpeta local")
        sync_group.add(self.local_path_row)

        # WebDAV rows
        self.webdav_url_row = Adw.EntryRow()
        self.webdav_url_row.set_title("URL del Servidor WebDAV")
        sync_group.add(self.webdav_url_row)

        self.webdav_user_row = Adw.EntryRow()
        self.webdav_user_row.set_title("Usuario WebDAV")
        sync_group.add(self.webdav_user_row)

        self.webdav_pass_row = Adw.PasswordEntryRow()
        self.webdav_pass_row.set_title("Contraseña WebDAV")
        sync_group.add(self.webdav_pass_row)

        # Trigger sync button row
        self.trigger_row = Adw.ActionRow()
        self.trigger_row.set_title("Ejecutar sincronización")
        self.sync_now_btn = Gtk.Button(label="Sincronizar ahora")
        self.sync_now_btn.set_valign(Gtk.Align.CENTER)
        self.sync_now_btn.set_css_classes(["suggested-action"])
        self.sync_now_btn.connect("clicked", self._on_sync_now_clicked)
        self.trigger_row.add_suffix(self.sync_now_btn)
        sync_group.add(self.trigger_row)

        # Load saved settings
        settings = load_settings()

        current_mode = settings.get("sync_mode", "none")
        if current_mode == "none":
            sync_mode_row.set_selected(0)
        elif current_mode == "local":
            sync_mode_row.set_selected(1)
        elif current_mode == "webdav":
            sync_mode_row.set_selected(2)

        self.local_path_row.set_text(settings.get("sync_local_path", ""))
        self.webdav_url_row.set_text(settings.get("sync_webdav_url", ""))
        self.webdav_user_row.set_text(settings.get("sync_webdav_user", ""))
        self.webdav_pass_row.set_text(settings.get("sync_webdav_password", ""))

        def update_visibility():
            mode = sync_mode_row.get_selected()
            self.local_path_row.set_visible(mode == 1)
            self.webdav_url_row.set_visible(mode == 2)
            self.webdav_user_row.set_visible(mode == 2)
            self.webdav_pass_row.set_visible(mode == 2)
            self.trigger_row.set_sensitive(mode > 0)

        update_visibility()

        def on_sync_mode_changed(row, pspec):
            selected = row.get_selected()
            if selected == 1:
                save_setting("sync_mode", "local")
            elif selected == 2:
                save_setting("sync_mode", "webdav")
            else:
                save_setting("sync_mode", "none")
            update_visibility()

        sync_mode_row.connect("notify::selected", on_sync_mode_changed)

        def on_local_path_changed(row, pspec):
            save_setting("sync_local_path", row.get_text().strip())
        self.local_path_row.connect("notify::text", on_local_path_changed)

        def on_webdav_url_changed(row, pspec):
            save_setting("sync_webdav_url", row.get_text().strip())
        self.webdav_url_row.connect("notify::text", on_webdav_url_changed)

        def on_webdav_user_changed(row, pspec):
            save_setting("sync_webdav_user", row.get_text().strip())
        self.webdav_user_row.connect("notify::text", on_webdav_user_changed)

        def on_webdav_pass_changed(row, pspec):
            save_setting("sync_webdav_password", row.get_text().strip())
        self.webdav_pass_row.connect("notify::text", on_webdav_pass_changed)

    def _on_sync_now_clicked(self, btn):
        settings = load_settings()
        mode = settings.get("sync_mode", "none")
        if mode == "none":
            return

        self.sync_now_btn.set_sensitive(False)
        self.trigger_row.set_title("Sincronizando...")

        def run_sync():
            success = False
            try:
                from soundwave.services.sync import sync_with_local_folder, sync_with_webdav
                if mode == "local":
                    local_path = settings.get("sync_local_path", "")
                    if local_path:
                        success = sync_with_local_folder(self.parent_window.db, local_path)
                elif mode == "webdav":
                    url = settings.get("sync_webdav_url", "")
                    user = settings.get("sync_webdav_user", "")
                    passwd = settings.get("sync_webdav_password", "")
                    if url:
                        success = sync_with_webdav(self.parent_window.db, url, user, passwd)
            except Exception as e:
                print(f"[Sync UI] Error ejecutando sincronización de fondo: {e}")

            GLib.idle_add(self._on_sync_complete, success)

        import threading
        threading.Thread(target=run_sync, daemon=True).start()

    def _on_sync_complete(self, success: bool):
        self.sync_now_btn.set_sensitive(True)
        self.trigger_row.set_title("Ejecutar sincronización")
        if success:
            self.settings_dialog._show_error("Sincronización completada con éxito.")
        else:
            self.settings_dialog._show_error("Error al sincronizar la biblioteca.")
