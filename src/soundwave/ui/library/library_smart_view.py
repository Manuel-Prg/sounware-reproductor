"""Mixin: vistas inteligentes (Smart Playlists / listas predefinidas)."""

import re
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from soundwave.ui.components.utils import clear_container
from soundwave.ui.library.song_object import SongObject

# Preset smart-playlist rules shown in the "Listas Inteligentes" section.
PRESET_RULES = [
    ("Recién Añadido", "Canciones agregadas recientemente", "list-add-symbolic",        {"recent": True}),
    ("Favoritos",      "Canciones con mejor valoración",    "emblem-favorite-symbolic",  {"rating_min": 4}),
    ("Más Escuchadas", "Canciones con más reproducciones",  "emblem-important-symbolic", {"most_played": True}),
]

_NORMALIZE = str.maketrans(
    "áéíóúñÁÉÍÓÚÑ",
    "aeiounAEIOUN",
)


def _css_slug(name: str) -> str:
    normalized = name.translate(_NORMALIZE).lower().replace(" ", "-")
    return re.sub(r"[^a-z0-9-]", "", normalized)


class LibrarySmartViewMixin:
    # Expose the presets so LibraryView can reference them if needed
    PRESET_RULES = PRESET_RULES

    # ── Build ─────────────────────────────────────────────────────────────

    def _build_smart_view(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._smart_flow = Gtk.FlowBox()
        self._smart_flow.set_max_children_per_line(6)
        self._smart_flow.set_min_children_per_line(2)
        self._smart_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._smart_flow.set_homogeneous(True)
        self._smart_flow.set_column_spacing(16)
        self._smart_flow.set_row_spacing(16)
        self._smart_flow.set_halign(Gtk.Align.FILL)
        self._smart_flow.set_valign(Gtk.Align.START)
        self._smart_flow.add_css_class("smart-grid")
        scrolled.set_child(self._smart_flow)
        self._stack.add_named(scrolled, "smart")

    # ── Populate ──────────────────────────────────────────────────────────

    def _populate_smart(self):
        clear_container(self._smart_flow)
        for name, desc, icon, rules in PRESET_RULES:
            self._smart_flow.append(
                self._build_smart_card(name, desc, icon, rules)
            )

    def _build_smart_card(self, name: str, desc: str, icon: str, rules: dict) -> Gtk.Overlay:
        css_suffix = _css_slug(name)

        overlay = Gtk.Overlay()
        overlay.add_css_class("smart-card")
        overlay.set_size_request(160, 200)

        card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        card_box.set_margin_start(12)
        card_box.set_margin_end(12)
        card_box.set_margin_top(12)
        card_box.set_margin_bottom(12)
        card_box.set_halign(Gtk.Align.FILL)
        card_box.set_valign(Gtk.Align.FILL)

        # Coloured icon container
        icon_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        icon_container.add_css_class("smart-icon-container")
        icon_container.add_css_class(f"smart-icon-{css_suffix}")
        icon_container.set_halign(Gtk.Align.START)
        icon_container.set_valign(Gtk.Align.START)
        icon_container.set_size_request(56, 56)

        icon_w = Gtk.Image.new_from_icon_name(icon)
        icon_w.set_pixel_size(24)
        icon_w.set_halign(Gtk.Align.CENTER)
        icon_w.set_valign(Gtk.Align.CENTER)
        icon_w.set_hexpand(True)
        icon_w.set_vexpand(True)
        icon_container.append(icon_w)
        card_box.append(icon_container)

        # Text
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        title_lbl = Gtk.Label(label=name)
        title_lbl.set_css_classes(["smart-card-title"])
        title_lbl.set_max_width_chars(16)
        title_lbl.set_wrap(True)
        title_lbl.set_xalign(0)
        title_lbl.set_halign(Gtk.Align.START)
        text_box.append(title_lbl)

        subtitle_lbl = Gtk.Label(label=desc)
        subtitle_lbl.set_css_classes(["smart-card-subtitle"])
        subtitle_lbl.set_max_width_chars(18)
        subtitle_lbl.set_wrap(True)
        subtitle_lbl.set_xalign(0)
        subtitle_lbl.set_halign(Gtk.Align.START)
        text_box.append(subtitle_lbl)

        card_box.append(text_box)
        overlay.set_child(card_box)

        # Floating play button
        play_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        play_btn.set_css_classes(["smart-play-btn", "circular"])
        play_btn.set_halign(Gtk.Align.END)
        play_btn.set_valign(Gtk.Align.END)
        play_btn.set_size_request(40, 40)
        play_btn.set_margin_end(12)
        play_btn.set_margin_bottom(12)
        play_btn.connect("clicked", lambda b, r=rules: self._on_smart_play(r))
        overlay.add_overlay(play_btn)

        # Click to drill into song list
        gesture = Gtk.GestureClick()
        gesture.connect(
            "pressed",
            lambda g, n, x, y, nm=name, r=rules: self._show_smart_songs(nm, r),
        )
        overlay.add_controller(gesture)

        return overlay

    # ── Actions ───────────────────────────────────────────────────────────

    def _show_smart_songs(self, name: str, rules: dict):
        from soundwave.library.playlists.smart_playlist import evaluate_rules
        songs = evaluate_rules(self.db, rules)

        self._previous_view_id = self._current_view_id
        if hasattr(self, "_back_btn"):
            self._back_btn.set_visible(True)
        self._title_label.set_label(name)

        self._current_playlist_id = None
        self._all_songs = songs
        self._sort_songs_list()

        objects = [SongObject(s) for s in self._all_songs]
        self._songs_store.splice(0, self._songs_store.get_n_items(), objects)

        self._stack.set_visible_child_name("songs")
        if hasattr(self, "_sort_btn"):
            self._sort_btn.set_visible(True)
            self._update_sort_popover_content()

    def _on_smart_play(self, rules: dict):
        from soundwave.library.playlists.smart_playlist import evaluate_rules
        songs = evaluate_rules(self.db, rules)
        if songs:
            for cb in self._play_song_cbs:
                cb(songs[0], songs)
