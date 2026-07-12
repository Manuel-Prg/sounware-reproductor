"""Página 'Acerca de' para los ajustes de Soundwave."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk
from pathlib import Path
import webbrowser


class AboutPage(Adw.PreferencesPage):
    def __init__(self, parent_window, settings_dialog):
        super().__init__()
        self.parent_window = parent_window
        self.settings_dialog = settings_dialog

        self.set_title("Acerca de")
        self.set_icon_name("help-about-symbolic")

        # Main Group
        group = Adw.PreferencesGroup()
        self.add(group)

        # Main vertical container for About content
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        main_box.set_margin_top(24)
        main_box.set_margin_bottom(24)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        main_box.set_halign(Gtk.Align.CENTER)

        # Container for the Logos side-by-side
        logos_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        logos_box.set_halign(Gtk.Align.CENTER)
        logos_box.set_valign(Gtk.Align.CENTER)

        # Determine paths
        project_root = Path(__file__).resolve().parents[4]
        style_manager = Adw.StyleManager.get_default()
        is_dark = style_manager.get_dark()

        # 1. App Logo
        app_logo_name = "icono-light-256.png"
        app_logo_file = project_root / "data" / "icons" / app_logo_name
        if not app_logo_file.exists():
            app_logo_file = project_root / "data" / "icons" / "icono-dark.png"

        # 2. User Logo ("mi logo")
        # In data/icons we have: icono_light.png (for light theme) and icono_black.png (for dark theme)
        user_logo_name = "icono_black.png" if is_dark else "icono_light.png"
        user_logo_file = project_root / "data" / "icons" / user_logo_name
        if not user_logo_file.exists():
            user_logo_file = project_root / "data" / "icons" / "icono_light.png"

        # App logo widget
        app_pic_widget = None
        if app_logo_file.exists():
            try:
                app_pic_widget = Gtk.Picture.new_for_filename(str(app_logo_file))
                app_pic_widget.set_size_request(88, 88)
                app_pic_widget.set_halign(Gtk.Align.CENTER)
                app_pic_widget.set_valign(Gtk.Align.CENTER)
            except Exception as e:
                print(f"[AboutPage] Error loading app logo: {e}")

        # User logo widget
        user_pic_widget = None
        if user_logo_file.exists():
            try:
                user_pic_widget = Gtk.Picture.new_for_filename(str(user_logo_file))
                user_pic_widget.set_size_request(88, 88)
                user_pic_widget.set_halign(Gtk.Align.CENTER)
                user_pic_widget.set_valign(Gtk.Align.CENTER)
            except Exception as e:
                print(f"[AboutPage] Error loading user logo: {e}")

        if app_pic_widget:
            logos_box.append(app_pic_widget)

        # Decorative X separator between logos
        x_label = Gtk.Label()
        x_label.set_markup("<span size='large' alpha='40%' weight='bold'>×</span>")
        x_label.set_valign(Gtk.Align.CENTER)
        logos_box.append(x_label)

        if user_pic_widget:
            logos_box.append(user_pic_widget)

        main_box.append(logos_box)

        # App Title & Version Info
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_halign(Gtk.Align.CENTER)

        title_lbl = Gtk.Label()
        title_lbl.set_markup("<span size='x-large' weight='bold'>Soundwave</span>")
        title_lbl.set_halign(Gtk.Align.CENTER)
        info_box.append(title_lbl)

        version_lbl = Gtk.Label()
        version_lbl.set_markup("<span size='medium' alpha='70%'>Versión 1.1.0</span>")
        version_lbl.set_halign(Gtk.Align.CENTER)
        info_box.append(version_lbl)

        main_box.append(info_box)

        # Developer Info
        dev_lbl = Gtk.Label()
        dev_lbl.set_markup("<span size='medium'>Desarrollado por <b>Manuel Pérez (Manuel-Prg)</b></span>")
        dev_lbl.set_halign(Gtk.Align.CENTER)
        main_box.append(dev_lbl)

        # App Description
        desc_lbl = Gtk.Label()
        desc_lbl.set_markup(
            "<span size='small' alpha='65%'>Un reproductor de música nativo para Linux diseñado\n"
            "con GTK4 y Libadwaita con un enfoque premium.</span>"
        )
        desc_lbl.set_wrap(True)
        desc_lbl.set_justify(Gtk.Justification.CENTER)
        desc_lbl.set_halign(Gtk.Align.CENTER)
        main_box.append(desc_lbl)

        # Social & Support Buttons Box
        buttons_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        buttons_box.set_margin_top(12)
        buttons_box.set_halign(Gtk.Align.FILL)

        # ── Ko-fi Support Button ──────────────────────────────────────────
        kofi_btn = Gtk.Button()
        kofi_btn.set_tooltip_text("Apóyame en Ko-fi")
        kofi_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        kofi_btn_box.set_halign(Gtk.Align.CENTER)
        kofi_btn_box.set_valign(Gtk.Align.CENTER)

        # Ko-fi Icon
        kofi_icon_file = project_root / "data" / "icons" / "kofi.png"
        if kofi_icon_file.exists():
            try:
                # Icon has a colormap aspect ratio of ~285x229
                kofi_icon = Gtk.Picture.new_for_filename(str(kofi_icon_file))
                kofi_icon.set_size_request(24, 19)
                kofi_icon.set_valign(Gtk.Align.CENTER)
                kofi_btn_box.append(kofi_icon)
            except Exception as e:
                print(f"[AboutPage] Error loading Ko-fi icon file: {e}")
        else:
            kofi_fallback = Gtk.Image.new_from_icon_name("emblem-favorite-symbolic")
            kofi_btn_box.append(kofi_fallback)

        kofi_lbl = Gtk.Label()
        kofi_lbl.set_markup("<span weight='bold'>Apóyame en Ko-fi</span>")
        kofi_btn_box.append(kofi_lbl)
        kofi_btn.set_child(kofi_btn_box)
        kofi_btn.set_css_classes(["suggested-action", "pill"])
        kofi_btn.set_size_request(200, 38)
        kofi_btn.connect("clicked", lambda b: webbrowser.open("https://ko-fi.com/O5O2PX2PA"))
        buttons_box.append(kofi_btn)

        # ── GitHub Repository Button ──────────────────────────────────────
        github_btn = Gtk.Button()
        github_btn.set_tooltip_text("Ver repositorio del proyecto en GitHub")
        github_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        github_btn_box.set_halign(Gtk.Align.CENTER)
        github_btn_box.set_valign(Gtk.Align.CENTER)

        # GitHub Icon
        github_icon_name = "GitHub_Invertocat_White_Clearspace.svg" if is_dark else "GitHub_Invertocat_Black_Clearspace.svg"
        github_icon_file = project_root / "data" / "icons" / github_icon_name
        if github_icon_file.exists():
            try:
                github_icon = Gtk.Picture.new_for_filename(str(github_icon_file))
                github_icon.set_size_request(20, 20)
                github_icon.set_valign(Gtk.Align.CENTER)
                github_btn_box.append(github_icon)
            except Exception as e:
                print(f"[AboutPage] Error loading GitHub icon: {e}")
        else:
            github_fallback = Gtk.Image.new_from_icon_name("folder-music-symbolic")
            github_btn_box.append(github_fallback)

        github_lbl = Gtk.Label()
        github_lbl.set_markup("<span>Ver en GitHub</span>")
        github_btn_box.append(github_lbl)
        github_btn.set_child(github_btn_box)
        github_btn.set_css_classes(["flat", "pill"])
        github_btn.set_size_request(200, 38)
        github_btn.connect("clicked", lambda b: webbrowser.open("https://github.com/Manuel-Prg/sounware-reproductor"))
        buttons_box.append(github_btn)

        main_box.append(buttons_box)
        group.add(main_box)
