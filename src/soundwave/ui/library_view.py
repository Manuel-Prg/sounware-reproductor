import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, Pango, GLib, Gio

from pathlib import Path
from typing import Optional, Callable

from soundwave.library.database import Database, Song, UNKNOWN_ARTIST, UNKNOWN_ALBUM, NO_GENRE
from soundwave.library.album_art import get_art_path, CACHE_DIR as ART_CACHE_DIR
from soundwave.player.engine import Player, PlayerState
from soundwave.ui.utils import clear_container
from soundwave.ui.library_cards import LibraryCardsMixin
from soundwave.ui.library_playlists import LibraryPlaylistsMixin
from soundwave.ui.library_menus import LibraryMenusMixin


PlaySongCallback = Callable[[Song, list[Song]], None]
QueueSongCallback = Callable[[Song], None]


class LibraryView(Gtk.Box, LibraryCardsMixin, LibraryPlaylistsMixin, LibraryMenusMixin):
    def __init__(self, db: Database, player: Player):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.db = db
        self.player = player
        self._play_song_cbs: list[PlaySongCallback] = []
        self._queue_song_cbs: list[QueueSongCallback] = []
        self._current_song_id: Optional[int] = None
        self._all_songs: list[Song] = []
        self._current_view_id: str = "songs"

        self._header = Adw.HeaderBar()
        self._header.add_css_class("green-deck-header")
        self._title_label = Gtk.Label(label="Todas las canciones")
        self._title_label.set_css_classes(["title"])
        self._header.set_title_widget(self._title_label)

        self._create_playlist_btn = Gtk.Button.new_from_icon_name("list-add-symbolic")
        self._create_playlist_btn.set_tooltip_text("Crear lista de reproducción")
        self._create_playlist_btn.connect("clicked", lambda b: self._on_create_playlist_clicked())
        self._create_playlist_btn.set_visible(False)
        self._header.pack_start(self._create_playlist_btn)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Buscar canciones, artistas...")
        self.search_entry.set_size_request(240, -1)
        self._header.pack_end(self.search_entry)

        self.append(self._header)

        self._stack = Gtk.Stack()
        self._stack.set_vexpand(True)
        self._stack.set_hexpand(True)
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(self._stack)
        self._toast_overlay.set_vexpand(True)
        self._toast_overlay.set_hexpand(True)
        self.append(self._toast_overlay)

        # Views
        self._build_songs_view()
        self._build_albums_view()
        self._build_artists_view()
        self._build_genres_view()
        self._build_search_view()
        self._build_smart_view()
        self._build_playlists_view()
        self._build_visualizer_view()

        self._stack.set_visible_child_name("songs")

    PRESET_RULES = [
        ("Recién Añadido", "Canciones agregadas recientemente", "list-add-symbolic", {"recent": True}),
        ("Favoritos", "Canciones con mejor valoración", "emblem-favorite-symbolic", {"rating_min": 4}),
        ("Más Escuchadas", "Canciones con más reproducciones", "emblem-important-symbolic", {"most_played": True}),
        ("Jazz", "Canciones del género Jazz", "audio-x-generic-symbolic", {"genre": "Jazz"}),
        ("Rock", "Canciones del género Rock", "audio-x-generic-symbolic", {"genre": "Rock"}),
        ("Electrónica", "Canciones del género Electrónica", "audio-x-generic-symbolic", {"genre": "Electronic"}),
    ]

    def _build_songs_view(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)

        self._songs_list = Gtk.ListBox()
        self._songs_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._songs_list.set_css_classes(["songs-list"])
        self._songs_list.connect("row-activated", self._on_song_activated)
        scrolled.set_child(self._songs_list)
        self._stack.add_named(scrolled, "songs")

    def _build_albums_view(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._albums_flow = Gtk.FlowBox()
        self._albums_flow.set_max_children_per_line(6)
        self._albums_flow.set_min_children_per_line(2)
        self._albums_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._albums_flow.set_css_classes(["album-grid"])
        self._albums_flow.set_homogeneous(True)
        self._albums_flow.set_column_spacing(16)
        self._albums_flow.set_row_spacing(16)
        self._albums_flow.set_halign(Gtk.Align.FILL)
        self._albums_flow.set_valign(Gtk.Align.START)
        scrolled.set_child(self._albums_flow)
        self._stack.add_named(scrolled, "albums")

    def _build_artists_view(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._artists_flow = Gtk.FlowBox()
        self._artists_flow.set_max_children_per_line(6)
        self._artists_flow.set_min_children_per_line(2)
        self._artists_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._artists_flow.set_css_classes(["artist-grid"])
        self._artists_flow.set_homogeneous(True)
        self._artists_flow.set_column_spacing(16)
        self._artists_flow.set_row_spacing(16)
        self._artists_flow.set_halign(Gtk.Align.FILL)
        self._artists_flow.set_valign(Gtk.Align.START)
        scrolled.set_child(self._artists_flow)
        self._stack.add_named(scrolled, "artists")

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

    def _build_search_view(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)

        self._search_list = Gtk.ListBox()
        self._search_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._search_list.set_css_classes(["songs-list"])
        self._search_list.connect("row-activated", self._on_song_activated)
        scrolled.set_child(self._search_list)
        self._stack.add_named(scrolled, "search")

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

    def _build_visualizer_view(self):
        from soundwave.ui.visualizer import VisualizerView
        self._visualizer_view = VisualizerView(self.db, self.player)
        self._visualizer_view.connect_play_song(self._on_visualizer_play)
        self._stack.add_named(self._visualizer_view, "visualizer")

    def _on_visualizer_play(self, song: Song, queue: list[Song]):
        for cb in self._play_song_cbs:
            cb(song, queue)

    def _populate_smart(self):
        clear_container(self._smart_flow)
        for name, desc, icon, rules in self.PRESET_RULES:
            # We use an overlay to place a hover play button over the card
            overlay = Gtk.Overlay()
            overlay.add_css_class("smart-card")
            overlay.set_size_request(160, 200)

            # Define a CSS-friendly class for the icon color container
            import re
            css_suffix = re.sub(
                r'[^a-zA-Z0-9-]', '', 
                name.lower().replace(" ", "-").replace("ñ", "n").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
            )
            
            # Content box containing the icon and texts
            card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            card_box.set_margin_start(12)
            card_box.set_margin_end(12)
            card_box.set_margin_top(12)
            card_box.set_margin_bottom(12)
            card_box.set_halign(Gtk.Align.FILL)
            card_box.set_valign(Gtk.Align.FILL)

            # Icon container (square with rounded borders, nicely padded, color background)
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

            # Text container
            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            
            title = Gtk.Label(label=name)
            title.set_css_classes(["smart-card-title"])
            title.set_max_width_chars(16)
            title.set_wrap(True)
            title.set_xalign(0)
            title.set_halign(Gtk.Align.START)
            text_box.append(title)

            subtitle = Gtk.Label(label=desc)
            subtitle.set_css_classes(["smart-card-subtitle"])
            subtitle.set_max_width_chars(18)
            subtitle.set_wrap(True)
            subtitle.set_xalign(0)
            subtitle.set_halign(Gtk.Align.START)
            text_box.append(subtitle)
            
            card_box.append(text_box)
            
            overlay.set_child(card_box)

            # Floating play button overlay (positioned at bottom right, visible on hover)
            play_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
            play_btn.set_css_classes(["smart-play-btn", "circular"])
            play_btn.set_halign(Gtk.Align.END)
            play_btn.set_valign(Gtk.Align.END)
            play_btn.set_size_request(40, 40)
            play_btn.set_margin_end(12)
            play_btn.set_margin_bottom(12)
            play_rules = rules
            play_btn.connect("clicked", lambda b, r=play_rules: self._on_smart_play(r))
            overlay.add_overlay(play_btn)

            # Make card clickable to show songs in detailed view
            card_gesture = Gtk.GestureClick()
            card_gesture.connect("pressed", lambda g, n, x, y, name=name, r=play_rules: self._show_smart_songs(name, r))
            overlay.add_controller(card_gesture)

            self._smart_flow.append(overlay)

    def _show_smart_songs(self, name: str, rules: dict):
        from soundwave.library.smart_playlist import evaluate_rules
        songs = evaluate_rules(self.db, rules)
        self._title_label.set_label(name)
        clear_container(self._songs_list)
        for s in songs:
            r = self._build_song_row(s)
            self._songs_list.append(r)
        self._stack.set_visible_child_name("songs")
        self._all_songs = songs

    def _on_smart_play(self, rules: dict):
        from soundwave.library.smart_playlist import evaluate_rules
        songs = evaluate_rules(self.db, rules)
        if songs:
            for cb in self._play_song_cbs:
                cb(songs[0], songs)

    # --- Public API ---
    def show_view(self, view_id: str):
        if hasattr(self, "_visualizer_view") and view_id != "visualizer":
            self._visualizer_view.on_hide()

        self._current_view_id = view_id
        if hasattr(self, "_create_playlist_btn"):
            self._create_playlist_btn.set_visible(view_id == "playlists")

        self._title_label.set_label({
            "all": "Todas las canciones",
            "albums": "Álbumes",
            "artists": "Artistas",
            "genres": "Géneros",
            "smart": "Listas Inteligentes",
            "playlists": "Listas de reproducción",
            "visualizer": "Visualizador",
        }.get(view_id, "Soundwave"))

        if view_id == "all":
            self._populate_songs()
            self._stack.set_visible_child_name("songs")
        elif view_id == "albums":
            self._populate_albums()
            self._stack.set_visible_child_name("albums")
        elif view_id == "artists":
            self._populate_artists()
            self._stack.set_visible_child_name("artists")
        elif view_id == "genres":
            self._populate_genres()
            self._stack.set_visible_child_name("genres")
        elif view_id == "smart":
            self._populate_smart()
            self._stack.set_visible_child_name("smart")
        elif view_id == "playlists":
            self._populate_playlists()
            self._stack.set_visible_child_name("playlists")
        elif view_id == "visualizer":
            self._visualizer_view.on_show()
            self._stack.set_visible_child_name("visualizer")

    def show_search_results(self, results: list[Song]):
        if hasattr(self, "_visualizer_view"):
            self._visualizer_view.on_hide()
        self._title_label.set_label(f"Resultados: {len(results)}")
        clear_container(self._search_list)
        for song in results:
            row = self._build_song_row(song)
            self._search_list.append(row)
        self._stack.set_visible_child_name("search")

    def refresh(self):
        self._all_songs = self.db.get_all_songs()
        self._populate_songs()
        if self._current_view_id == "playlists":
            self._populate_playlists()

    def highlight_song(self, song: Optional[Song]):
        self._current_song_id = song.id if song else None
        self._update_highlight()

    # --- Populate views ---
    def _populate_songs(self):
        clear_container(self._songs_list)
        self._all_songs = self.db.get_all_songs()
        for i, song in enumerate(self._all_songs):
            row = self._build_song_row(song)
            self._songs_list.append(row)

    def _populate_albums(self):
        clear_container(self._albums_flow)
        albums = self.db.get_albums()
        for album in albums:
            card = self._build_album_card(album)
            self._albums_flow.append(card)

    def _populate_artists(self):
        clear_container(self._artists_flow)
        artists = self.db.get_artists()
        for artist in artists:
            card = self._build_artist_card(artist)
            self._artists_flow.append(card)

    def _populate_genres(self):
        clear_container(self._genres_flow)
        genres = self.db.conn.execute("""
            SELECT 
                CASE WHEN genre = '' OR genre IS NULL THEN 'Sin género' ELSE genre END as genre,
                COUNT(*) as count 
            FROM songs 
            GROUP BY 
                CASE WHEN genre = '' OR genre IS NULL THEN 'Sin género' ELSE genre END 
            ORDER BY genre
        """).fetchall()
        for g in genres:
            card = self._build_genre_card(g)
            self._genres_flow.append(card)

    # --- Widget builders ---
    def _on_song_activated(self, listbox, row):
        song = getattr(row, "_song", None)
        if song is None and hasattr(row, "get_child"):
            c = row.get_child()
            if c:
                song = getattr(c, "_song", None)
        if song is None:
            return
        parent_listbox = listbox
        queue = []
        child = parent_listbox.get_first_child()
        while child:
            s = getattr(child, "_song", None)
            if s is None and hasattr(child, "get_child"):
                c = child.get_child()
                if c:
                    s = getattr(c, "_song", None)
            if s:
                queue.append(s)
            child = child.get_next_sibling()
        if not queue:
            queue = self._all_songs

        for cb in self._play_song_cbs:
            cb(song, queue)

    def _show_album_songs(self, album: dict):
        songs = self.db.get_songs_by_album(album["album"], album.get("album_artist", ""))
        if not songs:
            return
        album_name = album.get("album", UNKNOWN_ALBUM)
        artist_name = album.get("album_artist", "") or songs[0].display_artist
        self._title_label.set_label(f"{album_name}")
        clear_container(self._songs_list)
        for s in songs:
            r = self._build_song_row(s)
            self._songs_list.append(r)
        self._stack.set_visible_child_name("songs")
        self._all_songs = songs

    def _on_album_clicked(self, album: dict):
        self._show_album_songs(album)

    def _on_artist_selected_name(self, artist_name: str):
        songs = self.db.get_songs_by_artist(artist_name)
        if songs:
            self._title_label.set_label(artist_name)
            clear_container(self._songs_list)
            for s in songs:
                r = self._build_song_row(s)
                self._songs_list.append(r)
            self._stack.set_visible_child_name("songs")
            self._all_songs = songs

    def _on_genre_selected(self, genre: str):
        if genre == NO_GENRE:
            songs = [s for s in self.db.get_all_songs() if not s.genre or s.genre.strip() == ""]
        else:
            songs = self.db.search_songs(genre)
        if songs:
            self._title_label.set_label(f"Género: {genre}")
            clear_container(self._songs_list)
            for s in songs:
                r = self._build_song_row(s)
                self._songs_list.append(r)
            self._stack.set_visible_child_name("songs")
            self._all_songs = songs

    def _update_highlight(self):
        for listbox in [self._songs_list, self._search_list]:
            child = listbox.get_first_child()
            while child:
                song = getattr(child, "_song", None)
                if song and song.id == self._current_song_id:
                    listbox.select_row(child)
                    break
                child = child.get_next_sibling()

    # --- Callbacks ---
    def connect_play_song(self, cb: PlaySongCallback):
        self._play_song_cbs.append(cb)

    def connect_queue_song(self, cb: QueueSongCallback):
        self._queue_song_cbs.append(cb)

