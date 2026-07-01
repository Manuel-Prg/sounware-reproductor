"""Mixin: construcción de los scaffolds de vistas en cuadrícula (álbumes, artistas, géneros, visualizador)."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from soundwave.library.database.database import Song


class LibraryGridViewsMixin:
    # ── Albums ────────────────────────────────────────────────────────────

    def _build_albums_view(self):
        self._albums_main_stack = Gtk.Stack()
        self._albums_main_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # FlowBox view (circle / grid)
        scrolled_flow = Gtk.ScrolledWindow()
        scrolled_flow.set_vexpand(True)
        scrolled_flow.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._albums_flow = Gtk.FlowBox()
        self._albums_flow.set_max_children_per_line(6)
        self._albums_flow.set_min_children_per_line(2)
        self._albums_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._albums_flow.set_css_classes(["album-grid"])
        self._albums_flow.set_homogeneous(False)
        self._albums_flow.set_column_spacing(16)
        self._albums_flow.set_row_spacing(16)
        self._albums_flow.set_halign(Gtk.Align.FILL)
        self._albums_flow.set_valign(Gtk.Align.START)
        scrolled_flow.set_child(self._albums_flow)

        # ListBox view (list)
        scrolled_list = Gtk.ScrolledWindow()
        scrolled_list.set_vexpand(True)
        scrolled_list.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._albums_list = Gtk.ListBox()
        self._albums_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._albums_list.set_css_classes(["songs-list"])
        scrolled_list.set_child(self._albums_list)

        self._albums_main_stack.add_named(scrolled_flow, "grid")
        self._albums_main_stack.add_named(scrolled_list, "list")
        self._stack.add_named(self._albums_main_stack, "albums")

    # ── Artists ───────────────────────────────────────────────────────────

    def _build_artists_view(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._artists_flow = Gtk.FlowBox()
        self._artists_flow.set_max_children_per_line(6)
        self._artists_flow.set_min_children_per_line(2)
        self._artists_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._artists_flow.set_css_classes(["artist-grid"])
        self._artists_flow.set_homogeneous(False)
        self._artists_flow.set_column_spacing(16)
        self._artists_flow.set_row_spacing(16)
        self._artists_flow.set_halign(Gtk.Align.FILL)
        self._artists_flow.set_valign(Gtk.Align.START)
        scrolled.set_child(self._artists_flow)
        self._stack.add_named(scrolled, "artists")

    # ── Genres ────────────────────────────────────────────────────────────

    def _build_genres_view(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)

        self._genres_flow = Gtk.FlowBox()
        self._genres_flow.set_max_children_per_line(8)
        self._genres_flow.set_min_children_per_line(3)
        self._genres_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._genres_flow.set_homogeneous(True)
        self._genres_flow.set_column_spacing(12)
        self._genres_flow.set_row_spacing(12)
        self._genres_flow.set_halign(Gtk.Align.FILL)
        self._genres_flow.set_valign(Gtk.Align.START)
        self._genres_flow.add_css_class("genres-grid")
        scrolled.set_child(self._genres_flow)
        self._stack.add_named(scrolled, "genres")

    # ── Visualizer (deferred) ─────────────────────────────────────────────

    def _build_visualizer_view(self):
        """Create a lightweight placeholder; the real visualizer is built on first access."""
        self._visualizer_view = None
        placeholder = Gtk.Label(label="Visualizador")
        placeholder.set_halign(Gtk.Align.CENTER)
        placeholder.set_valign(Gtk.Align.CENTER)
        placeholder.add_css_class("dim-label")
        self._stack.add_named(placeholder, "visualizer")

    def _ensure_visualizer(self):
        """Lazily construct the VisualizerView the first time it is requested."""
        if self._visualizer_view is None:
            from soundwave.ui.visualizer.visualizer import VisualizerView
            self._visualizer_view = VisualizerView(self.db, self.player)
            self._visualizer_view.connect_play_song(self._on_visualizer_play)
            placeholder = self._stack.get_child_by_name("visualizer")
            if placeholder:
                self._stack.remove(placeholder)
            self._stack.add_named(self._visualizer_view, "visualizer")

    def _on_visualizer_play(self, song: Song, queue: list):
        for cb in self._play_song_cbs:
            cb(song, queue)
