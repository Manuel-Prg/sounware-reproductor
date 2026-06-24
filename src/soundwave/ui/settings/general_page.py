import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio

from pathlib import Path
from typing import Optional
from soundwave.library.config.config import load_settings, save_setting, apply_theme


class GeneralPage(Adw.PreferencesPage):
    def __init__(self, parent_window, settings_dialog):
        super().__init__()
        self.parent_window = parent_window
        self.settings_dialog = settings_dialog
        
        self.set_title("General")
        self.set_icon_name("preferences-other-symbolic")

        # Group 1: Appearance
        appearance_group = Adw.PreferencesGroup()
        appearance_group.set_title("Apariencia")
        appearance_group.set_description("Configura cómo se ve el reproductor")
        self.add(appearance_group)

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
        self.add(library_group)

        scan_row = Adw.ActionRow()
        scan_row.set_title("Añadir / Escanear carpeta")
        scan_row.set_subtitle("Selecciona una carpeta para buscar archivos de audio")
        scan_btn = Gtk.Button(label="Seleccionar...")
        scan_btn.set_valign(Gtk.Align.CENTER)
        scan_btn.connect("clicked", self._on_scan_clicked)
        scan_row.add_suffix(scan_btn)
        library_group.add(scan_row)

        # Action row: Re-scan library
        rescan_row = Adw.ActionRow()
        rescan_row.set_title("Actualizar / Re-escanear biblioteca")
        rescan_row.set_subtitle("Busca música nueva o eliminada en las carpetas de tu colección")
        rescan_btn = Gtk.Button(label="Re-escanear")
        rescan_btn.set_valign(Gtk.Align.CENTER)
        rescan_btn.connect("clicked", self._on_rescan_clicked)
        rescan_row.add_suffix(rescan_btn)
        library_group.add(rescan_row)

        # Album art download toggle
        art_download_row = Adw.SwitchRow()
        art_download_row.set_title("Descargar carátulas faltantes")
        art_download_row.set_subtitle("Busca y descarga en internet las carátulas de álbumes que no las tengan")
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
        self.add(audio_group)

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
            mode = "off"
            if selected == 0:
                mode = "off"
            elif selected == 1:
                mode = "track"
            elif selected == 2:
                mode = "album"
            save_setting("replaygain_mode", mode)
            if hasattr(self.parent_window, "player") and self.parent_window.player:
                self.parent_window.player._replaygain_mode = mode
                self.parent_window.player._apply_volume_with_gain()

        replaygain_row.connect("notify::selected", on_replaygain_changed)
        audio_group.add(replaygain_row)

        # Crossfade setting
        crossfade_row = Adw.SpinRow()
        crossfade_row.set_title("Crossfade")
        crossfade_row.set_subtitle("Tiempo de transición suave entre canciones (segundos)")
        crossfade_row.set_adjustment(Gtk.Adjustment.new(0, 0, 10, 0.5, 1, 0))
        
        # Cargar configuración actual de Crossfade
        settings = load_settings()
        current_crossfade = settings.get("crossfade_duration", 0)
        crossfade_row.set_value(current_crossfade)

        def on_crossfade_changed(row, pspec):
            val = row.get_value()
            save_setting("crossfade_duration", val)
            if hasattr(self.parent_window, "player") and self.parent_window.player:
                self.parent_window.player._crossfade_duration = val

        crossfade_row.connect("notify::value", on_crossfade_changed)
        audio_group.add(crossfade_row)

        # Gapless playback setting
        gapless_row = Adw.SwitchRow()
        gapless_row.set_title("Reproducción sin pausa")
        gapless_row.set_subtitle("Reproduce las canciones de forma continua sin silencios entre ellas")
        
        # Cargar configuración actual de reproducción sin pausa
        settings = load_settings()
        current_gapless = settings.get("gapless_enabled", True)
        gapless_row.set_active(current_gapless)

        def on_gapless_toggled(row, pspec):
            val = row.get_active()
            save_setting("gapless_enabled", val)
            if hasattr(self.parent_window, "player") and self.parent_window.player:
                self.parent_window.player.set_gapless_enabled(val)

        gapless_row.connect("notify::active", on_gapless_toggled)
        audio_group.add(gapless_row)

        # Equalizer bands setting
        eq_bands_row = Adw.ComboRow()
        eq_bands_row.set_title("Bandas del Ecualizador")
        eq_bands_row.set_subtitle("Número de bandas del ecualizador (más bandas = más control)")
        eq_bands_model = Gtk.StringList.new(["3 bandas", "5 bandas", "10 bandas"])
        eq_bands_row.set_model(eq_bands_model)

        # Cargar configuración actual de bandas
        settings = load_settings()
        current_n_bands = settings.get("equalizer_n_bands", 10)
        if current_n_bands == 3:
            eq_bands_row.set_selected(0)
        elif current_n_bands == 5:
            eq_bands_row.set_selected(1)
        elif current_n_bands == 10:
            eq_bands_row.set_selected(2)
        else:
            eq_bands_row.set_selected(2)  # Default to 10

        def on_eq_bands_changed(row, pspec):
            selected = row.get_selected()
            n_bands_map = [3, 5, 10]
            n_bands = n_bands_map[selected]
            save_setting("equalizer_n_bands", n_bands)

        eq_bands_row.connect("notify::selected", on_eq_bands_changed)
        audio_group.add(eq_bands_row)

        # Group: Playlists M3U8
        playlists_group = Adw.PreferencesGroup()
        playlists_group.set_title("Listas de reproducción")
        playlists_group.set_description("Importa y exporta listas de reproducción de la biblioteca")
        self.add(playlists_group)

        # Switch row: also export file based formats
        export_file_based_row = Adw.SwitchRow()
        export_file_based_row.set_title("También exportar listas de reproducción basada en archivos (.m3u8, .pls, etc.)")
        export_file_based_row.set_subtitle("Exporta archivos adicionales cuando exportes tus listas de reproducción")
        settings = load_settings()
        export_file_based_row.set_active(settings.get("export_file_based_playlists", False))

        def on_export_file_based_toggled(row, pspec):
            save_setting("export_file_based_playlists", row.get_active())

        export_file_based_row.connect("notify::active", on_export_file_based_toggled)
        playlists_group.add(export_file_based_row)

        # Action row: Import playlist
        import_playlist_row = Adw.ActionRow()
        import_playlist_row.set_title("Importar lista de reproducción")
        import_playlist_row.set_subtitle("Importa una lista de reproducción desde un archivo .m3u8 o .m3u")
        import_playlist_btn = Gtk.Button(label="Importar...")
        import_playlist_btn.set_valign(Gtk.Align.CENTER)
        import_playlist_btn.connect("clicked", self._on_import_playlist_clicked)
        import_playlist_row.add_suffix(import_playlist_btn)
        playlists_group.add(import_playlist_row)

        # Action row: Export playlist
        export_playlist_row = Adw.ActionRow()
        export_playlist_row.set_title("Exportar lista de reproducción")
        export_playlist_row.set_subtitle("Exporta una lista de reproducción de la biblioteca a formato M3U8")
        export_playlist_btn = Gtk.Button(label="Exportar...")
        export_playlist_btn.set_valign(Gtk.Align.CENTER)
        export_playlist_btn.connect("clicked", self._on_export_playlist_clicked)
        export_playlist_row.add_suffix(export_playlist_btn)
        playlists_group.add(export_playlist_row)

        # Group 4: Help / Onboarding
        help_group = Adw.PreferencesGroup()
        help_group.set_title("Ayuda")
        help_group.set_description("Guías y tutoriales de Soundwave")
        self.add(help_group)

        onboarding_row = Adw.ActionRow()
        onboarding_row.set_title("Ver tutorial de inicio")
        onboarding_row.set_subtitle("Muestra la guía rápida de bienvenida y configuración")
        onboarding_btn = Gtk.Button(label="Mostrar guía")
        onboarding_btn.set_valign(Gtk.Align.CENTER)
        onboarding_btn.connect("clicked", self._on_onboarding_clicked)
        onboarding_row.add_suffix(onboarding_btn)
        help_group.add(onboarding_row)

    def _on_scan_clicked(self, btn):
        self.settings_dialog.close()
        self.parent_window._open_folder_picker()

    def _on_rescan_clicked(self, btn):
        self.settings_dialog.close()
        if hasattr(self.parent_window, "_start_rescan"):
            self.parent_window._start_rescan()

    def _on_onboarding_clicked(self, btn):
        self.settings_dialog.close()
        from soundwave.ui.window.onboarding import OnboardingWindow
        dialog = OnboardingWindow(self.parent_window)
        dialog.present()

    def _on_batch_art_clicked(self, btn):
        self.batch_art_btn.set_sensitive(False)
        self.batch_art_btn.set_label("Buscando...")
        self.batch_art_row.set_subtitle("Descargando carátulas en segundo plano...")

        db_path = self.parent_window.db.db_path

        def run_batch():
            try:
                from soundwave.library.metadata.album_art import get_art_path, download_and_cache_album_art
                from soundwave.library.database.database import Database
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

    def _on_import_playlist_clicked(self, btn):
        if hasattr(Gtk, "FileDialog"):
            dialog = Gtk.FileDialog.new()
            dialog.set_title("Importar lista de reproducción")
            
            f = Gtk.FileFilter()
            f.set_name("Listas de reproducción M3U8/M3U (*.m3u8, *.m3u)")
            f.add_pattern("*.m3u8")
            f.add_pattern("*.m3u")
            
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(f)
            dialog.set_filters(filters)

            def on_file_selected(dialog, result):
                try:
                    file = dialog.open_finish(result)
                    if file:
                        path = Path(file.get_path())
                        self._do_import_playlist(path)
                except GLib.Error as e:
                    print("Importación cancelada o fallida:", e)

            dialog.open(self.settings_dialog, None, on_file_selected)
        else:
            dialog = Gtk.FileChooserNative.new(
                title="Importar lista de reproducción",
                parent=self.settings_dialog,
                action=Gtk.FileChooserAction.OPEN,
                accept_label="Importar",
                cancel_label="Cancelar"
            )
            f = Gtk.FileFilter()
            f.set_name("Listas de reproducción M3U8/M3U (*.m3u8, *.m3u)")
            f.add_pattern("*.m3u8")
            f.add_pattern("*.m3u")
            dialog.add_filter(f)

            def on_response(dialog, response_id):
                if response_id == Gtk.ResponseType.ACCEPT:
                    file = dialog.get_file()
                    if file:
                        path = Path(file.get_path())
                        self._do_import_playlist(path)
                self._file_chooser = None

            dialog.connect("response", on_response)
            dialog.show()

    def _do_import_playlist(self, path: Path):
        try:
            from soundwave.library.playlists.m3u8 import import_playlist_from_m3u8
            playlist_name = import_playlist_from_m3u8(self.parent_window.db, path)
            self.settings_dialog._show_error(f"Lista '{playlist_name}' importada con éxito.")
            if hasattr(self.parent_window, "_library_view"):
                GLib.idle_add(self.parent_window._library_view.refresh)
        except Exception as e:
            print(f"[Import M3U8] Error: {e}")
            self.settings_dialog._show_error(f"Error al importar: {e}")

    def _on_export_playlist_clicked(self, btn):
        playlists = self.parent_window.db.get_playlists()
        if not playlists:
            self.settings_dialog._show_error("No hay listas de reproducción en la biblioteca para exportar.")
            return

        from soundwave.ui.library.library_dialogs import ExportPlaylistDialog
        dialog = ExportPlaylistDialog(self.settings_dialog, playlists, self._prompt_save_playlist)
        dialog.present()

    def _prompt_save_playlist(self, playlist):
        if hasattr(Gtk, "FileDialog"):
            dialog = Gtk.FileDialog.new()
            dialog.set_title(f"Exportar lista '{playlist.name}'")
            dialog.set_initial_name(f"{playlist.name}.m3u8")
            
            f = Gtk.FileFilter()
            f.set_name("Lista de reproducción M3U8 (*.m3u8)")
            f.add_pattern("*.m3u8")
            
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(f)
            dialog.set_filters(filters)

            def on_save_selected(dialog, result):
                try:
                    file = dialog.save_finish(result)
                    if file:
                        path = Path(file.get_path())
                        self._do_export_playlist(playlist, path)
                except GLib.Error as e:
                    print("Exportación cancelada o fallida:", e)

            dialog.save(self.settings_dialog, None, on_save_selected)
        else:
            dialog = Gtk.FileChooserNative.new(
                title=f"Exportar lista '{playlist.name}'",
                parent=self.settings_dialog,
                action=Gtk.FileChooserAction.SAVE,
                accept_label="Guardar",
                cancel_label="Cancelar"
            )
            dialog.set_current_name(f"{playlist.name}.m3u8")
            
            f = Gtk.FileFilter()
            f.set_name("Lista de reproducción M3U8 (*.m3u8)")
            f.add_pattern("*.m3u8")
            dialog.add_filter(f)

            def on_response(dialog, response_id):
                if response_id == Gtk.ResponseType.ACCEPT:
                    file = dialog.get_file()
                    if file:
                        path = Path(file.get_path())
                        self._do_export_playlist(playlist, path)
                self._file_chooser = None

            dialog.connect("response", on_response)
            dialog.show()

    def _do_export_playlist(self, playlist, path: Path):
        try:
            from soundwave.library.playlists.m3u8 import export_playlist_to_m3u8
            settings = load_settings()
            also_export_file_based = settings.get("export_file_based_playlists", False)
            
            export_playlist_to_m3u8(
                self.parent_window.db, 
                playlist.id, 
                path, 
                also_export_file_based=also_export_file_based
            )
            
            msg = f"Lista '{playlist.name}' exportada con éxito."
            if also_export_file_based:
                msg += " (Se exportaron archivos .m3u8 y .pls)"
            self.settings_dialog._show_error(msg)
        except Exception as e:
            print(f"[Export M3U8] Error: {e}")
            self.settings_dialog._show_error(f"Error al exportar: {e}")
