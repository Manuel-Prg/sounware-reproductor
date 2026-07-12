"""Página 'Acerca de' para los ajustes de Soundwave."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Adw, Gdk, GdkPixbuf, GLib
from pathlib import Path
import webbrowser
from typing import Optional


class AboutPage(Adw.PreferencesPage):
    def __init__(self, parent_window, settings_dialog):
        super().__init__()
        self.parent_window = parent_window
        self.settings_dialog = settings_dialog

        self.set_title("Acerca de")
        self.set_icon_name("help-about-symbolic")

        # Custom styles for the About Page
        css_provider = Gtk.CssProvider()
        css_provider.load_from_string("""
            .about-header-box {
                margin-top: 16px;
                margin-bottom: 8px;
            }
            .about-logo-card {
                background-color: @card_bg_color;
                border: 1px solid @card_border_color;
                border-radius: 18px;
                padding: 16px 28px;
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.05);
            }
            .about-logo {
                border-radius: 12px;
                box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
            }
            .about-logo-sep {
                color: @insensitive_fg_color;
                font-weight: bold;
                font-size: 20px;
            }
            .about-title {
                margin-top: 12px;
            }
            .about-version {
                margin-bottom: 12px;
            }
            .about-description {
                margin-top: 6px;
                margin-bottom: 16px;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        project_root = Path(__file__).resolve().parents[4]

        # ── Group 1: Header (No title) ───────────────────────────────────
        header_group = Adw.PreferencesGroup()
        self.add(header_group)

        # Header vertical box
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        header_box.add_css_class("about-header-box")
        header_box.set_halign(Gtk.Align.CENTER)
        header_group.add(header_box)

        # Logo Card
        logo_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        logo_card.add_css_class("about-logo-card")
        logo_card.set_halign(Gtk.Align.CENTER)
        logo_card.set_valign(Gtk.Align.CENTER)
        header_box.append(logo_card)

        # App Logo (Fixed size 72x72)
        app_logo_file = project_root / "data" / "icons" / "icono-light-256.png"
        if not app_logo_file.exists():
            app_logo_file = project_root / "data" / "icons" / "icono-dark.png"

        if app_logo_file.exists():
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(app_logo_file), 72, 72, True)
                if pixbuf:
                    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                    app_pic = Gtk.Picture.new_for_paintable(texture)
                    app_pic.set_size_request(72, 72)
                    app_pic.set_halign(Gtk.Align.CENTER)
                    app_pic.set_valign(Gtk.Align.CENTER)
                    app_pic.set_hexpand(False)
                    app_pic.set_vexpand(False)
                    app_pic.add_css_class("about-logo")
                    logo_card.append(app_pic)
            except Exception as e:
                print(f"[AboutPage] Error loading app logo: {e}")

        # Decorative separator label
        sep_lbl = Gtk.Label(label="×")
        sep_lbl.add_css_class("about-logo-sep")
        sep_lbl.set_valign(Gtk.Align.CENTER)
        logo_card.append(sep_lbl)

        # User Logo (Fixed size 72x72)
        self.user_pic_widget = Gtk.Picture()
        self.user_pic_widget.set_size_request(72, 72)
        self.user_pic_widget.set_halign(Gtk.Align.CENTER)
        self.user_pic_widget.set_valign(Gtk.Align.CENTER)
        self.user_pic_widget.set_hexpand(False)
        self.user_pic_widget.set_vexpand(False)
        self.user_pic_widget.add_css_class("about-logo")
        logo_card.append(self.user_pic_widget)

        # App Title
        title_lbl = Gtk.Label()
        title_lbl.set_markup("<b>Soundwave</b>")
        title_lbl.add_css_class("title-1")
        title_lbl.add_css_class("about-title")
        title_lbl.set_halign(Gtk.Align.CENTER)
        header_box.append(title_lbl)

        # App Version
        version_lbl = Gtk.Label(label="Versión 1.1.0")
        version_lbl.add_css_class("caption")
        version_lbl.add_css_class("dim-label")
        version_lbl.add_css_class("about-version")
        version_lbl.set_halign(Gtk.Align.CENTER)
        header_box.append(version_lbl)

        # Description
        desc_lbl = Gtk.Label()
        desc_lbl.set_markup(
            "Un reproductor de música nativo para Linux diseñado\n"
            "con GTK4 y Libadwaita con un enfoque premium."
        )
        desc_lbl.add_css_class("body")
        desc_lbl.add_css_class("dim-label")
        desc_lbl.add_css_class("about-description")
        desc_lbl.set_wrap(True)
        desc_lbl.set_justify(Gtk.Justification.CENTER)
        desc_lbl.set_halign(Gtk.Align.CENTER)
        header_box.append(desc_lbl)


        # ── Group 2: Información y Redes ─────────────────────────────────
        info_group = Adw.PreferencesGroup()
        info_group.set_title("Información y Redes")
        self.add(info_group)

        # Developer Row
        dev_row = Adw.ActionRow()
        dev_row.set_title("Desarrollador")
        dev_row.set_subtitle("Manuel Pérez (Manuel-Prg)")
        dev_icon = Gtk.Image.new_from_icon_name("avatar-default-symbolic")
        dev_row.add_prefix(dev_icon)
        info_group.add(dev_row)

        # Ko-fi Row
        kofi_row = Adw.ActionRow()
        kofi_row.set_title("Apoyar en Ko-fi")
        kofi_row.set_subtitle("kofi.com/O5O2PX2PA")
        kofi_row.set_activatable(True)
        
        # Load Kofi Icon
        self.kofi_icon_img = Gtk.Image()
        kofi_icon_file = project_root / "data" / "icons" / "kofi.png"
        if kofi_icon_file.exists():
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(kofi_icon_file), 24, 24, True)
                if pixbuf:
                    self.kofi_icon_img.set_from_pixbuf(pixbuf)
            except Exception as e:
                print(f"[AboutPage] Error loading Ko-fi icon: {e}")
                self.kofi_icon_img.set_from_icon_name("emblem-favorite-symbolic")
        else:
            self.kofi_icon_img.set_from_icon_name("emblem-favorite-symbolic")
            
        kofi_row.add_prefix(self.kofi_icon_img)
        
        # Suffix link icon
        kofi_link_icon = Gtk.Image.new_from_icon_name("window-new-symbolic")
        kofi_row.add_suffix(kofi_link_icon)
        kofi_row.connect("activated", lambda r: webbrowser.open("https://ko-fi.com/O5O2PX2PA"))
        info_group.add(kofi_row)

        # GitHub Row
        github_row = Adw.ActionRow()
        github_row.set_title("Código fuente")
        github_row.set_subtitle("github.com/Manuel-Prg/sounware-reproductor")
        github_row.set_activatable(True)
        
        self.github_icon_img = Gtk.Image()
        github_row.add_prefix(self.github_icon_img)
        
        # Suffix link icon
        github_link_icon = Gtk.Image.new_from_icon_name("window-new-symbolic")
        github_row.add_suffix(github_link_icon)
        github_row.connect("activated", lambda r: webbrowser.open("https://github.com/Manuel-Prg/sounware-reproductor"))
        info_group.add(github_row)


        # ── Group 3: Licencia y Sistema ──────────────────────────────────
        system_group = Adw.PreferencesGroup()
        system_group.set_title("Licencia y Sistema")
        self.add(system_group)

        # License Row
        license_row = Adw.ActionRow()
        license_row.set_title("Licencia")
        license_row.set_subtitle("Licencia MIT")
        license_icon = Gtk.Image.new_from_icon_name("document-properties-symbolic")
        license_row.add_prefix(license_icon)
        system_group.add(license_row)

        # Tech Row
        tech_row = Adw.ActionRow()
        tech_row.set_title("Tecnologías")
        tech_row.set_subtitle("Python, GTK4, Libadwaita, GStreamer")
        tech_icon = Gtk.Image.new_from_icon_name("preferences-system-symbolic")
        tech_row.add_prefix(tech_icon)
        system_group.add(tech_row)

        # Connect theme monitoring for user logo & GitHub icon
        style_manager = Adw.StyleManager.get_default()
        style_manager.connect("notify::dark", self._on_theme_changed)
        
        # Initial call to populate theme-dependent assets
        self.update_theme_dependent_widgets()

    def update_theme_dependent_widgets(self):
        style_manager = Adw.StyleManager.get_default()
        is_dark = style_manager.get_dark()
        project_root = Path(__file__).resolve().parents[4]

        # Update User Logo
        user_logo_name = "icono_black.png" if is_dark else "icono_light.png"
        user_logo_file = project_root / "data" / "icons" / user_logo_name
        if not user_logo_file.exists():
            user_logo_file = project_root / "data" / "icons" / "icono_light.png"
        
        if user_logo_file.exists():
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(user_logo_file), 72, 72, True)
                if pixbuf:
                    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                    self.user_pic_widget.set_paintable(texture)
            except Exception as e:
                print(f"[AboutPage] Error updating user logo: {e}")

        # Update GitHub Icon
        github_icon_name = "GitHub_Invertocat_White_Clearspace.svg" if is_dark else "GitHub_Invertocat_Black_Clearspace.svg"
        github_icon_file = project_root / "data" / "icons" / github_icon_name
        if github_icon_file.exists():
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(github_icon_file), 24, 24, True)
                if pixbuf:
                    self.github_icon_img.set_from_pixbuf(pixbuf)
            except Exception as e:
                print(f"[AboutPage] Error updating GitHub icon: {e}")

    def _on_theme_changed(self, style_manager, pspec):
        self.update_theme_dependent_widgets()
