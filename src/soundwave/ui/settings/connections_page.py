import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from typing import Optional


class ConnectionsPage(Adw.PreferencesPage):
    def __init__(self, parent_window, settings_dialog, lastfm):
        super().__init__()
        self.parent_window = parent_window
        self.settings_dialog = settings_dialog
        self.lastfm = lastfm
        
        self._api_key_timeout = None
        self._api_secret_timeout = None
        self._oauth_token = None

        self.set_title("Conexiones")
        self.set_icon_name("network-wired-symbolic")

        # Group 3: Last.fm
        lastfm_group = Adw.PreferencesGroup()
        lastfm_group.set_title("Last.fm")
        lastfm_group.set_description("Registra lo que escuchas automáticamente en Last.fm")
        self.add(lastfm_group)

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

        # User statistics section (hidden initially)
        self.stats_group = Adw.PreferencesGroup()
        self.stats_group.set_title("Estadísticas de Last.fm")
        self.stats_group.set_description("Tu actividad en Last.fm")
        self.stats_group.set_visible(False)
        self.add(self.stats_group)

        # Play count
        self.play_count_row = Adw.ActionRow()
        self.play_count_row.set_title("Reproducciones totales")
        self.play_count_row.set_subtitle("Cargando...")
        self.stats_group.add(self.play_count_row)

        # Refresh stats button
        refresh_stats_row = Adw.ActionRow()
        refresh_stats_row.set_title("Actualizar estadísticas")
        refresh_stats_btn = Gtk.Button(label="Actualizar")
        refresh_stats_btn.set_valign(Gtk.Align.CENTER)
        refresh_stats_btn.connect("clicked", self._on_refresh_stats)
        refresh_stats_row.add_suffix(refresh_stats_btn)
        self.stats_group.add(refresh_stats_row)

        # Recent tracks section
        self.recent_group = Adw.PreferencesGroup()
        self.recent_group.set_title("Canciones recientes")
        self.recent_group.set_description("Tus últimas reproducciones en Last.fm")
        self.recent_group.set_visible(False)
        self.add(self.recent_group)

        # Connect text entries for auto-save if desired (although there's a save button now, the original code had these timeouts)
        self.api_key_entry.connect("changed", self._on_api_key_changed)
        self.api_secret_entry.connect("changed", self._on_api_secret_changed)

        self._update_lastfm_ui()

    def _update_lastfm_ui(self):
        if self.lastfm.connected:
            self.status_row.set_subtitle(f"Conectado como {self.lastfm.username}")
            self.api_key_entry.set_sensitive(False)
            self.api_secret_entry.set_sensitive(False)
            self.oauth_btn.set_visible(False)
            self.complete_oauth_row.set_visible(False)
            self.disconnect_row.set_visible(True)
            self.stats_group.set_visible(True)
            self.recent_group.set_visible(True)
            # Load stats automatically when connected
            self._load_lastfm_stats()
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
            self.stats_group.set_visible(False)
            self.recent_group.set_visible(False)

    def _on_api_key_changed(self, entry):
        if self._api_key_timeout:
            GLib.source_remove(self._api_key_timeout)

        def save_api_key():
            self.lastfm.api_key = entry.get_text().strip()
            self.lastfm._save_config()
            self._update_lastfm_ui()
            self._api_key_timeout = None
            return False

        self._api_key_timeout = GLib.timeout_add(300, save_api_key)

    def _on_api_secret_changed(self, entry):
        if self._api_secret_timeout:
            GLib.source_remove(self._api_secret_timeout)

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
        self.settings_dialog._show_error("Credenciales de API guardadas correctamente")

    def _on_oauth_start(self, btn):
        """Start OAuth flow by getting token and opening browser"""
        if not self.lastfm.configured:
            self.settings_dialog._show_error("Primero configura la API Key y API Secret de Last.fm.")
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
            self.settings_dialog._show_error("No se pudo obtener el token de autorización. Verifica tus credenciales de API.")

    def _on_oauth_complete(self, btn):
        """Complete OAuth flow after user authorization"""
        if not self._oauth_token:
            self.settings_dialog._show_error("No hay token de autorización. Inicia el proceso de nuevo.")
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
            self.settings_dialog._show_error("Conectado a Last.fm correctamente")
        else:
            self.status_row.set_subtitle("Error al completar autorización")
            self.settings_dialog._show_error("No se pudo completar la autorización. Asegúrate de haber autorizado la aplicación en el navegador.")

    def _on_lastfm_disconnect(self, btn):
        """Disconnect from Last.fm"""
        self.lastfm.disconnect()
        self._update_lastfm_ui()
        self.settings_dialog._show_error("Desconectado de Last.fm")

    def _load_lastfm_stats(self):
        """Load Last.fm user statistics in background"""
        if not self.lastfm.connected:
            return

        def load_stats():
            try:
                user_info = self.lastfm.get_user_info()
                recent_tracks = self.lastfm.get_recent_tracks(limit=5)
                GLib.idle_add(self._update_stats_display, user_info, recent_tracks)
            except Exception as e:
                print(f"[Settings] Error loading Last.fm stats: {e}")
                GLib.idle_add(self.play_count_row.set_subtitle, "Error al cargar estadísticas")

        import threading
        threading.Thread(target=load_stats, daemon=True).start()

    def _update_stats_display(self, user_info: Optional[dict], recent_tracks: list):
        """Update the UI with Last.fm statistics"""
        if user_info:
            play_count = user_info.get("playcount", "0")
            self.play_count_row.set_subtitle(f"{play_count} reproducciones")

        # Clear previous recent tracks
        if hasattr(self, "_recent_rows"):
            for row in self._recent_rows:
                try:
                    self.recent_group.remove(row)
                except Exception:
                    pass
        self._recent_rows = []

        # Add recent tracks
        if recent_tracks:
            for track in recent_tracks:
                track_name = track.get("name", "Desconocido")
                artist_name = track.get("artist", {}).get("name", "Desconocido")
                row = Adw.ActionRow()
                row.set_title(track_name)
                row.set_subtitle(artist_name)
                row.set_sensitive(False)
                self.recent_group.add(row)
                self._recent_rows.append(row)
        else:
            row = Adw.ActionRow()
            row.set_title("No hay canciones recientes")
            row.set_sensitive(False)
            self.recent_group.add(row)
            self._recent_rows.append(row)

    def _on_refresh_stats(self, btn):
        """Refresh Last.fm statistics"""
        self.play_count_row.set_subtitle("Actualizando...")
        self._load_lastfm_stats()
        self.settings_dialog._show_error("Estadísticas actualizadas")
