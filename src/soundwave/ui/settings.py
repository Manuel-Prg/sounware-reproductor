import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from pathlib import Path
from typing import Optional
from soundwave.library.config.config import load_settings, save_setting, apply_theme


class SettingsDialog(Adw.PreferencesWindow):
    def __init__(self, parent_window, lastfm):
        super().__init__(transient_for=parent_window, modal=True)
        self.parent_window = parent_window
        self.lastfm = lastfm
        self._api_key_timeout = None
        self._api_secret_timeout = None

        self.set_title("Ajustes")
        self.set_default_size(480, 540)

        # Page 1: General
        general_page = Adw.PreferencesPage()
        general_page.set_title("General")
        general_page.set_icon_name("preferences-other-symbolic")
        self.add(general_page)

        # Group 1: Appearance
        appearance_group = Adw.PreferencesGroup()
        appearance_group.set_title("Apariencia")
        appearance_group.set_description("Configura cómo se ve el reproductor")
        general_page.add(appearance_group)

        theme_row = Adw.ComboRow()
        theme_row.set_title("Tema")
        theme_row.set_subtitle("Elige la apariencia visual de la aplicación")
        theme_model = Gtk.StringList.new(["Sistema", "Claro", "Oscuro"])
        theme_row.set_model(theme_model)

        style_manager = Adw.StyleManager.get_default()
        current_scheme = style_manager.get_color_scheme()
        if current_scheme in (Adw.ColorScheme.PREFER_LIGHT, Adw.ColorScheme.FORCE_LIGHT):
            theme_row.set_selected(1)
        elif current_scheme in (Adw.ColorScheme.PREFER_DARK, Adw.ColorScheme.FORCE_DARK):
            theme_row.set_selected(2)
        else:
            theme_row.set_selected(0)

        def on_theme_changed(row, pspec):
            selected = row.get_selected()
            if selected == 1:
                apply_theme("light")
                save_setting("theme", "light")
            elif selected == 2:
                apply_theme("dark")
                save_setting("theme", "dark")
            else:
                apply_theme("system")
                save_setting("theme", "system")

        theme_row.connect("notify::selected", on_theme_changed)
        appearance_group.add(theme_row)

        # Accent color selection
        accent_row = Adw.ComboRow()
        accent_row.set_title("Color de acento")
        accent_row.set_subtitle("Elige el color de acentuación de la interfaz")
        
        ACCENT_COLORS = [
            ("Verde (Predeterminado)", "#1DB954"),
            ("Azul", "#3584e4"),
            ("Púrpura", "#9141ac"),
            ("Rojo", "#e01b24"),
            ("Naranja", "#ff7800"),
            ("Teal", "#16a085"),
            ("Rosa", "#e01b84"),
            ("Gris", "#777777")
        ]
        
        accent_names = [name for name, _ in ACCENT_COLORS]
        accent_model = Gtk.StringList.new(accent_names)
        accent_row.set_model(accent_model)
        
        current_settings = load_settings()
        current_accent = current_settings.get("accent_color", "#1DB954")
        selected_idx = 0
        for idx, (_, hex_code) in enumerate(ACCENT_COLORS):
            if hex_code == current_accent:
                selected_idx = idx
                break
        accent_row.set_selected(selected_idx)
        
        def on_accent_changed(row, pspec):
            idx = row.get_selected()
            if 0 <= idx < len(ACCENT_COLORS):
                hex_code = ACCENT_COLORS[idx][1]
                save_setting("accent_color", hex_code)
                if hasattr(self.parent_window, "apply_accent_color"):
                    self.parent_window.apply_accent_color(hex_code)
                    
        accent_row.connect("notify::selected", on_accent_changed)
        appearance_group.add(accent_row)

        # Group 2: Library
        library_group = Adw.PreferencesGroup()
        library_group.set_title("Biblioteca de Música")
        library_group.set_description("Administra tu colección musical")
        general_page.add(library_group)

        scan_row = Adw.ActionRow()
        scan_row.set_title("Añadir / Escanear carpeta")
        scan_row.set_subtitle("Selecciona una carpeta para buscar archivos de audio")
        scan_btn = Gtk.Button(label="Seleccionar...")
        scan_btn.set_valign(Gtk.Align.CENTER)
        scan_btn.connect("clicked", self._on_scan_clicked)
        scan_row.add_suffix(scan_btn)
        library_group.add(scan_row)

        # Album art download toggle
        art_download_row = Adw.SwitchRow()
        art_download_row.set_title("Descargar carátulas faltantes")
        art_download_row.set_subtitle("Busca y descarga en internet las carátulas de álbumes que no las tengan")
        # pyrefly: ignore [unbound-name]
        settings = load_settings()
        art_download_row.set_active(settings.get("download_missing_art", False))

        def on_art_download_toggled(row, pspec):
            save_setting("download_missing_art", row.get_active())

        art_download_row.connect("notify::active", on_art_download_toggled)
        library_group.add(art_download_row)

        # Batch download art now
        self.batch_art_row = Adw.ActionRow()
        self.batch_art_row.set_title("Buscar carátulas ahora")
        self.batch_art_row.set_subtitle("Descarga en segundo plano las carátulas que faltan en la biblioteca")
        self.batch_art_btn = Gtk.Button(label="Buscar")
        self.batch_art_btn.set_valign(Gtk.Align.CENTER)
        self.batch_art_btn.set_css_classes(["suggested-action"])
        self.batch_art_btn.connect("clicked", self._on_batch_art_clicked)
        self.batch_art_row.add_suffix(self.batch_art_btn)
        library_group.add(self.batch_art_row)

        # Group 3: Audio Settings
        audio_group = Adw.PreferencesGroup()
        audio_group.set_title("Audio")
        audio_group.set_description("Configura opciones de reproducción de sonido")
        general_page.add(audio_group)

        replaygain_row = Adw.ComboRow()
        replaygain_row.set_title("ReplayGain")
        replaygain_row.set_subtitle("Normaliza el volumen automáticamente según los metadatos")
        replaygain_model = Gtk.StringList.new(["Desactivado", "Por Pista (Track)", "Por Álbum (Album)"])
        replaygain_row.set_model(replaygain_model)

        # Cargar configuración actual de ReplayGain
        settings = load_settings()
        current_rg = settings.get("replaygain_mode", "track")
        if current_rg == "off":
            replaygain_row.set_selected(0)
        elif current_rg == "track":
            replaygain_row.set_selected(1)
        elif current_rg == "album":
            replaygain_row.set_selected(2)

        def on_replaygain_changed(row, pspec):
            selected = row.get_selected()
            if selected == 0:
                save_setting("replaygain_mode", "off")
            elif selected == 1:
                save_setting("replaygain_mode", "track")
            elif selected == 2:
                save_setting("replaygain_mode", "album")

        replaygain_row.connect("notify::selected", on_replaygain_changed)
        audio_group.add(replaygain_row)

        # Page 2: Connections
        conn_page = Adw.PreferencesPage()
        conn_page.set_title("Conexiones")
        conn_page.set_icon_name("network-wired-symbolic")
        self.add(conn_page)

        # Group 3: Last.fm
        lastfm_group = Adw.PreferencesGroup()
        lastfm_group.set_title("Last.fm")
        lastfm_group.set_description("Registra lo que escuchas automáticamente en Last.fm")
        conn_page.add(lastfm_group)

        self.status_row = Adw.ActionRow()
        self.status_row.set_title("Estado")
        lastfm_group.add(self.status_row)

        # API Configuration (advanced)
        api_key_row = Adw.ActionRow()
        api_key_row.set_title("API Key")
        api_key_row.set_subtitle("Clave de API de Last.fm (obtén una en last.fm/api)")
        self.api_key_entry = Gtk.Entry()
        self.api_key_entry.set_valign(Gtk.Align.CENTER)
        self.api_key_entry.set_text(self.lastfm.api_key or "")
        self.api_key_entry.set_hexpand(True)
        api_key_row.add_suffix(self.api_key_entry)
        lastfm_group.add(api_key_row)

        api_secret_row = Adw.ActionRow()
        api_secret_row.set_title("API Secret")
        api_secret_row.set_subtitle("Secreto de API de Last.fm")
        self.api_secret_entry = Gtk.PasswordEntry()
        self.api_secret_entry.set_valign(Gtk.Align.CENTER)
        self.api_secret_entry.set_text(self.lastfm.api_secret or "")
        self.api_secret_entry.set_hexpand(True)
        api_secret_row.add_suffix(self.api_secret_entry)
        lastfm_group.add(api_secret_row)

        # Save button for API credentials
        save_api_btn_row = Adw.ActionRow()
        save_api_btn = Gtk.Button(label="Guardar credenciales API")
        save_api_btn.set_valign(Gtk.Align.CENTER)
        save_api_btn.set_css_classes(["suggested-action"])
        save_api_btn.connect("clicked", self._on_save_api_credentials)
        save_api_btn_row.add_suffix(save_api_btn)
        lastfm_group.add(save_api_btn_row)

        # OAuth authorization button
        oauth_row = Adw.ActionRow()
        oauth_row.set_title("Autorización")
        oauth_row.set_subtitle("Autoriza Soundwave en Last.fm")
        self.oauth_btn = Gtk.Button(label="Autorizar con Last.fm")
        self.oauth_btn.set_valign(Gtk.Align.CENTER)
        self.oauth_btn.set_css_classes(["suggested-action"])
        self.oauth_btn.connect("clicked", self._on_oauth_start)
        oauth_row.add_suffix(self.oauth_btn)
        lastfm_group.add(oauth_row)

        # Complete authorization button (hidden initially)
        self.complete_oauth_row = Adw.ActionRow()
        self.complete_oauth_row.set_title("Completar autorización")
        self.complete_oauth_row.set_subtitle("Haz clic después de autorizar en el navegador")
        self.complete_oauth_btn = Gtk.Button(label="Completar")
        self.complete_oauth_btn.set_valign(Gtk.Align.CENTER)
        self.complete_oauth_btn.set_css_classes(["suggested-action"])
        self.complete_oauth_btn.connect("clicked", self._on_oauth_complete)
        self.complete_oauth_row.add_suffix(self.complete_oauth_btn)
        self.complete_oauth_row.set_visible(False)
        lastfm_group.add(self.complete_oauth_row)

        # Disconnect button (hidden initially)
        self.disconnect_row = Adw.ActionRow()
        self.disconnect_btn = Gtk.Button(label="Desconectar")
        self.disconnect_btn.set_valign(Gtk.Align.CENTER)
        self.disconnect_btn.set_css_classes(["destructive-action"])
        self.disconnect_btn.connect("clicked", self._on_lastfm_disconnect)
        self.disconnect_row.add_suffix(self.disconnect_btn)
        self.disconnect_row.set_visible(False)
        lastfm_group.add(self.disconnect_row)

        self._oauth_token = None

        self._update_lastfm_ui()

        # Page 3: Sincronización
        sync_page = Adw.PreferencesPage()
        sync_page.set_title("Sincronización")
        sync_page.set_icon_name("changes-prevent-symbolic")
        self.add(sync_page)

        sync_group = Adw.PreferencesGroup()
        sync_group.set_title("Sincronización de Biblioteca")
        sync_group.set_description("Sincroniza tus valoraciones, reproducciones y listas de reproducción")
        sync_page.add(sync_group)

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

    def _update_lastfm_ui(self):
        if self.lastfm.connected:
            self.status_row.set_subtitle(f"Conectado como {self.lastfm.username}")
            self.api_key_entry.set_sensitive(False)
            self.api_secret_entry.set_sensitive(False)
            self.oauth_btn.set_visible(False)
            self.complete_oauth_row.set_visible(False)
            self.disconnect_row.set_visible(True)
        else:
            if not self.lastfm.configured:
                self.status_row.set_subtitle("Configura API Key y Secret primero")
                self.oauth_btn.set_sensitive(False)
            else:
                self.status_row.set_subtitle("Desconectado")
                self.oauth_btn.set_sensitive(True)
            self.api_key_entry.set_sensitive(True)
            self.api_secret_entry.set_sensitive(True)
            self.oauth_btn.set_visible(True)
            self.complete_oauth_row.set_visible(False)
            self.disconnect_row.set_visible(False)

    def _on_api_key_changed(self, entry):
        # Clear existing timeout
        if self._api_key_timeout:
            GLib.source_remove(self._api_key_timeout)

        # Set new timeout to save after 300ms of inactivity
        def save_api_key():
            self.lastfm.api_key = entry.get_text().strip()
            self.lastfm._save_config()
            self._update_lastfm_ui()
            self._api_key_timeout = None
            return False

        self._api_key_timeout = GLib.timeout_add(300, save_api_key)

    def _on_api_secret_changed(self, entry):
        # Clear existing timeout
        if self._api_secret_timeout:
            GLib.source_remove(self._api_secret_timeout)

        # Set new timeout to save after 300ms of inactivity
        def save_api_secret():
            self.lastfm.api_secret = entry.get_text().strip()
            self.lastfm._save_config()
            self._update_lastfm_ui()
            self._api_secret_timeout = None
            return False

        self._api_secret_timeout = GLib.timeout_add(300, save_api_secret)

    def _on_save_api_credentials(self, btn):
        """Manually save API credentials when button is clicked"""
        self.lastfm.api_key = self.api_key_entry.get_text().strip()
        self.lastfm.api_secret = self.api_secret_entry.get_text().strip()
        self.lastfm._save_config()
        self._update_lastfm_ui()
        self._show_error("Credenciales de API guardadas correctamente")

    def _on_oauth_start(self, btn):
        """Start OAuth flow by getting token and opening browser"""
        if not self.lastfm.configured:
            self._show_error("Primero configura la API Key y API Secret de Last.fm.")
            return

        self.oauth_btn.set_sensitive(False)
        self.status_row.set_subtitle("Obteniendo token de autorización...")

        def get_token():
            token = self.lastfm.get_auth_token()
            GLib.idle_add(self._on_token_received, token)

        import threading
        threading.Thread(target=get_token, daemon=True).start()

    def _on_token_received(self, token: Optional[str]):
        if token:
            self._oauth_token = token
            auth_url = f"https://www.last.fm/api/auth/?api_key={self.lastfm.api_key}&token={token}"
            import webbrowser
            webbrowser.open(auth_url)
            self.status_row.set_subtitle("Autoriza en el navegador, luego haz clic en 'Completar'")
            self.oauth_btn.set_visible(False)
            self.complete_oauth_row.set_visible(True)
        else:
            self.oauth_btn.set_sensitive(True)
            self.status_row.set_subtitle("Error al obtener token")
            self._show_error("No se pudo obtener el token de autorización. Verifica tus credenciales de API.")

    def _on_oauth_complete(self, btn):
        """Complete OAuth flow after user authorization"""
        if not self._oauth_token:
            self._show_error("No hay token de autorización. Inicia el proceso de nuevo.")
            return

        self.complete_oauth_btn.set_sensitive(False)
        self.status_row.set_subtitle("Completando autorización...")

        def complete_auth():
            success = self.lastfm.complete_auth(self._oauth_token)
            GLib.idle_add(self._on_oauth_complete_done, success)

        import threading
        threading.Thread(target=complete_auth, daemon=True).start()

    def _on_oauth_complete_done(self, success: bool):
        self.complete_oauth_btn.set_sensitive(True)
        if success:
            self._oauth_token = None
            self._update_lastfm_ui()
            self._show_error("Conectado a Last.fm correctamente")
        else:
            self.status_row.set_subtitle("Error al completar autorización")
            self._show_error("No se pudo completar la autorización. Asegúrate de haber autorizado la aplicación en el navegador.")

    def _on_lastfm_disconnect(self, btn):
        """Disconnect from Last.fm"""
        self.lastfm.disconnect()
        self._update_lastfm_ui()
        self._show_error("Desconectado de Last.fm")

    def _on_scan_clicked(self, btn):
        self.close()
        self.parent_window._open_folder_picker()

    def _show_error(self, message: str):
        toast = Adw.Toast.new(message)
        self.add_toast(toast)

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
            self._show_error("Sincronización completada con éxito.")
        else:
            self._show_error("Error al sincronizar la biblioteca.")

    def _on_batch_art_clicked(self, btn):
        self.batch_art_btn.set_sensitive(False)
        self.batch_art_btn.set_label("Buscando...")
        self.batch_art_row.set_subtitle("Descargando carátulas en segundo plano...")

        # Capture db_path before entering the thread (SQLite connections
        # cannot be shared across threads)
        db_path = self.parent_window.db.db_path

        def run_batch():
            try:
                from soundwave.library.metadata.album_art import get_art_path, download_and_cache_album_art
                from soundwave.library.database.database import Database
                # Open a new, thread-local connection
                thread_db = Database(db_path)
                try:
                    songs = thread_db.get_all_songs()
                    downloaded = 0
                    for song in songs:
                        if song.id is None:
                            continue
                        existing = get_art_path(song.id, thread_db)
                        if existing and existing.exists():
                            continue
                        result = download_and_cache_album_art(song.id, thread_db)
                        if result:
                            downloaded += 1
                finally:
                    thread_db.close()
                GLib.idle_add(self._on_batch_art_complete, downloaded)
            except Exception as e:
                print(f"[Settings] Error en descarga de carátulas: {e}")
                GLib.idle_add(self._on_batch_art_complete, -1)

        import threading
        threading.Thread(target=run_batch, daemon=True).start()

    def _on_batch_art_complete(self, downloaded: int):
        self.batch_art_btn.set_sensitive(True)
        self.batch_art_btn.set_label("Buscar")
        if downloaded == -1:
            self.batch_art_row.set_subtitle("Error al descargar carátulas.")
        elif downloaded == 0:
            self.batch_art_row.set_subtitle("Todas las canciones ya tienen carátula.")
        else:
            self.batch_art_row.set_subtitle(f"¡Descarga completada! {downloaded} carátula(s) nuevas.")
            if hasattr(self.parent_window, "_library_view"):
                GLib.idle_add(self.parent_window._library_view.refresh)
