import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from typing import Callable, Optional

SearchCallback = Callable[[str], None]


class SearchBar(Gtk.SearchBar):
    def __init__(self):
        super().__init__()
        self._search_cbs: list[SearchCallback] = []
        self._search_timer: Optional[int] = None

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        self._entry = Gtk.SearchEntry()
        self._entry.set_hexpand(True)
        self._entry.set_placeholder_text("Buscar canciones, artistas, álbumes...")
        self._entry.connect("search-changed", self._on_search_changed)
        self._entry.connect("activate", self._on_search_activate)
        box.append(self._entry)

        close_btn = Gtk.Button.new_from_icon_name("window-close-symbolic")
        close_btn.set_css_classes(["flat"])
        close_btn.connect("clicked", lambda b: self.clear())
        box.append(close_btn)

        self.set_child(box)
        self.connect_entry(self._entry)

    def _on_search_changed(self, entry):
        if self._search_timer:
            GLib.source_remove(self._search_timer)
        query = entry.get_text().strip()
        self._search_timer = GLib.timeout_add(300, self._do_search, query)

    def _on_search_activate(self, entry):
        query = entry.get_text().strip()
        self._do_search(query)

    def _do_search(self, query: str) -> bool:
        for cb in self._search_cbs:
            cb(query)
        self._search_timer = None
        return False

    def focus(self):
        self.set_search_mode(True)
        self._entry.grab_focus()

    def clear(self):
        self._entry.set_text("")
        self.set_search_mode(False)
        for cb in self._search_cbs:
            cb("")

    def connect_search(self, cb: SearchCallback):
        self._search_cbs.append(cb)
