import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk

from soundwave.library.database.database import Song, UNKNOWN_ARTIST, UNKNOWN_ALBUM
from soundwave.library.metadata.album_art import get_art_path, CACHE_DIR as ART_CACHE_DIR
from soundwave.ui.components.utils import clear_container


class LibraryAlbumDetailsMixin:
    def _build_album_details_view(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        main_box.set_margin_start(24)
        main_box.set_margin_end(24)
        main_box.set_margin_top(24)
        main_box.set_margin_bottom(24)

        # Header Box
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        header_box.add_css_class("album-details-header")

        # Cover image (large)
        self._album_details_avatar = Adw.Avatar(size=160, text="", show_initials=True)
        self._album_details_avatar.set_halign(Gtk.Align.START)
        self._album_details_avatar.set_valign(Gtk.Align.CENTER)
        header_box.append(self._album_details_avatar)

        # Info Box (Vertical)
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        info_box.set_valign(Gtk.Align.CENTER)
        info_box.set_hexpand(True)

        type_label = Gtk.Label(label="ÁLBUM")
        type_label.set_halign(Gtk.Align.START)
        type_label.add_css_class("album-details-type")
        info_box.append(type_label)

        self._album_details_title = Gtk.Label(label="")
        self._album_details_title.set_halign(Gtk.Align.START)
        self._album_details_title.set_wrap(True)
        self._album_details_title.add_css_class("album-details-title")
        info_box.append(self._album_details_title)

        self._album_details_artist = Gtk.Label(label="")
        self._album_details_artist.set_halign(Gtk.Align.START)
        self._album_details_artist.add_css_class("album-details-artist")
        info_box.append(self._album_details_artist)

        self._album_details_meta = Gtk.Label(label="")
        self._album_details_meta.set_halign(Gtk.Align.START)
        self._album_details_meta.add_css_class("album-details-meta")
        info_box.append(self._album_details_meta)

        # Buttons Box
        buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        buttons_box.set_margin_top(8)

        play_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        play_btn.add_css_class("play-button-main")
        play_btn.set_size_request(48, 48)
        play_btn.set_tooltip_text("Reproducir álbum")
        play_btn.connect("clicked", self._on_album_details_play_clicked)
        buttons_box.append(play_btn)

        shuffle_btn = Gtk.Button.new_from_icon_name("media-playlist-shuffle-symbolic")
        shuffle_btn.add_css_class("flat")
        shuffle_btn.add_css_class("circular")
        shuffle_btn.set_size_request(48, 48)
        shuffle_btn.set_tooltip_text("Aleatorio")
        shuffle_btn.connect("clicked", self._on_album_details_shuffle_clicked)
        buttons_box.append(shuffle_btn)

        info_box.append(buttons_box)
        header_box.append(info_box)
        main_box.append(header_box)

        # Songs list for this album
        self._album_details_list = Gtk.ListBox()
        self._album_details_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._album_details_list.set_css_classes(["songs-list"])
        self._album_details_list.connect("row-activated", self._on_song_activated)
        
        main_box.append(self._album_details_list)

        scrolled.set_child(main_box)
        self._stack.add_named(scrolled, "album_details")

    def _show_album_songs(self, album: dict):
        songs = self.db.get_songs_by_album(album["album"], album.get("album_artist", ""))
        if not songs:
            return
        album_name = album.get("album", UNKNOWN_ALBUM)
        self._title_label.set_label(f"{album_name}")
        clear_container(self._songs_list)
        for s in songs:
            r = self._build_song_row(s)
            self._songs_list.append(r)
        self._stack.set_visible_child_name("songs")
        self._all_songs = songs

    def _show_album_details(self, album: dict):
        songs = self.db.get_songs_by_album(album["album"], album.get("album_artist", ""))
        if not songs:
            return
        album_name = album.get("album", UNKNOWN_ALBUM)
        artist_name = album.get("album_artist", "")
        if (not artist_name or artist_name == UNKNOWN_ARTIST) and songs:
            artist_name = songs[0].display_artist
        
        self._previous_view_id = self._current_view_id
        if hasattr(self, "_back_btn"):
            self._back_btn.set_visible(True)

        self._title_label.set_label(f"Álbum: {album_name}")

        self._album_details_title.set_label(album_name)
        self._album_details_artist.set_label(artist_name)
        
        total_duration = sum(s.duration for s in songs if s.duration)
        min_duration, sec_duration = divmod(int(total_duration), 60)
        hr_duration, min_duration = divmod(min_duration, 60)
        
        if hr_duration > 0:
            duration_str = f"{hr_duration} h {min_duration} min"
        else:
            duration_str = f"{min_duration} min {sec_duration} s"

        songs_count_str = f"{len(songs)} canción" if len(songs) == 1 else f"{len(songs)} canciones"
        
        year = None
        for s in songs:
            if hasattr(s, "year") and s.year:
                year = s.year
                break
        if year:
            self._album_details_meta.set_label(f"{year} · {songs_count_str} · {duration_str}")
        else:
            self._album_details_meta.set_label(f"{songs_count_str} · {duration_str}")

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

        self._album_details_avatar.set_text(album_name)
        if art_texture:
            self._album_details_avatar.set_custom_image(art_texture)
        else:
            self._album_details_avatar.set_custom_image(None)

        clear_container(self._album_details_list)
        for s in songs:
            r = self._build_song_row(s)
            self._album_details_list.append(r)

        self._album_details_songs = songs
        self._all_songs = songs
        
        self._stack.set_visible_child_name("album_details")

    def _on_album_details_play_clicked(self, btn):
        if hasattr(self, "_album_details_songs") and self._album_details_songs:
            songs = self._album_details_songs
            for cb in self._play_song_cbs:
                cb(songs[0], songs)

    def _on_album_details_shuffle_clicked(self, btn):
        if hasattr(self, "_album_details_songs") and self._album_details_songs:
            import random
            songs = list(self._album_details_songs)
            random.shuffle(songs)
            for cb in self._play_song_cbs:
                cb(songs[0], songs)

    def _on_album_clicked(self, album: dict):
        self._show_album_details(album)

    def _on_artist_selected_name(self, artist_name: str):
        songs = self.db.get_songs_by_artist(artist_name)
        if songs:
            self._previous_view_id = self._current_view_id
            if hasattr(self, "_back_btn"):
                self._back_btn.set_visible(True)
            self._title_label.set_label(artist_name)
            clear_container(self._songs_list)
            for s in songs:
                r = self._build_song_row(s)
                self._songs_list.append(r)
            self._stack.set_visible_child_name("songs")
            self._all_songs = songs

    def _on_genre_selected(self, genre: str):
        songs = self.db.get_songs_by_genre(genre)
        if songs:
            self._previous_view_id = self._current_view_id
            if hasattr(self, "_back_btn"):
                self._back_btn.set_visible(True)
            self._title_label.set_label(genre)
            clear_container(self._songs_list)
            for s in songs:
                r = self._build_song_row(s)
                self._songs_list.append(r)
            self._stack.set_visible_child_name("songs")
            self._all_songs = songs
