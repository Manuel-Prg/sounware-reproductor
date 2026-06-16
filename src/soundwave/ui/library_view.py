import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, Pango

from pathlib import Path
from typing import Optional, Callable

from soundwave.library.database import Database, Song
from soundwave.library.album_art import get_art_path
from soundwave.player.engine import Player, PlayerState


PlaySongCallback = Callable[[Song, list[Song]], None]
QueueSongCallback = Callable[[Song], None]


class LibraryView(Gtk.Box):
    def __init__(self, db: Database, player: Player):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.db = db
        self.player = player
        self._play_song_cbs: list[PlaySongCallback] = []
        self._queue_song_cbs: list[QueueSongCallback] = []
        self._current_song_id: Optional[int] = None
        self._all_songs: list[Song] = []

        self._header = Adw.HeaderBar()
        self._title_label = Gtk.Label(label="Todas las canciones")
        self._title_label.set_css_classes(["title"])
        self._header.set_title_widget(self._title_label)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Buscar canciones, artistas...")
        self.search_entry.set_size_request(240, -1)
        self._header.pack_end(self.search_entry)

        self.append(self._header)

        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.append(self._stack)

        # Views
        self._build_songs_view()
        self._build_albums_view()
        self._build_artists_view()
        self._build_genres_view()
        self._build_search_view()

        self._stack.set_visible_child_name("songs")

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

        self._albums_flow = Gtk.FlowBox()
        self._albums_flow.set_max_children_per_line(6)
        self._albums_flow.set_min_children_per_line(2)
        self._albums_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._albums_flow.set_css_classes(["album-grid"])
        self._albums_flow.set_homogeneous(True)
        self._albums_flow.set_column_spacing(12)
        self._albums_flow.set_row_spacing(12)
        self._albums_flow.set_halign(Gtk.Align.FILL)
        scrolled.set_child(self._albums_flow)
        self._stack.add_named(scrolled, "albums")

    def _build_artists_view(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)

        self._artists_list = Gtk.ListBox()
        self._artists_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._artists_list.set_css_classes(["artists-list"])
        self._artists_list.connect("row-activated", self._on_artist_activated)
        scrolled.set_child(self._artists_list)
        self._stack.add_named(scrolled, "artists")

    def _build_genres_view(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)

        self._genres_flow = Gtk.FlowBox()
        self._genres_flow.set_max_children_per_line(8)
        self._genres_flow.set_min_children_per_line(3)
        self._genres_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._genres_flow.set_homogeneous(True)
        self._genres_flow.set_column_spacing(8)
        self._genres_flow.set_row_spacing(8)
        self._genres_flow.set_halign(Gtk.Align.FILL)
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

    # --- Public API ---
    def show_view(self, view_id: str):
        self._title_label.set_label({
            "all": "Todas las canciones",
            "albums": "Álbumes",
            "artists": "Artistas",
            "genres": "Géneros",
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

    def show_search_results(self, results: list[Song]):
        self._title_label.set_label(f"Resultados: {len(results)}")
        while True:
            child = self._search_list.get_first_child()
            if child:
                self._search_list.remove(child)
            else:
                break
        for song in results:
            row = self._build_song_row(song)
            self._search_list.append(row)
        self._stack.set_visible_child_name("search")

    def refresh(self):
        self._all_songs = self.db.get_all_songs()
        self._populate_songs()

    def highlight_song(self, song: Optional[Song]):
        self._current_song_id = song.id if song else None
        self._update_highlight()

    # --- Populate views ---
    def _populate_songs(self):
        while True:
            child = self._songs_list.get_first_child()
            if child:
                self._songs_list.remove(child)
            else:
                break

        self._all_songs = self.db.get_all_songs()
        for i, song in enumerate(self._all_songs):
            row = self._build_song_row(song)
            self._songs_list.append(row)

    def _populate_albums(self):
        while True:
            child = self._albums_flow.get_first_child()
            if child:
                self._albums_flow.remove(child)
            else:
                break

        albums = self.db.get_albums()
        for album in albums:
            card = self._build_album_card(album)
            self._albums_flow.append(card)

    def _populate_artists(self):
        while True:
            child = self._artists_list.get_first_child()
            if child:
                self._artists_list.remove(child)
            else:
                break

        artists = self.db.get_artists()
        for artist in artists:
            row = Adw.ActionRow()
            row.set_title(artist["artist"])
            row.set_subtitle(f"{artist['album_count']} álbumes · {artist['song_count']} canciones")
            row._artist_name = artist["artist"]
            self._artists_list.append(row)

    def _populate_genres(self):
        while True:
            child = self._genres_flow.get_first_child()
            if child:
                self._genres_flow.remove(child)
            else:
                break

        genres = self.db.conn.execute(
            "SELECT genre, COUNT(*) as count FROM songs WHERE genre != '' GROUP BY genre ORDER BY genre"
        ).fetchall()
        for g in genres:
            btn = Gtk.Button(label=f"{g['genre']}\n{g['count']} canciones")
            btn.set_css_classes(["genre-button"])
            btn.set_halign(Gtk.Align.FILL)
            btn.set_size_request(120, 80)
            btn._genre = g["genre"]
            btn.connect("clicked", self._on_genre_clicked)
            self._genres_flow.append(btn)

    # --- Widget builders ---
    def _build_song_row(self, song: Song) -> Adw.ActionRow:
        row = Adw.ActionRow()
        row.set_title(song.display_title)
        row.set_subtitle(f"{song.display_artist} · {song.display_album}")
        if song.duration:
            m, s = divmod(int(song.duration), 60)
            row.add_suffix(Gtk.Label(label=f"{m}:{s:02d}"))

        row._song = song
        return row

    def _build_album_card(self, album: dict) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_size_request(160, 220)
        box.add_css_class("album-card")

        # Overlay for cover art + play button
        overlay = Gtk.Overlay()

        picture = Gtk.Picture()
        picture.set_size_request(160, 160)
        picture.set_content_fit(Gtk.ContentFit.COVER)
        picture.set_css_classes(["album-cover"])

        # Try to find art for this album
        songs = self.db.get_songs_by_album(album["album"], album.get("album_artist", ""))
        art_found = False
        for s in songs:
            art_path = get_art_path(s.id, self.db)
            if art_path and art_path.exists():
                texture = Gdk.Texture.new_from_filename(str(art_path))
                picture.set_paintable(texture)
                art_found = True
                break

        if not art_found:
            picture.set_paintable(None)

        overlay.set_child(picture)

        # Floating Play Button
        play_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        play_btn.set_css_classes(["play-button-card", "circular"])
        play_btn.set_halign(Gtk.Align.END)
        play_btn.set_valign(Gtk.Align.END)
        play_btn.set_margin_end(8)
        play_btn.set_margin_bottom(8)
        play_btn.set_size_request(36, 36)
        play_btn.connect("clicked", lambda b, a=album: self._on_album_clicked(a))
        overlay.add_overlay(play_btn)

        box.append(overlay)

        # Title
        title = Gtk.Label(label=album["album"])
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.set_max_width_chars(18)
        title.set_xalign(0)
        title.add_css_class("heading")
        box.append(title)

        # Subtitle
        subtitle = Gtk.Label(label=album.get("album_artist", "") or "Varios artistas")
        subtitle.set_ellipsize(Pango.EllipsizeMode.END)
        subtitle.set_max_width_chars(18)
        subtitle.set_xalign(0)
        subtitle.add_css_class("caption")
        box.append(subtitle)

        # Click handler - play album (double click or general card click)
        gesture = Gtk.GestureClick()
        gesture.connect("pressed", lambda g, n, x, y, a=album: self._on_album_clicked(a))
        box.add_controller(gesture)

        return box

    # --- Event handlers ---
    def _on_song_activated(self, listbox, row):
        song = getattr(row, "_song", None)
        if song is None:
            return
        parent_listbox = listbox
        queue = []
        child = parent_listbox.get_first_child()
        while child:
            s = getattr(child, "_song", None)
            if s:
                queue.append(s)
            child = child.get_next_sibling()
        if not queue:
            queue = self._all_songs

        for cb in self._play_song_cbs:
            cb(song, queue)

    def _on_album_clicked(self, album: dict):
        songs = self.db.get_songs_by_album(album["album"], album.get("album_artist", ""))
        if songs:
            for cb in self._play_song_cbs:
                cb(songs[0], songs)

    def _on_artist_activated(self, listbox, row):
        artist_name = getattr(row, "_artist_name", "")
        songs = self.db.get_songs_by_artist(artist_name)
        if songs:
            self._title_label.set_label(artist_name)
            while True:
                child = self._songs_list.get_first_child()
                if child:
                    self._songs_list.remove(child)
                else:
                    break
            for s in songs:
                r = self._build_song_row(s)
                self._songs_list.append(r)
            self._stack.set_visible_child_name("songs")
            self._all_songs = songs

    def _on_genre_clicked(self, button):
        genre = getattr(button, "_genre", "")
        songs = self.db.search_songs(genre)
        if songs:
            self._title_label.set_label(f"Género: {genre}")
            while True:
                child = self._songs_list.get_first_child()
                if child:
                    self._songs_list.remove(child)
                else:
                    break
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
