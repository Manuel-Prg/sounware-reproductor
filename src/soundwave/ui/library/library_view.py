"""LibraryView — vista principal de la biblioteca musical.

Este archivo es intencionalmente pequeño (~160 líneas).
Toda la lógica de cada sección vive en mixins especializados:

  library_songs_view.py   → ListView virtualizado de canciones + búsqueda
  library_queue_view.py   → Vista y lógica de cola de reproducción
  library_populate.py     → Población de álbumes, artistas, géneros, canciones
  library_smart_view.py   → Listas inteligentes
  library_grid_views.py   → Scaffolds de álbumes/artistas/géneros/visualizador
  library_cards.py        → Tarjetas de álbum y artista
  library_playlists.py    → Playlists de usuario
  library_menus.py        → Menús contextuales de canción
  library_sorting.py      → Ordenamiento
  library_album_details.py→ Vista de detalle de álbum
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from typing import Optional, Callable

from soundwave.library.database.database import Database, Song
from soundwave.player.engine import Player
from soundwave.ui.library.library_songs_view import LibrarySongsViewMixin
from soundwave.ui.library.library_queue_view import LibraryQueueViewMixin
from soundwave.ui.library.library_populate import LibraryPopulateMixin
from soundwave.ui.library.library_smart_view import LibrarySmartViewMixin
from soundwave.ui.library.library_grid_views import LibraryGridViewsMixin
from soundwave.ui.library.library_cards import LibraryCardsMixin
from soundwave.ui.library.library_playlists import LibraryPlaylistsMixin
from soundwave.ui.library.library_menus import LibraryMenusMixin
from soundwave.ui.library.library_sorting import LibrarySortingMixin
from soundwave.ui.library.library_album_details import LibraryAlbumDetailsMixin
from soundwave.ui.library.song_object import SongObject

PlaySongCallback = Callable[[Song, list[Song]], None]
QueueSongCallback = Callable[[Song], None]


class LibraryView(
    Gtk.Box,
    LibrarySongsViewMixin,
    LibraryQueueViewMixin,
    LibraryPopulateMixin,
    LibrarySmartViewMixin,
    LibraryGridViewsMixin,
    LibraryCardsMixin,
    LibraryPlaylistsMixin,
    LibraryMenusMixin,
    LibrarySortingMixin,
    LibraryAlbumDetailsMixin,
):
    def __init__(self, db: Database, player: Player):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.db = db
        self.player = player
        self.player.connect_queue(self._on_player_queue_changed)

        self._play_song_cbs: list[PlaySongCallback] = []
        self._queue_song_cbs: list[QueueSongCallback] = []
        self._current_song_id: Optional[int] = None
        self._all_songs: list[Song] = []
        self._current_view_id: str = "all"

        # Sorting state
        self._song_sort_criteria = "title"
        self._song_sort_order = "asc"
        self._album_sort_criteria = "album"
        self._album_sort_order = "asc"
        self._current_playlist_id = None
        self._dragged_row = None
        self._playlist_pos_cache: dict = {}
        self._playlist_pos_cache_id = None

        # Album view mode
        from soundwave.library.config.config import load_settings
        settings = load_settings()
        self._album_view_mode = settings.get("album_view_mode", "circle")

        self._build_header()
        self._build_stack()

        # Which views need a (re)populate on next access.
        # Queue is exempt — it is always fresh from player state.
        self._views_dirty: set[str] = {
            "all", "albums", "artists", "genres", "smart", "playlists"
        }

        # Defer initial song load so the window can appear first
        GLib.idle_add(self._initial_load)

    # ── Header ────────────────────────────────────────────────────────────

    def _build_header(self):
        self._header = Adw.HeaderBar()
        self._header.add_css_class("green-deck-header")

        self._title_label = Gtk.Label(label="Todas las canciones")
        self._title_label.set_css_classes(["title"])
        self._header.set_title_widget(self._title_label)

        self._back_btn = Gtk.Button.new_from_icon_name("go-previous-symbolic")
        self._back_btn.set_tooltip_text("Volver")
        self._back_btn.connect("clicked", lambda b: self._on_back_clicked())
        self._back_btn.set_visible(False)
        self._header.pack_start(self._back_btn)

        self._create_playlist_btn = Gtk.Button.new_from_icon_name("list-add-symbolic")
        self._create_playlist_btn.set_tooltip_text("Crear lista de reproducción")
        self._create_playlist_btn.connect("clicked", lambda b: self._on_create_playlist_clicked())
        self._create_playlist_btn.set_visible(False)
        self._header.pack_start(self._create_playlist_btn)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Buscar canciones, artistas...")
        self.search_entry.set_size_request(240, -1)
        self._header.pack_end(self.search_entry)

        self._sort_btn = Gtk.MenuButton()
        self._sort_btn.set_icon_name("view-sort-ascending-symbolic")
        self._sort_btn.set_tooltip_text("Ordenar")
        self._sort_popover = Gtk.Popover()
        self._sort_btn.set_popover(self._sort_popover)
        self._header.pack_end(self._sort_btn)

        self._album_view_mode_btn = Gtk.MenuButton()
        self._album_view_mode_btn.set_icon_name("view-grid-symbolic")
        self._album_view_mode_btn.set_tooltip_text("Modo de vista para álbum")
        self._album_view_mode_popover = Gtk.Popover()
        self._album_view_mode_btn.set_popover(self._album_view_mode_popover)
        self._album_view_mode_btn.set_visible(False)
        self._header.pack_end(self._album_view_mode_btn)

        self.append(self._header)

    # ── Main stack ────────────────────────────────────────────────────────

    def _build_stack(self):
        self._stack = Gtk.Stack()
        self._stack.set_vexpand(True)
        self._stack.set_hexpand(True)
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(self._stack)
        self._toast_overlay.set_vexpand(True)
        self._toast_overlay.set_hexpand(True)
        self.append(self._toast_overlay)

        # Build all view scaffolds (no data yet)
        self._build_songs_view()
        self._build_queue_view()
        self._build_albums_view()
        self._build_album_details_view()
        self._build_artists_view()
        self._build_genres_view()
        self._build_search_view()
        self._build_smart_view()
        self._build_playlists_view()
        self._build_visualizer_view()

        self._stack.set_visible_child_name("songs")
        self._update_sort_popover_content()

    # ── Public API ────────────────────────────────────────────────────────

    def connect_play_song(self, cb: PlaySongCallback):
        self._play_song_cbs.append(cb)

    def connect_queue_song(self, cb: QueueSongCallback):
        self._queue_song_cbs.append(cb)

    def show_view(self, view_id: str):
        if self._visualizer_view and view_id != "visualizer":
            self._visualizer_view.on_hide()

        self._current_view_id = view_id
        self._back_btn.set_visible(False)
        self._create_playlist_btn.set_visible(view_id == "playlists")
        self._sort_btn.set_visible(view_id in {"all", "albums", "playlists", "smart"})
        self._album_view_mode_btn.set_visible(view_id == "albums")

        self._title_label.set_label({
            "all":       "Todas las canciones",
            "queue":     "Cola de reproducción",
            "albums":    "Álbumes",
            "artists":   "Artistas",
            "genres":    "Géneros",
            "smart":     "Listas Inteligentes",
            "playlists": "Listas de reproducción",
            "visualizer":"Visualizador",
        }.get(view_id, "Soundwave"))

        # Queue is always live; everything else uses the dirty cache.
        needs_populate = (view_id == "queue") or (view_id in self._views_dirty)

        _populate_map = {
            "all":       (self._populate_songs,    "songs"),
            "albums":    (self._populate_albums,   "albums"),
            "artists":   (self._populate_artists,  "artists"),
            "genres":    (self._populate_genres,   "genres"),
            "smart":     (self._populate_smart,    "smart"),
            "playlists": (self._populate_playlists,"playlists"),
        }

        if view_id == "queue":
            self._populate_queue()
            self._stack.set_visible_child_name("queue")
        elif view_id == "visualizer":
            self._ensure_visualizer()
            if self._visualizer_view:
                self._visualizer_view.on_show()
            self._stack.set_visible_child_name("visualizer")
        elif view_id in _populate_map:
            populate_fn, stack_name = _populate_map[view_id]
            if needs_populate:
                populate_fn()
                self._views_dirty.discard(view_id)
            self._stack.set_visible_child_name(stack_name)

        self._update_sort_popover_content()

    def show_search_results(self, results: list[Song]):
        if self._visualizer_view:
            self._visualizer_view.on_hide()
        self._title_label.set_label(f"Resultados: {len(results)}")
        self._current_playlist_id = None
        self._all_songs = results
        self._sort_songs_list()

        objects = [SongObject(song) for song in self._all_songs]
        self._search_store.splice(0, self._search_store.get_n_items(), objects)

        self._stack.set_visible_child_name("search")
        self._sort_btn.set_visible(True)
        self._update_sort_popover_content()

    def refresh(self):
        """Called after a library scan or file-watcher event.
        Marks all static views dirty and immediately repopulates the current one.
        """
        self._views_dirty = {"all", "albums", "artists", "genres", "smart", "playlists"}
        current = self._current_view_id
        _refresh_map = {
            "all":       self._populate_songs,
            "albums":    self._populate_albums,
            "artists":   self._populate_artists,
            "genres":    self._populate_genres,
            "smart":     self._populate_smart,
            "playlists": self._populate_playlists,
        }
        if current in _refresh_map:
            _refresh_map[current]()
            self._views_dirty.discard(current)

    def highlight_song(self, song: Optional[Song]):
        self._current_song_id = song.id if song else None
        if self._current_view_id == "queue":
            self._populate_queue()
        else:
            self._update_highlight()

    # ── Internal ──────────────────────────────────────────────────────────

    def _initial_load(self) -> bool:
        """Populate the songs view once the main loop is running."""
        self._populate_songs()
        self._views_dirty.discard("all")
        return False

    def _on_back_clicked(self):
        if hasattr(self, "_previous_view_id") and self._previous_view_id:
            self.show_view(self._previous_view_id)

    def _update_highlight(self):
        # Virtualised ListViews
        for store, sel in (
            (self._songs_store,  self._songs_selection),
            (self._search_store, self._search_selection),
        ):
            for i in range(store.get_n_items()):
                obj = store.get_item(i)
                if obj and obj.song.id == self._current_song_id:
                    sel.set_selected(i)
                    break
            else:
                sel.set_selected(Gtk.INVALID_LIST_POSITION)

        # Legacy ListBox in album details
        if hasattr(self, "_album_details_list") and self._album_details_list:
            if self._album_details_list.get_mapped():
                child = self._album_details_list.get_first_child()
                while child:
                    if isinstance(child, Gtk.ListBoxRow) and child.get_parent() == self._album_details_list:
                        if getattr(child, "_song", None) and child._song.id == self._current_song_id:
                            self._album_details_list.select_row(child)
                            break
                    child = child.get_next_sibling()

        # Queue ListBox
        if hasattr(self, "_queue_list") and self._queue_list:
            if self._queue_list.get_mapped():
                curr_idx = self.player.get_current_index()
                child = self._queue_list.get_first_child()
                while child:
                    if isinstance(child, Gtk.ListBoxRow) and child.get_parent() == self._queue_list:
                        # Only try to match index if it's a valid song row (not placeholder which has index but no song)
                        if getattr(child, "_song", None) and child.get_index() == curr_idx:
                            self._queue_list.select_row(child)
                            break
                    child = child.get_next_sibling()
