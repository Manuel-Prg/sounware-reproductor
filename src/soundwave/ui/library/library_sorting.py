import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from soundwave.library.database.database import Song
from soundwave.ui.components.utils import clear_container


class LibrarySortingMixin:
    def _build_sort_popover_content(self) -> Gtk.Widget:
        current_child = self._stack.get_visible_child_name()
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        title_lbl = Gtk.Label()
        title_lbl.set_halign(Gtk.Align.START)
        title_lbl.set_css_classes(["dim-label"])
        title_lbl.set_margin_bottom(4)
        
        options = []
        
        if current_child == "albums":
            title_lbl.set_label("Ordenar álbumes por:")
            box.append(title_lbl)
            
            options = [
                ("Nombre - ascendente", "album", "asc"),
                ("Nombre - descendente", "album", "desc"),
                ("Número de canciones - ascendente", "song_count", "asc"),
                ("Número de canciones - descendente", "song_count", "desc"),
                ("Duración - ascendente", "total_duration", "asc"),
                ("Duración - descendente", "total_duration", "desc"),
                ("Año - ascendente", "year", "asc"),
                ("Año - descendente", "year", "desc"),
                ("Fecha actualización - ascendente", "date", "asc"),
                ("Fecha actualización - descendente", "date", "desc"),
                ("Artista - ascendente", "artist", "asc"),
                ("Artista - descendente", "artist", "desc"),
                ("Artista de Álbum - ascendente", "album_artist", "asc"),
                ("Artista de Álbum - descendente", "album_artist", "desc"),
                ("Compositor - ascendente", "composer", "asc"),
                ("Compositor - descendente", "composer", "desc"),
            ]
            
            active_crit = getattr(self, "_album_sort_criteria", "album")
            active_ord = getattr(self, "_album_sort_order", "asc")
            
            def set_album_sort(crit, ord_val):
                self._album_sort_criteria = crit
                self._album_sort_order = ord_val
                self._sort_popover.popdown()
                self._populate_albums()
                
            select_callback = set_album_sort
            
        else:
            title_lbl.set_label("Ordenar canciones por:")
            box.append(title_lbl)
            
            options = [
                ("Nombre - ascendente", "title", "asc"),
                ("Nombre - descendente", "title", "desc"),
                ("Artista - ascendente", "artist", "asc"),
                ("Artista - descendente", "artist", "desc"),
                ("Álbum - ascendente", "album", "asc"),
                ("Álbum - descendente", "album", "desc"),
                ("Duración - ascendente", "duration", "asc"),
                ("Duración - descendente", "duration", "desc"),
                ("Año - ascendente", "year", "asc"),
                ("Año - descendente", "year", "desc"),
                ("Fecha actualización - ascendente", "date", "asc"),
                ("Fecha actualización - descendente", "date", "desc"),
                ("Compositor - ascendente", "composer", "asc"),
                ("Compositor - descendente", "composer", "desc"),
            ]
            
            if getattr(self, "_current_playlist_id", None) is not None:
                options.insert(0, ("Orden de la lista", "playlist", "asc"))
            
            active_crit = getattr(self, "_song_sort_criteria", "title")
            active_ord = getattr(self, "_song_sort_order", "asc")
            
            def set_song_sort(crit, ord_val):
                self._song_sort_criteria = crit
                self._song_sort_order = ord_val
                self._sort_popover.popdown()
                self._sort_and_refresh_songs()
                
            select_callback = set_song_sort

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_max_content_height(300)
        scroll.set_propagate_natural_height(True)
        
        options_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        for label, crit, ord_val in options:
            btn = Gtk.Button()
            btn.set_halign(Gtk.Align.FILL)
            btn.set_css_classes(["flat"])
            
            btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            
            lbl = Gtk.Label(label=label)
            lbl.set_xalign(0.0)
            lbl.set_hexpand(True)
            btn_box.append(lbl)
            
            if crit == active_crit and ord_val == active_ord:
                check_img = Gtk.Image.new_from_icon_name("object-select-symbolic")
                check_img.set_pixel_size(12)
                btn_box.append(check_img)
                btn.add_css_class("suggested-action")
                
            btn.set_child(btn_box)
            btn.connect("clicked", lambda b, c=crit, o=ord_val: select_callback(c, o))
            options_box.append(btn)
            
        scroll.set_child(options_box)
        box.append(scroll)
        return box

    def _update_sort_popover_content(self):
        if not hasattr(self, "_sort_popover"):
            return
        content = self._build_sort_popover_content()
        self._sort_popover.set_child(content)

    def _sort_songs_list(self):
        if not hasattr(self, "_all_songs") or not self._all_songs:
            return
            
        criteria = getattr(self, "_song_sort_criteria", "title")
        order = getattr(self, "_song_sort_order", "asc")
        descending = (order == "desc")

        def sort_key(s: Song):
            if criteria == "playlist" and getattr(self, "_current_playlist_id", None) is not None:
                playlist_id = self._current_playlist_id
                if not hasattr(self, "_playlist_pos_cache") or getattr(self, "_playlist_pos_cache_id", None) != playlist_id:
                    rows = self.db.conn.execute(
                        "SELECT song_id, position FROM playlists_songs WHERE playlist_id = ? ORDER BY position",
                        (playlist_id,)
                    ).fetchall()
                    self._playlist_pos_cache = {r["song_id"]: r["position"] for r in rows}
                    self._playlist_pos_cache_id = playlist_id
                return self._playlist_pos_cache.get(s.id, 999999)
            elif criteria == "title":
                return (s.title or "").lower()
            elif criteria == "artist":
                return (s.artist or "").lower()
            elif criteria == "album":
                return (s.album or "").lower()
            elif criteria == "duration":
                return s.duration or 0.0
            elif criteria == "year":
                return s.year or 0
            elif criteria == "date":
                return s.added_at or 0.0
            elif criteria == "composer":
                return (s.composer or "").lower()
            return (s.title or "").lower()

        self._all_songs.sort(key=sort_key, reverse=descending)

    def _sort_and_refresh_songs(self):
        self._sort_songs_list()
        
        current_child = self._stack.get_visible_child_name()
        if current_child == "search":
            clear_container(self._search_list)
            for song in self._all_songs:
                row = self._build_song_row(song)
                self._search_list.append(row)
        else:
            clear_container(self._songs_list)
            playlist_id = getattr(self, "_current_playlist_id", None)
            
            initial_batch = self._all_songs[:100]
            for song in initial_batch:
                row = self._build_song_row(song, playlist_id=playlist_id)
                self._songs_list.append(row)
            if len(self._all_songs) > 100:
                GLib.idle_add(self._load_remaining_songs, 100)
