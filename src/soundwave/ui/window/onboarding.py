"""Onboarding de inicio para Soundwave."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Adw, GLib, Gdk, GdkPixbuf
from pathlib import Path

class OnboardingWindow(Adw.Window):
    def __init__(self, parent_window):
        super().__init__(transient_for=parent_window, modal=True)
        self.parent_window = parent_window
        self.set_title("Guía de Inicio de Soundwave")
        self.set_default_size(560, 620)
        self.set_resizable(False)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        header_bar = Adw.HeaderBar()
        header_bar.set_show_start_title_buttons(False)
        header_bar.set_show_end_title_buttons(True)
        main_box.append(header_bar)

        # Carousel
        self.carousel = Adw.Carousel()
        self.carousel.set_vexpand(True)
        self.carousel.set_hexpand(True)
        main_box.append(self.carousel)

        # Slides
        self.carousel.append(self._build_slide_welcome())
        self.carousel.append(self._build_slide_interactivity())
        self.carousel.append(self._build_slide_library())
        self.carousel.append(self._build_slide_shortcuts())

        # Bottom navigation controls
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        bottom_box.set_margin_start(24)
        bottom_box.set_margin_end(24)
        bottom_box.set_margin_top(12)
        bottom_box.set_margin_bottom(20)

        # Left: Back button
        self.btn_back = Gtk.Button(label="Anterior")
        self.btn_back.connect("clicked", self._on_back_clicked)
        bottom_box.append(self.btn_back)

        # Center: Indicator Dots
        dots = Adw.CarouselIndicatorDots()
        dots.set_carousel(self.carousel)
        dots.set_hexpand(True)
        dots.set_halign(Gtk.Align.CENTER)
        bottom_box.append(dots)

        # Right: Next/Empezar button
        self.btn_next = Gtk.Button(label="Siguiente")
        self.btn_next.add_css_class("suggested-action")
        self.btn_next.connect("clicked", self._on_next_clicked)
        bottom_box.append(self.btn_next)

        main_box.append(bottom_box)

        self.carousel.connect("notify::position", self._on_carousel_position_changed)
        self._update_navigation_buttons(0.0)

    def _on_carousel_position_changed(self, carousel, pspec):
        pos = carousel.get_position()
        self._update_navigation_buttons(pos)

    def _update_navigation_buttons(self, pos):
        page = int(round(pos))
        self.btn_back.set_sensitive(page > 0)
        if page == 3:
            self.btn_next.set_label("Empezar")
        else:
            self.btn_next.set_label("Siguiente")

    def _on_back_clicked(self, btn):
        page = round(self.carousel.get_position())
        if page > 0:
            self.carousel.scroll_to(self.carousel.get_nth_page(page - 1), True)

    def _on_next_clicked(self, btn):
        page = round(self.carousel.get_position())
        if page < 3:
            self.carousel.scroll_to(self.carousel.get_nth_page(page + 1), True)
        else:
            from soundwave.library.config.config import save_setting
            save_setting("onboarding_completed", True)
            self.close()

    # --- Slide Builders ---

    def _get_app_logo(self, size=128):
        # Check active theme to decide logo-dark or logo-light
        style_manager = Adw.StyleManager.get_default()
        is_dark = style_manager.get_dark()
        
        logo_name = "icono-dark.png" if is_dark else "icono-light.png"
        project_root = Path(__file__).resolve().parents[4]
        logo_file = project_root / "data" / "icons" / logo_name
        
        # Fallback if file doesn't exist
        if not logo_file.exists():
            logo_file = project_root / "data" / "icons" / "icono-dark.png"
            
        if logo_file.exists():
            try:
                pic = Gtk.Picture.new_for_filename(str(logo_file))
                pic.set_size_request(size, size)
                pic.set_halign(Gtk.Align.CENTER)
                pic.set_valign(Gtk.Align.CENTER)
                pic.set_hexpand(False)
                pic.set_vexpand(False)
                return pic
            except Exception as e:
                print(f"[Onboarding] Error loading logo file: {e}")
                
        # Generic fallback
        fallback_icon = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")
        fallback_icon.set_pixel_size(size)
        fallback_icon.set_halign(Gtk.Align.CENTER)
        return fallback_icon

    def _build_slide_welcome(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_start(32)
        box.set_margin_end(32)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_valign(Gtk.Align.CENTER)

        # Large Logo
        logo = self._get_app_logo(128)
        box.append(logo)

        # Title
        title = Gtk.Label()
        title.set_markup("<span size='xx-large' weight='bold'>Bienvenido a Soundwave</span>")
        title.set_halign(Gtk.Align.CENTER)
        box.append(title)

        # Subtitle
        subtitle = Gtk.Label()
        subtitle.set_markup("<span size='medium' alpha='70%'>El reproductor de música premium para tu biblioteca local</span>")
        subtitle.set_halign(Gtk.Align.CENTER)
        subtitle.set_wrap(True)
        subtitle.set_justify(Gtk.Justification.CENTER)
        box.append(subtitle)

        # Features list
        features_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        features_box.set_halign(Gtk.Align.CENTER)
        features_box.set_margin_top(16)

        features = [
            "<b>Ecualizador de precisión</b> de hasta 10 bandas y AutoEQ.",
            "<b>Visualizador ultra-sensible</b> con múltiples modos de ondas y espectros.",
            "<b>Letras sincronizadas</b> en tiempo real durante la reproducción."
        ]
        for desc in features:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.set_halign(Gtk.Align.START)
            
            bullet_lbl = Gtk.Label()
            bullet_lbl.set_markup("<span size='large' color='#1DB954'>•</span>")
            row.append(bullet_lbl)
            
            desc_lbl = Gtk.Label()
            desc_lbl.set_markup(desc)
            desc_lbl.set_wrap(True)
            desc_lbl.set_xalign(0)
            row.append(desc_lbl)
            features_box.append(row)

        box.append(features_box)
        return box

    def _build_slide_interactivity(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_start(32)
        box.set_margin_end(32)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_valign(Gtk.Align.CENTER)

        # Large Icon
        icon = Gtk.Image.new_from_icon_name("media-optical-symbolic")
        icon.set_pixel_size(96)
        icon.set_halign(Gtk.Align.CENTER)
        box.append(icon)

        # Title
        title = Gtk.Label()
        title.set_markup("<span size='xx-large' weight='bold'>Visualizador e Interactividad</span>")
        title.set_halign(Gtk.Align.CENTER)
        box.append(title)

        # Description
        desc_lbl = Gtk.Label()
        desc_lbl.set_markup(
            "<span size='medium'>¡Sácale el máximo partido al reproductor! "
            "La vista del visualizador es completamente interactiva:</span>"
        )
        desc_lbl.set_halign(Gtk.Align.CENTER)
        desc_lbl.set_wrap(True)
        desc_lbl.set_justify(Gtk.Justification.CENTER)
        box.append(desc_lbl)

        # Tips
        tips_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        tips_box.set_halign(Gtk.Align.CENTER)
        tips_box.set_margin_top(12)

        tips = [
            "<b>Ver Discografía Completa</b>: Haz clic sobre el nombre del artista en el visualizador para abrir al instante todos sus álbumes y canciones.",
            "<b>Pantalla Completa</b>: Haz doble clic en el visualizador o presiona <b>F11</b> para entrar/salir de pantalla completa.",
            "<b>Cambiar de Modo</b>: Haz clic sobre la carátula para alternar entre los modos de visualización (radial, barras de bloque, espectro u ondas)."
        ]
        for text in tips:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.set_halign(Gtk.Align.START)
            
            bullet_lbl = Gtk.Label()
            bullet_lbl.set_markup("<span size='large' color='#1DB954'>•</span>")
            row.append(bullet_lbl)
            
            text_lbl = Gtk.Label()
            text_lbl.set_markup(text)
            text_lbl.set_wrap(True)
            text_lbl.set_xalign(0)
            text_lbl.set_max_width_chars(45)
            row.append(text_lbl)
            tips_box.append(row)

        box.append(tips_box)
        return box

    def _build_slide_library(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_start(32)
        box.set_margin_end(32)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_valign(Gtk.Align.CENTER)

        # Large Icon
        icon = Gtk.Image.new_from_icon_name("folder-music-symbolic")
        icon.set_pixel_size(96)
        icon.set_halign(Gtk.Align.CENTER)
        box.append(icon)

        # Title
        title = Gtk.Label()
        title.set_markup("<span size='xx-large' weight='bold'>Tu Biblioteca de Música</span>")
        title.set_halign(Gtk.Align.CENTER)
        box.append(title)

        # Description
        desc = Gtk.Label()
        desc.set_markup(
            "Selecciona la carpeta raíz donde almacenas tus archivos de audio. "
            "Soundwave los importará y organizará automáticamente por artistas, álbumes y géneros."
        )
        desc.set_halign(Gtk.Align.CENTER)
        desc.set_wrap(True)
        desc.set_justify(Gtk.Justification.CENTER)
        box.append(desc)

        # Folder list status
        self.folder_status_lbl = Gtk.Label()
        self.folder_status_lbl.set_halign(Gtk.Align.CENTER)
        self.folder_status_lbl.set_margin_top(8)
        self.folder_status_lbl.set_margin_bottom(8)
        self._update_folder_status()
        box.append(self.folder_status_lbl)

        # Add Folder Button
        add_btn = Gtk.Button(label="Añadir carpeta de música...")
        add_btn.set_halign(Gtk.Align.CENTER)
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._on_add_folder_clicked)
        box.append(add_btn)

        return box

    def _update_folder_status(self):
        from soundwave.library.config.config import load_settings
        settings = load_settings()
        dirs = settings.get("music_directories", [])
        if dirs:
            paths_str = "\n".join([f"• {Path(d).name}" for d in dirs[:3]])
            if len(dirs) > 3:
                paths_str += f"\n• ...y {len(dirs) - 3} más"
            self.folder_status_lbl.set_markup(
                f"<span color='#1DB954' weight='bold'>Carpetas configuradas:</span>\n{paths_str}"
            )
        else:
            self.folder_status_lbl.set_markup(
                "<span color='#ff7800'>Ninguna carpeta seleccionada aún.</span>"
            )

    def _on_add_folder_clicked(self, btn):
        if hasattr(self.parent_window, "_open_folder_picker"):
            self.parent_window._open_folder_picker()
            GLib.timeout_add(1000, self._check_folders_update)

    def _check_folders_update(self):
        if not self.get_realized():
            return False
        self._update_folder_status()
        return True

    def _build_slide_shortcuts(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(32)
        box.set_margin_end(32)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_valign(Gtk.Align.CENTER)

        # Title
        title = Gtk.Label()
        title.set_markup("<span size='xx-large' weight='bold'>Atajos de Teclado Rápidos</span>")
        title.set_halign(Gtk.Align.CENTER)
        box.append(title)

        # Grid for shortcuts
        grid = Gtk.Grid()
        grid.set_column_spacing(24)
        grid.set_row_spacing(6)
        grid.set_halign(Gtk.Align.CENTER)

        shortcuts = [
            ("Espacio", "Reproducir / Pausar"),
            ("Ctrl + Flecha Derecha", "Siguiente canción"),
            ("Ctrl + Flecha Izquierda", "Anterior canción"),
            ("Ctrl + F", "Buscar en biblioteca"),
            ("Ctrl + E", "Abrir Ecualizador"),
            ("Ctrl + M", "Modo Mini-reproductor"),
            ("Ctrl + B", "Mostrar / Ocultar barra lateral"),
            ("F11", "Entrar / Salir Pantalla completa")
        ]
        for idx, (key, action) in enumerate(shortcuts):
            key_lbl = Gtk.Label()
            key_lbl.set_markup(f"<span bgcolor='#333333' color='#eeeeee' font_family='monospace'>  {key}  </span>")
            key_lbl.set_halign(Gtk.Align.END)
            grid.attach(key_lbl, 0, idx, 1, 1)

            action_lbl = Gtk.Label(label=action)
            action_lbl.set_halign(Gtk.Align.START)
            grid.attach(action_lbl, 1, idx, 1, 1)

        box.append(grid)

        # Options box
        options_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        options_box.set_margin_top(12)
        options_box.set_halign(Gtk.Align.CENTER)

        art_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        art_box.set_halign(Gtk.Align.CENTER)

        art_switch = Gtk.Switch()
        from soundwave.library.config.config import load_settings, save_setting
        settings = load_settings()
        art_switch.set_active(settings.get("download_missing_art", False))

        def on_art_toggled(switch, pspec):
            save_setting("download_missing_art", switch.get_active())

        art_switch.connect("notify::active", on_art_toggled)
        art_box.append(art_switch)

        art_lbl = Gtk.Label(label="Descargar automáticamente carátulas faltantes")
        art_box.append(art_lbl)
        options_box.append(art_box)

        box.append(options_box)
        return box
