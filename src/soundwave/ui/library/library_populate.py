"""Mixin: lógica de población de vistas (álbumes, artistas, géneros, canciones)."""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from soundwave.ui.components.utils import clear_container
from soundwave.ui.library.song_object import SongObject


class LibraryPopulateMixin:
    # ── Songs ─────────────────────────────────────────────────────────────

    def _populate_songs(self):
        self._current_playlist_id = None
        if getattr(self, "_song_sort_criteria", "title") == "playlist":
            self._song_sort_criteria = "title"

        self._all_songs = self.db.get_all_songs()
        self._sort_songs_list()

        # Gtk.ListView only renders what's visible — fill the whole store at once.
        objects = [SongObject(song) for song in self._all_songs]
        self._songs_store.splice(0, self._songs_store.get_n_items(), objects)

    def _load_remaining_songs(self, start_index: int) -> bool:
        """Kept for API compatibility; no longer used (store is filled at once)."""
        return False

    # ── Albums ────────────────────────────────────────────────────────────

    def _populate_albums(self):
        self._update_album_view_mode_popover()

        view_mode = getattr(self, "_album_view_mode", "circle")
        if view_mode == "list":
            self._albums_main_stack.set_visible_child_name("list")
            clear_container(self._albums_list)
        else:
            self._albums_main_stack.set_visible_child_name("grid")
            clear_container(self._albums_flow)

        albums = self.db.get_albums()

        # Sort
        criteria = getattr(self, "_album_sort_criteria", "album")
        order = getattr(self, "_album_sort_order", "asc")
        descending = (order == "desc")

        def sort_key(a: dict):
            if criteria == "album":
                return (a.get("album") or "").lower()
            elif criteria == "song_count":
                return a.get("song_count") or 0
            elif criteria == "total_duration":
                return a.get("total_duration") or 0.0
            elif criteria == "year":
                return a.get("year") or 0
            elif criteria == "date":
                return a.get("added_at") or 0.0
            elif criteria == "artist":
                return (a.get("artist") or "").lower()
            elif criteria == "album_artist":
                return (a.get("album_artist") or "").lower()
            elif criteria == "composer":
                return (a.get("composer") or "").lower()
            return (a.get("album") or "").lower()

        albums.sort(key=sort_key, reverse=descending)

        # Load first 20 immediately, then batch-load the rest in idle callbacks.
        for album in albums[:20]:
            self._append_album_widget(album, view_mode)
        if len(albums) > 20:
            GLib.idle_add(self._load_remaining_albums, albums, 20)

    def _append_album_widget(self, album: dict, view_mode: str):
        if view_mode == "list":
            self._albums_list.append(self._build_album_list_row(album))
        else:
            self._albums_flow.append(self._build_album_card(album))

    def _load_remaining_albums(self, albums: list, start_index: int) -> bool:
        view_mode = getattr(self, "_album_view_mode", "circle")
        batch_size = 15
        end_index = min(start_index + batch_size, len(albums))
        for i in range(start_index, end_index):
            self._append_album_widget(albums[i], view_mode)
        if end_index < len(albums):
            GLib.idle_add(self._load_remaining_albums, albums, end_index)
        return False

    # ── Artists ───────────────────────────────────────────────────────────

    def _populate_artists(self):
        clear_container(self._artists_flow)
        artists = self.db.get_artists()
        for artist in artists[:20]:
            self._artists_flow.append(self._build_artist_card(artist))
        if len(artists) > 20:
            GLib.idle_add(self._load_remaining_artists, artists, 20)

    def _load_remaining_artists(self, artists: list, start_index: int) -> bool:
        batch_size = 15
        end_index = min(start_index + batch_size, len(artists))
        for i in range(start_index, end_index):
            self._artists_flow.append(self._build_artist_card(artists[i]))
        if end_index < len(artists):
            GLib.idle_add(self._load_remaining_artists, artists, end_index)
        return False

    # ── Genres ────────────────────────────────────────────────────────────

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
        for g in genres[:15]:
            self._genres_flow.append(self._build_genre_card(g))
        if len(genres) > 15:
            GLib.idle_add(self._load_remaining_genres, genres, 15)

    def _load_remaining_genres(self, genres: list, start: int) -> bool:
        batch_size = 10
        end = min(start + batch_size, len(genres))
        for i in range(start, end):
            self._genres_flow.append(self._build_genre_card(genres[i]))
        if end < len(genres):
            GLib.idle_add(self._load_remaining_genres, genres, end)
        return False

    # ── Album view-mode popover ───────────────────────────────────────────

    def _update_album_view_mode_popover(self):
        if not hasattr(self, "_album_view_mode_popover"):
            return
        self._album_view_mode_popover.set_child(
            self._build_view_mode_popover_content()
        )

    def _build_view_mode_popover_content(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        title_lbl = Gtk.Label(label="Modo de vista para álbum")
        title_lbl.set_halign(Gtk.Align.START)
        title_lbl.set_css_classes(["dim-label"])
        title_lbl.set_margin_bottom(4)
        box.append(title_lbl)

        options = [
            ("Vista en círculo", "circle"),
            ("Vista en cuadrícula", "grid"),
            ("Vista en lista", "list"),
        ]
        active_mode = getattr(self, "_album_view_mode", "circle")

        def set_view_mode(mode):
            from soundwave.library.config.config import save_setting
            self._album_view_mode = mode
            save_setting("album_view_mode", mode)
            self._album_view_mode_popover.popdown()
            # Mark albums as dirty so next show_view rebuilds them
            self._views_dirty.add("albums")
            self._populate_albums()

        for label, mode in options:
            btn = Gtk.Button()
            btn.set_halign(Gtk.Align.FILL)
            btn.set_css_classes(["flat"])

            btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            lbl = Gtk.Label(label=label)
            lbl.set_xalign(0.0)
            lbl.set_hexpand(True)
            btn_box.append(lbl)

            if mode == active_mode:
                check = Gtk.Image.new_from_icon_name("object-select-symbolic")
                check.set_pixel_size(12)
                btn_box.append(check)
                btn.add_css_class("suggested-action")

            btn.set_child(btn_box)
            btn.connect("clicked", lambda b, m=mode: set_view_mode(m))
            box.append(btn)

        return box
