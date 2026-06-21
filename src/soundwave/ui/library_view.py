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


PlaySongCallback = Callable[[Song, list[Song]], None]
QueueSongCallback = Callable[[Song], None]


class CreatePlaylistDialog(Gtk.Window):
    def __init__(self, parent_window, callback):
        super().__init__(transient_for=parent_window, modal=True)
        self.set_title("Nueva Lista de Reproducción")
        self.set_default_size(300, 150)
        self.callback = callback

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)

        label = Gtk.Label(label="Introduce el nombre de la lista:")
        label.set_halign(Gtk.Align.START)
        box.append(label)

        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Mi lista de reproducción")
        self.entry.connect("activate", lambda e: self._on_create())
        box.append(self.entry)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="Cancelar")
        cancel_btn.connect("clicked", lambda b: self.destroy())
        btn_box.append(cancel_btn)

        self.create_btn = Gtk.Button(label="Crear")
        self.create_btn.add_css_class("suggested-action")
        self.create_btn.connect("clicked", lambda b: self._on_create())
        btn_box.append(self.create_btn)

        box.append(btn_box)
        self.set_child(box)

    def _on_create(self):
        name = self.entry.get_text().strip()
        if name:
            self.callback(name)
            self.destroy()


class LibraryView(Gtk.Box):
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
    def _build_song_row(self, song: Song, playlist_id: Optional[int] = None) -> Adw.ActionRow:
        row = Adw.ActionRow()
        row.set_activatable(True)
        row.set_title(GLib.markup_escape_text(song.display_title))
        row.set_subtitle(GLib.markup_escape_text(f"{song.display_artist} · {song.display_album}"))
        
        # Add Favorite toggle button
        fav_btn = Gtk.Button.new_from_icon_name("emblem-favorite-symbolic")
        fav_btn.set_valign(Gtk.Align.CENTER)
        fav_btn.set_css_classes(["flat", "circular"])
        
        if song.rating >= 4:
            fav_btn.add_css_class("song-fav-active")
        else:
            fav_btn.add_css_class("song-fav-inactive")
            
        def on_fav_clicked(btn, s=song):
            if s.rating >= 4:
                self.db.update_rating(s.id, 0)
                s.rating = 0
                btn.remove_css_class("song-fav-active")
                btn.add_css_class("song-fav-inactive")
            else:
                self.db.update_rating(s.id, 5)
                s.rating = 5
                btn.remove_css_class("song-fav-inactive")
                btn.add_css_class("song-fav-active")
                
        fav_btn.connect("clicked", on_fav_clicked)
        row.add_suffix(fav_btn)

        # Context menu button for other actions (Add to playlist, etc)
        menu_btn = Gtk.Button.new_from_icon_name("view-more-symbolic")
        menu_btn.set_valign(Gtk.Align.CENTER)
        menu_btn.set_css_classes(["flat", "circular"])
        menu_btn.set_tooltip_text("Más opciones")
        menu_btn.connect("clicked", lambda b, s=song: self._show_song_menu(b, s))
        row.add_suffix(menu_btn)

        # If we are viewing inside a custom playlist, add a "remove from playlist" button
        if playlist_id is not None:
            remove_btn = Gtk.Button.new_from_icon_name("list-remove-symbolic")
            remove_btn.set_valign(Gtk.Align.CENTER)
            remove_btn.set_css_classes(["flat", "circular"])
            remove_btn.set_tooltip_text("Quitar de esta lista")
            
            def on_remove_clicked(btn, pid=playlist_id, sid=song.id):
                self.db.remove_from_playlist(pid, sid)
                toast = Adw.Toast.new("Canción quitada de la lista")
                self.add_toast(toast)
                # Re-fetch updated playlist and refresh view
                updated_pl = None
                for pl in self.db.get_playlists():
                    if pl.id == pid:
                        updated_pl = pl
                        break
                if updated_pl:
                    self._show_playlist_songs(updated_pl)
                else:
                    self.show_view("playlists")
                    
            remove_btn.connect("clicked", on_remove_clicked)
            row.add_suffix(remove_btn)

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

        # Try to find art for this album (check cache first, then DB)
        songs = self.db.get_songs_by_album(album["album"], album.get("album_artist", ""))
        art_texture = None
        for s in songs:
            for ext in (".jpg", ".png"):
                cached = ART_CACHE_DIR / f"{s.id}{ext}"
                if cached.exists():
                    art_texture = Gdk.Texture.new_from_filename(str(cached))
                    break
            if art_texture:
                break
        if not art_texture:
            for s in songs:
                art_path = get_art_path(s.id, self.db) if s.id is not None else None
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
        artist_name = album.get("album_artist", "") or UNKNOWN_ARTIST
        artist = Gtk.Label(label=artist_name)
        artist.set_ellipsize(Pango.EllipsizeMode.END)
        artist.set_max_width_chars(18)
        artist.set_xalign(0.5)
        artist.add_css_class("album-card-subtitle")
        box.append(artist)

        # Click handler - play album (left click) or context menu (right click)
        gesture = Gtk.GestureClick()
        gesture.set_button(0)  # Listen to all mouse buttons
        gesture.connect("pressed", lambda g, n, x, y, a=album: self._on_album_card_pressed(g, n, x, y, a))
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
            art_path = get_art_path(s.id, self.db) if s.id is not None else None
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

    def _build_genre_card(self, g: dict) -> Gtk.Widget:
        import hashlib
        
        # Gtk.Overlay allows us to overlay text on top of a background image/icon
        overlay = Gtk.Overlay()
        overlay.add_css_class("genre-card")
        
        # Calculate a stable hash based on the genre name to pick a gradient index (0-7)
        genre_name = g["genre"]
        genre_hash = int(hashlib.md5(genre_name.encode("utf-8")).hexdigest(), 16)
        gradient_idx = genre_hash % 8
        
        if genre_name == NO_GENRE or genre_name == "Sin género":
            overlay.add_css_class("genre-card-no-genre")
        else:
            overlay.add_css_class(f"genre-card-grad-{gradient_idx}")
            
        overlay.set_size_request(160, 110)
        
        # Decorative semi-transparent icon in the bottom right corner
        icon = Gtk.Image.new_from_icon_name("folder-music-symbolic")
        icon.set_pixel_size(64)
        icon.set_halign(Gtk.Align.END)
        icon.set_valign(Gtk.Align.END)
        icon.add_css_class("genre-card-bg-icon")
        overlay.add_overlay(icon)
        
        # Vertical Box to hold titles with proper margins
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_valign(Gtk.Align.FILL)
        
        # Genre Name (Bold, white/contrasted, with custom css class)
        name_label = Gtk.Label(label=genre_name)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_max_width_chars(14)
        name_label.set_xalign(0)
        name_label.add_css_class("genre-card-name")
        content.append(name_label)

        # Song Count (Smaller, semi-transparent label)
        count_label = Gtk.Label(label=f"{g['count']} canciones")
        count_label.set_xalign(0)
        count_label.add_css_class("genre-card-count")
        content.append(count_label)
        
        overlay.set_child(content)

        # Click handler
        gesture = Gtk.GestureClick()
        gesture.connect("pressed", lambda gesture, n_press, x, y, name=genre_name: self._on_genre_selected(name))
        overlay.add_controller(gesture)

        return overlay

    # --- Event handlers ---
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

    def _on_album_card_pressed(self, gesture, n_press, x, y, album):
        button = gesture.get_current_button()
        if button == 1:  # Left click
            self._on_album_clicked(album)
        elif button == 3:  # Right click
            self._show_album_context_menu(gesture, album)

    def _show_album_context_menu(self, gesture, album):
        popover = Gtk.Popover()
        popover.set_parent(gesture.get_widget())

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        
        play_btn = Gtk.Button(label="Reproducir álbum")
        play_btn.set_has_frame(False)
        play_btn.set_halign(Gtk.Align.START)
        play_btn.connect("clicked", lambda b: (popover.popdown(), self._on_album_clicked(album)))
        box.append(play_btn)

        change_cover_btn = Gtk.Button(label="Cambiar carátula...")
        change_cover_btn.set_has_frame(False)
        change_cover_btn.set_halign(Gtk.Align.START)
        change_cover_btn.connect("clicked", lambda b: (popover.popdown(), self._prompt_custom_cover(album)))
        box.append(change_cover_btn)

        popover.set_child(box)
        popover.popup()

    def _prompt_custom_cover(self, album):
        if hasattr(Gtk, "FileDialog"):
            dialog = Gtk.FileDialog.new()
            dialog.set_title("Seleccionar carátula para el álbum")
            
            filter_img = Gtk.FileFilter()
            filter_img.set_name("Imágenes")
            filter_img.add_mime_type("image/jpeg")
            filter_img.add_mime_type("image/png")
            
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(filter_img)
            dialog.set_filters(filters)

            def on_file_selected(dialog, result, *args):
                try:
                    file = dialog.open_finish(result)
                    if file:
                        self._apply_custom_cover(album, Path(file.get_path()))
                except GLib.Error as e:
                    print("Selección de carátula cancelada o fallida:", e)
            dialog.open(self.get_root(), None, on_file_selected)
        else:
            dialog = Gtk.FileChooserNative.new(
                title="Seleccionar carátula para el álbum",
                parent=self.get_root(),
                action=Gtk.FileChooserAction.OPEN,
                accept_label="Seleccionar",
                cancel_label="Cancelar"
            )
            filter_img = Gtk.FileFilter()
            filter_img.set_name("Imágenes")
            filter_img.add_mime_type("image/jpeg")
            filter_img.add_mime_type("image/png")
            dialog.add_filter(filter_img)

            self._file_chooser = dialog
            def on_response(dialog, response_id):
                if response_id == Gtk.ResponseType.ACCEPT:
                    file = dialog.get_file()
                    if file:
                        self._apply_custom_cover(album, Path(file.get_path()))
                self._file_chooser = None
            dialog.connect("response", on_response)
            dialog.show()

    def _apply_custom_cover(self, album, file_path: Path):
        try:
            img_bytes = file_path.read_bytes()
            songs = self.db.get_songs_by_album(album["album"], album.get("album_artist", ""))
            if not songs:
                return

            ART_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            for s in songs:
                if s.id is not None:
                    cache_path = ART_CACHE_DIR / f"{s.id}.jpg"
                    cache_path.write_bytes(img_bytes)
                    from soundwave.library.album_art import _export_art_to_tmp
                    _export_art_to_tmp(s.id, cache_path)

            first_song_path = Path(songs[0].filepath)
            album_dir = first_song_path.parent
            if album_dir.exists():
                local_cover = album_dir / "cover.jpg"
                try:
                    local_cover.write_bytes(img_bytes)
                except Exception as e:
                    print(f"No se pudo guardar la carátula local en {album_dir}: {e}")

            self._populate_albums()

            root = self.get_root()
            if root and hasattr(root, "add_toast"):
                root.add_toast("Carátula aplicada al álbum correctamente")
                
            # If current playing song is in this album, update art
            if self.player.current_song:
                curr = self.player.current_song
                if curr.album == album["album"]:
                    if root and hasattr(root, "refresh_current_artwork"):
                        root.refresh_current_artwork()
        except Exception as e:
            print(f"Error al aplicar la carátula personalizada: {e}")

    # --- Playlist Support ---
    def add_toast(self, toast):
        self._toast_overlay.add_toast(toast)

    def _show_song_menu(self, btn, song):
        popover = Gtk.Popover()
        popover.set_parent(btn)
        popover.set_has_arrow(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        title_label = Gtk.Label(label="Agregar a lista:")
        title_label.set_halign(Gtk.Align.START)
        title_label.set_css_classes(["dim-label"])
        title_label.set_margin_bottom(4)
        box.append(title_label)

        playlists = self.db.get_playlists()
        if playlists:
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroll.set_max_content_height(150)
            scroll.set_propagate_natural_height(True)
            
            pl_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            for pl in playlists:
                pl_btn = Gtk.Button()
                pl_btn.set_halign(Gtk.Align.FILL)
                pl_btn.set_css_classes(["flat"])
                
                pl_label = Gtk.Label(label=pl.name)
                pl_label.set_xalign(0.0)
                pl_btn.set_child(pl_label)
                
                if song.id in pl.song_ids:
                    pl_btn.set_sensitive(False)
                    pl_btn.set_tooltip_text("Ya está en esta lista")
                    
                def on_pl_clicked(b, playlist_id=pl.id, playlist_name=pl.name):
                    self.db.add_to_playlist(playlist_id, song.id)
                    toast = Adw.Toast.new(f"Añadida a '{playlist_name}'")
                    self.add_toast(toast)
                    popover.popdown()
                    
                pl_btn.connect("clicked", on_pl_clicked)
                pl_box.append(pl_btn)
            
            scroll.set_child(pl_box)
            box.append(scroll)
        else:
            no_pl_label = Gtk.Label(label="No hay listas creadas")
            no_pl_label.set_halign(Gtk.Align.START)
            no_pl_label.set_margin_bottom(4)
            no_pl_label.add_css_class("dim-label")
            box.append(no_pl_label)

        sep = Gtk.Separator()
        sep.set_margin_top(4)
        sep.set_margin_bottom(4)
        box.append(sep)

        new_pl_btn = Gtk.Button()
        new_pl_btn.set_halign(Gtk.Align.FILL)
        new_pl_btn.set_css_classes(["flat"])
        
        new_pl_label = Gtk.Label(label="Nueva lista...")
        new_pl_label.set_xalign(0.0)
        new_pl_btn.set_child(new_pl_label)
        
        def on_new_pl_clicked(b):
            popover.popdown()
            dialog = CreatePlaylistDialog(self.get_native(), lambda name: self._create_playlist_and_add_song(name, song.id))
            dialog.present()
            
        new_pl_btn.connect("clicked", on_new_pl_clicked)
        box.append(new_pl_btn)

        popover.set_child(box)
        popover.popup()

    def _create_playlist_and_add_song(self, name: str, song_id: int):
        playlist_id = self.db.create_playlist(name)
        self.db.add_to_playlist(playlist_id, song_id)
        toast = Adw.Toast.new(f"Lista '{name}' creada y canción añadida")
        self.add_toast(toast)
        if self._current_view_id == "playlists":
            self._populate_playlists()
        # Also refresh sidebar counts since we added a playlist
        root = self.get_native()
        if root and hasattr(root, "_refresh_sidebar_counts"):
            root._refresh_sidebar_counts()

    def _on_create_playlist_clicked(self):
        def on_created(name):
            self.db.create_playlist(name)
            toast = Adw.Toast.new(f"Lista '{name}' creada")
            self.add_toast(toast)
            self._populate_playlists()
            # Also refresh sidebar counts since we added a playlist
            root = self.get_native()
            if root and hasattr(root, "_refresh_sidebar_counts"):
                root._refresh_sidebar_counts()
            
        dialog = CreatePlaylistDialog(self.get_native(), on_created)
        dialog.present()

    def _build_playlists_view(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._playlists_flow = Gtk.FlowBox()
        self._playlists_flow.set_max_children_per_line(6)
        self._playlists_flow.set_min_children_per_line(2)
        self._playlists_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._playlists_flow.set_homogeneous(True)
        self._playlists_flow.set_column_spacing(16)
        self._playlists_flow.set_row_spacing(16)
        self._playlists_flow.set_halign(Gtk.Align.FILL)
        self._playlists_flow.set_valign(Gtk.Align.START)
        self._playlists_flow.add_css_class("playlists-grid")
        scrolled.set_child(self._playlists_flow)
        self._stack.add_named(scrolled, "playlists")

    def _populate_playlists(self):
        clear_container(self._playlists_flow)
        playlists = self.db.get_playlists()
        
        for pl in playlists:
            overlay = Gtk.Overlay()
            overlay.add_css_class("playlist-card")
            overlay.set_size_request(160, 200)

            import hashlib
            h = hashlib.md5(pl.name.encode('utf-8')).hexdigest()
            color_index = int(h, 16) % 8
            
            card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            card_box.set_margin_start(12)
            card_box.set_margin_end(12)
            card_box.set_margin_top(12)
            card_box.set_margin_bottom(12)
            card_box.set_halign(Gtk.Align.FILL)
            card_box.set_valign(Gtk.Align.FILL)

            icon_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            icon_container.add_css_class("playlist-icon-container")
            icon_container.add_css_class(f"playlist-icon-grad-{color_index}")
            icon_container.set_halign(Gtk.Align.START)
            icon_container.set_valign(Gtk.Align.START)
            icon_container.set_size_request(56, 56)
            
            icon_w = Gtk.Image.new_from_icon_name("playlist-symbolic")
            icon_w.set_pixel_size(24)
            icon_w.set_halign(Gtk.Align.CENTER)
            icon_w.set_valign(Gtk.Align.CENTER)
            icon_w.set_hexpand(True)
            icon_w.set_vexpand(True)
            icon_container.append(icon_w)
            
            card_box.append(icon_container)

            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            
            title = Gtk.Label(label=pl.name)
            title.set_css_classes(["playlist-card-title"])
            title.set_max_width_chars(16)
            title.set_wrap(True)
            title.set_xalign(0)
            title.set_halign(Gtk.Align.START)
            text_box.append(title)

            num_songs = len(pl.song_ids)
            desc_text = f"{num_songs} canción" if num_songs == 1 else f"{num_songs} canciones"
            subtitle = Gtk.Label(label=desc_text)
            subtitle.set_css_classes(["playlist-card-subtitle"])
            subtitle.set_max_width_chars(18)
            subtitle.set_wrap(True)
            subtitle.set_xalign(0)
            subtitle.set_halign(Gtk.Align.START)
            text_box.append(subtitle)
            
            card_box.append(text_box)
            overlay.set_child(card_box)

            btns_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            btns_box.set_halign(Gtk.Align.END)
            btns_box.set_valign(Gtk.Align.END)
            btns_box.set_margin_end(12)
            btns_box.set_margin_bottom(12)

            delete_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
            delete_btn.set_css_classes(["playlist-action-btn", "playlist-delete-btn", "circular"])
            delete_btn.set_size_request(36, 36)
            delete_btn.set_tooltip_text("Eliminar lista")
            
            def on_delete_clicked(b, playlist_id=pl.id, playlist_name=pl.name):
                self.db.delete_playlist(playlist_id)
                toast = Adw.Toast.new(f"Lista '{playlist_name}' eliminada")
                self.add_toast(toast)
                self._populate_playlists()
                # Refresh sidebar counts
                root = self.get_native()
                if root and hasattr(root, "_refresh_sidebar_counts"):
                    root._refresh_sidebar_counts()
                
            delete_btn.connect("clicked", on_delete_clicked)
            btns_box.append(delete_btn)

            play_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
            play_btn.set_css_classes(["playlist-play-btn", "circular"])
            play_btn.set_size_request(40, 40)
            play_btn.connect("clicked", lambda b, plist=pl: self._on_playlist_play(plist))
            btns_box.append(play_btn)

            overlay.add_overlay(btns_box)

            card_gesture = Gtk.GestureClick()
            card_gesture.connect("pressed", lambda g, n, x, y, plist=pl: self._show_playlist_songs(plist))
            overlay.add_controller(card_gesture)

            self._playlists_flow.append(overlay)

    def _show_playlist_songs(self, plist):
        songs = []
        for sid in plist.song_ids:
            s = self.db.get_song(sid)
            if s:
                songs.append(s)
        self._title_label.set_label(plist.name)
        clear_container(self._songs_list)
        for s in songs:
            r = self._build_song_row(s, playlist_id=plist.id)
            self._songs_list.append(r)
        self._stack.set_visible_child_name("songs")
        self._all_songs = songs

    def _on_playlist_play(self, plist):
        songs = []
        for sid in plist.song_ids:
            s = self.db.get_song(sid)
            if s:
                songs.append(s)
        if songs:
            for cb in self._play_song_cbs:
                cb(songs[0], songs)
