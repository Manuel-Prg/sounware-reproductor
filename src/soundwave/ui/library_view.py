import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, Pango, GLib

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
        self._header.add_css_class("green-deck-header")
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
        self._build_smart_view()

        self._stack.set_visible_child_name("songs")

    PRESET_RULES = [
        ("Recién Añadido", "Canciones agregadas recientemente", "list-add-symbolic", {"year_min": 2024}),
        ("Favoritos", "Canciones con mejor valoración", "emblem-favorite-symbolic", {"rating_min": 4}),
        ("Más Escuchadas", "Canciones con más reproducciones", "emblem-important-symbolic", {"play_count_min": 10}),
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
        scrolled.set_child(self._smart_flow)
        self._stack.add_named(scrolled, "smart")

    def _populate_smart(self):
        while True:
            child = self._smart_flow.get_first_child()
            if child:
                self._smart_flow.remove(child)
            else:
                break
        for name, desc, icon, rules in self.PRESET_RULES:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            card.set_css_classes(["smart-card"])
            card.set_size_request(-1, 120)
            card.set_halign(Gtk.Align.FILL)
            card.set_valign(Gtk.Align.FILL)

            icon_w = Gtk.Image.new_from_icon_name(icon)
            icon_w.set_pixel_size(32)
            icon_w.set_margin_top(16)
            card.append(icon_w)

            title = Gtk.Label(label=name)
            title.set_css_classes(["card-title"])
            title.set_max_width_chars(16)
            title.set_wrap(True)
            title.set_halign(Gtk.Align.CENTER)
            card.append(title)

            subtitle = Gtk.Label(label=desc)
            subtitle.set_css_classes(["dim-label", "card-subtitle"])
            subtitle.set_max_width_chars(16)
            subtitle.set_wrap(True)
            subtitle.set_halign(Gtk.Align.CENTER)
            card.append(subtitle)

            spacer = Gtk.Label()
            spacer.set_vexpand(True)
            card.append(spacer)

            play_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
            play_btn.set_css_classes(["circular", "play-pulse"])
            play_btn.set_halign(Gtk.Align.CENTER)
            play_btn.set_valign(Gtk.Align.CENTER)
            play_btn.set_margin_bottom(12)
            play_rules = rules
            play_btn.connect("clicked", lambda b, r=play_rules: self._on_smart_play(r))
            card.append(play_btn)

            self._smart_flow.append(card)

    def _on_smart_play(self, rules: dict):
        from soundwave.library.smart_playlist import evaluate_rules
        songs = evaluate_rules(self.db, rules)
        if songs:
            for cb in self._play_song_cbs:
                cb(songs[0], songs)

    # --- Public API ---
    def show_view(self, view_id: str):
        self._title_label.set_label({
            "all": "Todas las canciones",
            "albums": "Álbumes",
            "artists": "Artistas",
            "genres": "Géneros",
            "smart": "Listas Inteligentes",
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
            child = self._artists_flow.get_first_child()
            if child:
                self._artists_flow.remove(child)
            else:
                break

        artists = self.db.get_artists()
        for artist in artists:
            card = self._build_artist_card(artist)
            self._artists_flow.append(card)

    def _populate_genres(self):
        while True:
            child = self._genres_flow.get_first_child()
            if child:
                self._genres_flow.remove(child)
            else:
                break

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
    def _build_song_row(self, song: Song) -> Adw.ActionRow:
        row = Adw.ActionRow()
        row.set_activatable(True)
        row.set_title(GLib.markup_escape_text(song.display_title))
        row.set_subtitle(GLib.markup_escape_text(f"{song.display_artist} · {song.display_album}"))
        if song.duration:
            m, s = divmod(int(song.duration), 60)
            row.add_suffix(Gtk.Label(label=f"{m}:{s:02d}"))

        row._song = song
        return row

    def _build_album_card(self, album: dict) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_size_request(140, -1)
        box.add_css_class("album-card")

        overlay = Gtk.Overlay()

        # Try to find art for this album
        songs = self.db.get_songs_by_album(album["album"], album.get("album_artist", ""))
        art_texture = None
        for s in songs:
            art_path = get_art_path(s.id, self.db)
            if art_path and art_path.exists():
                art_texture = Gdk.Texture.new_from_filename(str(art_path))
                break

        avatar = Adw.Avatar(size=120, text=album["album"], show_initials=True)
        if art_texture:
            avatar.set_custom_image(art_texture)

        avatar.set_halign(Gtk.Align.CENTER)
        overlay.set_child(avatar)

        # Floating Play Button in the center (visible on hover)
        play_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        play_btn.set_css_classes(["album-play-btn", "circular"])
        play_btn.set_halign(Gtk.Align.CENTER)
        play_btn.set_valign(Gtk.Align.CENTER)
        play_btn.set_size_request(44, 44)
        album_songs = songs
        play_btn.connect("clicked", lambda b, a=album, s=album_songs: (
            s and [cb(s[0], s) for cb in self._play_song_cbs]
        ))
        overlay.add_overlay(play_btn)

        box.append(overlay)

        # Title
        title = Gtk.Label(label=album["album"])
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.set_max_width_chars(16)
        title.set_xalign(0.5)
        title.add_css_class("album-card-title")
        box.append(title)

        # Subtitle (Artist)
        artist_name = album.get("album_artist", "") or "Artista desconocido"
        artist = Gtk.Label(label=artist_name)
        artist.set_ellipsize(Pango.EllipsizeMode.END)
        artist.set_max_width_chars(18)
        artist.set_xalign(0.5)
        artist.add_css_class("album-card-subtitle")
        box.append(artist)

        # Click handler - play album
        gesture = Gtk.GestureClick()
        gesture.connect("pressed", lambda g, n, x, y, a=album: self._on_album_clicked(a))
        box.add_controller(gesture)

        return box

    def _build_artist_card(self, artist: dict) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.set_size_request(140, -1)
        card.add_css_class("artist-card")

        # Let's find an album cover to use as the artist's avatar image
        songs = self.db.get_songs_by_artist(artist["artist"])
        art_texture = None
        for s in songs:
            art_path = get_art_path(s.id, self.db)
            if art_path and art_path.exists():
                art_texture = Gdk.Texture.new_from_filename(str(art_path))
                break

        avatar = Adw.Avatar(size=120, text=artist["artist"], show_initials=True)
        if art_texture:
            avatar.set_custom_image(art_texture)

        avatar.set_halign(Gtk.Align.CENTER)
        card.append(avatar)

        # Name
        name = Gtk.Label(label=artist["artist"])
        name.set_ellipsize(Pango.EllipsizeMode.END)
        name.set_max_width_chars(16)
        name.set_xalign(0.5)
        name.add_css_class("artist-card-name")
        card.append(name)

        # Subtitle
        subtitle_text = f"{artist['album_count']} álb. · {artist['song_count']} canc."
        subtitle = Gtk.Label(label=subtitle_text)
        subtitle.set_ellipsize(Pango.EllipsizeMode.END)
        subtitle.set_max_width_chars(18)
        subtitle.set_xalign(0.5)
        subtitle.add_css_class("artist-card-subtitle")
        card.append(subtitle)

        # Click gesture to open artist's songs
        gesture = Gtk.GestureClick()
        gesture.connect("pressed", lambda g, n, x, y, name=artist["artist"]: self._on_artist_selected_name(name))
        card.add_controller(gesture)

        return card

    def _build_genre_card(self, g: dict) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.set_size_request(140, -1)
        card.add_css_class("genre-card")

        # Icon box
        icon_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        icon_box.set_halign(Gtk.Align.START)
        icon_box.add_css_class("genre-icon-box")
        
        icon = Gtk.Image.new_from_icon_name("folder-music-symbolic")
        icon.set_pixel_size(24)
        icon_box.append(icon)
        card.append(icon_box)

        # Genre Name
        name_label = Gtk.Label(label=g["genre"])
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_max_width_chars(16)
        name_label.set_xalign(0)
        name_label.add_css_class("genre-name")
        card.append(name_label)

        # Song Count
        count_label = Gtk.Label(label=f"{g['count']} canciones")
        count_label.set_xalign(0)
        count_label.add_css_class("genre-count")
        card.append(count_label)

        # Click handler
        gesture = Gtk.GestureClick()
        gesture.connect("pressed", lambda gesture, n_press, x, y, name=g["genre"]: self._on_genre_selected(name))
        card.add_controller(gesture)

        return card

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

    def _show_album_songs(self, album: dict):
        songs = self.db.get_songs_by_album(album["album"], album.get("album_artist", ""))
        if not songs:
            return
        album_name = album.get("album", "Álbum desconocido")
        artist_name = album.get("album_artist", "") or songs[0].display_artist
        self._title_label.set_label(f"{album_name}")
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

    def _on_album_clicked(self, album: dict):
        self._show_album_songs(album)

    def _on_artist_selected_name(self, artist_name: str):
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

    def _on_genre_selected(self, genre: str):
        if genre == "Sin género":
            songs = [s for s in self.db.get_all_songs() if not s.genre or s.genre.strip() == ""]
        else:
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
