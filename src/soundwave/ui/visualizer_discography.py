"""Discografía del visualizador."""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango, GLib, Gdk

from soundwave.library.database import Song
from soundwave.ui.utils import clear_container


def extract_main_artist(artist_name: str) -> str:
    if not artist_name:
        return ""
    delimiters = [
        " feat.", " feat ", " ft.", " ft ", " featuring ", " FEAT.", " FEAT ", " FT.", " FT ",
        " & ", " / ", " vs.", " vs ", ", ", " Feat.", " Feat "
    ]
    main = artist_name
    for delim in delimiters:
        if delim in main:
            main = main.split(delim)[0]
    return main.strip()


class VisualizerDiscographyMixin:
    def _on_artist_clicked(self, gesture, n_press, x, y):
        if self._current_artist:
            self._show_discography = not self._show_discography
            if self._show_discography:
                self._populate_discography()
            self._discography_revealer.set_reveal_child(self._show_discography)

    def _populate_discography(self):
        clear_container(self._discography_box)

        if not self._current_artist:
            return

        main_artist = extract_main_artist(self._current_artist)
        if not main_artist:
            return

        # Fetch all songs in the database and filter by main artist
        all_songs = self.db.get_all_songs()
        songs = []
        for s in all_songs:
            s_main = extract_main_artist(s.artist)
            s_album_main = extract_main_artist(s.album_artist)
            if s_main == main_artist or s_album_main == main_artist:
                songs.append(s)

        if not songs:
            return

        # Sort the list by album, disc_number, track_number
        songs.sort(key=lambda s: (s.album or "", s.disc_number or 1, s.track_number or 0))

        albums: dict[str, list[Song]] = {}
        for s in songs:
            album_name = s.display_album
            if album_name not in albums:
                albums[album_name] = []
            albums[album_name].append(s)

        current_song = self._player.get_current_song()
        current_id = current_song.id if current_song else None

        num_albums = len(albums)

        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        section.set_css_classes(["discography-section"])
        section.set_halign(Gtk.Align.CENTER)

        # Dynamic size request based on number of columns
        if num_albums == 1:
            section.set_size_request(450, -1)
            max_cols = 1
        elif num_albums == 2:
            section.set_size_request(760, -1)
            max_cols = 2
        else:
            section.set_size_request(1000, -1)
            max_cols = 3

        # Header Box (Icon + Title + Subtitle)
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        header_box.set_margin_top(6)
        header_box.set_margin_bottom(6)
        header_box.set_margin_start(10)
        header_box.set_margin_end(10)

        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_row.set_halign(Gtk.Align.START)
        
        art_icon = Gtk.Image.new_from_icon_name("avatar-default-symbolic")
        art_icon.set_pixel_size(14)
        art_icon.add_css_class("discography-header-icon")
        title_row.append(art_icon)

        title_lbl = Gtk.Label(label=f"Discografía de {main_artist}")
        title_lbl.add_css_class("discography-header-title")
        title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        title_lbl.set_max_width_chars(45)
        title_row.append(title_lbl)
        header_box.append(title_row)

        sub_lbl = Gtk.Label(label=f"{num_albums} álbumes · {len(songs)} canciones")
        sub_lbl.add_css_class("discography-header-subtitle")
        sub_lbl.set_xalign(0)
        sub_lbl.set_margin_start(22)
        header_box.append(sub_lbl)
        
        section.append(header_box)

        # Grid containing the album columns
        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(12)
        grid.set_column_homogeneous(True)
        grid.set_hexpand(True)

        col = 0
        row_idx = 0

        for album_name, album_songs in albums.items():
            album_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            album_col.add_css_class("discography-album-col")
            album_col.set_valign(Gtk.Align.START)
            album_col.set_hexpand(True)

            # Album header inside the column
            album_header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            album_header_box.set_margin_top(6)
            album_header_box.set_margin_bottom(4)
            album_header_box.set_margin_start(8)
            album_header_box.set_margin_end(8)

            album_icon = Gtk.Image.new_from_icon_name("media-optical-symbolic")
            album_icon.set_pixel_size(14)
            album_icon.add_css_class("discography-album-icon")
            album_header_box.append(album_icon)

            album_lbl = Gtk.Label(label=album_name)
            album_lbl.add_css_class("discography-album-title")
            album_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            album_lbl.set_xalign(0)
            album_header_box.append(album_lbl)

            album_col.append(album_header_box)

            # ListBox for the songs in this album
            listbox = Gtk.ListBox()
            listbox.set_selection_mode(Gtk.SelectionMode.NONE)
            listbox.add_css_class("discography-listbox")

            for s in album_songs:
                song_row = Gtk.ListBoxRow()
                song_row.add_css_class("discography-song-row")
                is_current = (s.id == current_id)
                if is_current:
                    song_row.add_css_class("discography-song-row-current")

                song_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                song_box.set_margin_top(4)
                song_box.set_margin_bottom(4)
                song_box.set_margin_start(10)
                song_box.set_margin_end(8)

                # Icon
                if is_current:
                    song_icon = Gtk.Image.new_from_icon_name("audio-volume-high-symbolic")
                    song_icon.add_css_class("discography-song-icon-current")
                else:
                    song_icon = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")
                    song_icon.add_css_class("discography-song-icon")
                song_icon.set_pixel_size(12)
                song_box.append(song_icon)

                # Title
                song_lbl = Gtk.Label(label=GLib.markup_escape_text(s.display_title))
                song_lbl.set_xalign(0)
                song_lbl.set_ellipsize(Pango.EllipsizeMode.END)
                song_lbl.set_hexpand(True)
                song_lbl.add_css_class("discography-song-title")
                if is_current:
                    song_lbl.add_css_class("discography-song-title-current")
                song_box.append(song_lbl)

                # Duration
                if s.duration:
                    m, sec = divmod(int(s.duration), 60)
                    dur_lbl = Gtk.Label(label=f"{m}:{sec:02d}")
                    dur_lbl.add_css_class("discography-song-duration")
                    if is_current:
                        dur_lbl.add_css_class("discography-song-duration-current")
                    song_box.append(dur_lbl)

                song_row.set_child(song_box)
                song_row.set_cursor(Gdk.Cursor.new_from_name("pointer"))
                
                row_gesture = Gtk.GestureClick()
                row_gesture.connect("pressed", lambda g, n, x, y, song=s, all_songs=songs: self._on_disco_song_clicked(song, all_songs))
                song_row.add_controller(row_gesture)

                listbox.append(song_row)

            album_col.append(listbox)
            grid.attach(album_col, col, row_idx, 1, 1)

            col += 1
            if col >= max_cols:
                col = 0
                row_idx += 1

        section.append(grid)
        self._discography_box.append(section)
        self._discography_box.show()

    def _on_disco_song_clicked(self, song: Song, all_songs: list[Song]):
        for cb in self._play_song_cbs:
            cb(song, all_songs)

