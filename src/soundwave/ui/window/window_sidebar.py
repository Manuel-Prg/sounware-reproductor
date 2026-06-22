"""Barra lateral de la ventana principal."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw


class WindowSidebarMixin:
    def _build_sidebar(self) -> Gtk.Widget:
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar.set_size_request(220, -1)
        sidebar.add_css_class("navigation-sidebar")

        header = Adw.HeaderBar()
        header.add_css_class("green-deck-header")
        header.set_title_widget(Gtk.Label(label=""))  # Clear center title

        # Pack title label on the left (start)
        title_label = Gtk.Label(label="Soundwave")
        title_label.add_css_class("title")
        title_label.set_halign(Gtk.Align.START)
        title_label.set_margin_start(28)
        header.pack_start(title_label)

        # Pack collapse button first, then settings button, so they sit side-by-side at the end (right side)
        # of the sidebar header, leaving the start (left side) clear for system window controls.
        collapse_btn = Gtk.Button.new_from_icon_name("sidebar-hide-symbolic")
        collapse_btn.set_css_classes(["flat", "circular"])
        collapse_btn.set_tooltip_text("Colapsar barra lateral")
        collapse_btn.connect("clicked", lambda b: self._toggle_sidebar())
        collapse_btn.set_margin_end(12)
        header.pack_end(collapse_btn)

        settings_btn = Gtk.Button.new_from_icon_name("preferences-system-symbolic")
        settings_btn.set_css_classes(["flat", "circular"])
        settings_btn.set_tooltip_text("Ajustes")
        settings_btn.connect("clicked", lambda b: self._on_show_settings())
        header.pack_end(settings_btn)

        sidebar.append(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        sidebar.append(scrolled)

        self._sidebar_list = Gtk.ListBox()
        self._sidebar_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._sidebar_list.set_css_classes(["sidebar-list"])
        scrolled.set_child(self._sidebar_list)

        items = [
            ("audio-x-generic-symbolic", "Todas las canciones", "all"),
            ("media-optical-symbolic", "Álbumes", "albums"),
            ("avatar-default-symbolic", "Artistas", "artists"),
            ("folder-music-symbolic", "Géneros", "genres"),
            ("view-list-symbolic", "Listas Inteligentes", "smart"),
            ("playlist-symbolic", "Listas de reproducción", "playlists"),
        ]
        self._sidebar_count_labels = {}
        for icon_name, label, view_id in items:
            row = Adw.ActionRow()
            row.set_activatable(True)
            row.set_title(label)
            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(18)
            row.add_prefix(icon)
            row.set_css_classes(["sidebar-row"])
            row._view_id = view_id

            # Create a suffix label for the count
            count_label = Gtk.Label()
            count_label.add_css_class("dim-label")
            count_label.set_margin_end(6)
            row.add_suffix(count_label)
            self._sidebar_count_labels[view_id] = count_label

            self._sidebar_list.append(row)

        self._sidebar_list.connect("row-activated", self._on_sidebar_row_activated)

        # Select first
        first = self._sidebar_list.get_row_at_index(0)
        if first:
            self._sidebar_list.select_row(first)
            self._current_view = "all"

        return sidebar

