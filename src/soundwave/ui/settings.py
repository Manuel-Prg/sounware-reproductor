import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from pathlib import Path
from soundwave.library.config import save_setting, apply_theme
from soundwave.library.smart_playlist import evaluate_rules
from soundwave.library.database import Database

class SettingsDialog(Adw.PreferencesWindow):
    def __init__(self, parent_window, lastfm):
        super().__init__(transient_for=parent_window, modal=True)
        self.parent_window = parent_window
        self.lastfm = lastfm

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
        from soundwave.library.config import load_settings
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

        self.user_row = Adw.EntryRow()
        self.user_row.set_title("Usuario")
        lastfm_group.add(self.user_row)

        self.pass_row = Adw.PasswordEntryRow()
        self.pass_row.set_title("Contraseña")
        lastfm_group.add(self.pass_row)

        btn_row = Adw.ActionRow()
        self.action_btn = Gtk.Button()
        self.action_btn.set_valign(Gtk.Align.CENTER)
        self.action_btn.connect("clicked", self._on_lastfm_action)
        btn_row.add_suffix(self.action_btn)
        lastfm_group.add(btn_row)

        # Page 3: Smart Playlists
        smart_page = Adw.PreferencesPage()
        smart_page.set_title("Listas Inteligentes")
        smart_page.set_icon_name("folder-music-symbolic")
        self.add(smart_page)

        smart_group = Adw.PreferencesGroup()
        smart_group.set_title("Listas de reproducción automáticas")
        smart_group.set_description("Las listas inteligentes se actualizan solas según las reglas definidas")
        smart_page.add(smart_group)

        PRESET_RULES = [
            ("Recién Añadido", "Canciones agregadas recientemente", {"year_min": 2024}),
            ("Favoritos", "Canciones con mejor valoración", {"rating_min": 4}),
            ("Más Escuchadas", "Canciones con más reproducciones", {"play_count_min": 10}),
            ("Jazz", "Canciones del género Jazz", {"genre": "Jazz"}),
            ("Rock", "Canciones del género Rock", {"genre": "Rock"}),
            ("Electrónica", "Canciones del género Electrónica", {"genre": "Electronic"}),
        ]

        for name, desc, rules in PRESET_RULES:
            row = Adw.ActionRow()
            row.set_title(name)
            row.set_subtitle(desc)
            btn = Gtk.Button(label="Reproducir")
            btn.set_valign(Gtk.Align.CENTER)
            btn.set_css_classes(["suggested-action"])
            btn.connect("clicked", self._on_play_smart, rules)
            row.add_suffix(btn)
            smart_group.add(row)

        self._update_lastfm_ui()

    def _on_play_smart(self, btn, rules):
        db = self.parent_window.db
        songs = evaluate_rules(db, rules)
        if songs:
            for cb in self.parent_window._library_view._play_song_cbs:
                cb(songs[0], songs)
            self.close()

    def _update_lastfm_ui(self):
        if self.lastfm.connected:
            self.status_row.set_subtitle(f"Conectado como {self.lastfm.username}")
            self.user_row.set_sensitive(False)
            self.pass_row.set_sensitive(False)
            self.user_row.set_text(self.lastfm.username or "")
            self.pass_row.set_text("********")
            self.action_btn.set_label("Desconectar")
            self.action_btn.set_css_classes(["destructive-action"])
        else:
            self.status_row.set_subtitle("Desconectado")
            self.user_row.set_sensitive(True)
            self.pass_row.set_sensitive(True)
            self.user_row.set_text("")
            self.pass_row.set_text("")
            self.action_btn.set_label("Conectar")
            self.action_btn.set_css_classes(["suggested-action"])

    def _on_scan_clicked(self, btn):
        self.close()
        self.parent_window._open_folder_picker()

    def _on_lastfm_action(self, btn):
        if self.lastfm.connected:
            self.lastfm.disconnect()
            self._update_lastfm_ui()
        else:
            username = self.user_row.get_text().strip()
            password = self.pass_row.get_text().strip()
            if not username or not password:
                self._show_error("Por favor, introduce tu usuario y contraseña.")
                return

            self.action_btn.set_sensitive(False)
            self.status_row.set_subtitle("Conectando...")

            # Run auth in background to avoid freezing the UI
            def do_auth():
                success = self.lastfm.authenticate(username, password)
                GLib.idle_add(self._on_auth_complete, success)

            import threading
            threading.Thread(target=do_auth, daemon=True).start()

    def _on_auth_complete(self, success: bool):
        self.action_btn.set_sensitive(True)
        if success:
            self._update_lastfm_ui()
        else:
            self.status_row.set_subtitle("Error de conexión o credenciales incorrectas")
            self._show_error("No se pudo iniciar sesión. Verifica tu usuario y contraseña.")

    def _show_error(self, message: str):
        toast = Adw.Toast.new(message)
        self.add_toast(toast)
