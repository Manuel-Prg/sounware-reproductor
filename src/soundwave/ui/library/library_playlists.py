import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

import hashlib

from soundwave.ui.library.library_dialogs import CreatePlaylistDialog
from soundwave.ui.components.utils import clear_container


class LibraryPlaylistsMixin:
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
        self._previous_view_id = self._current_view_id
        if hasattr(self, "_back_btn"):
            self._back_btn.set_visible(True)
        self._title_label.set_label(plist.name)
        
        self._current_playlist_id = plist.id
        self._all_songs = songs
        self._sort_songs_list()
        
        clear_container(self._songs_list)
        initial_batch = self._all_songs[:100]
        for s in initial_batch:
            r = self._build_song_row(s, playlist_id=plist.id)
            self._songs_list.append(r)
        if len(self._all_songs) > 100:
            GLib.idle_add(self._load_remaining_songs, 100)
            
        self._stack.set_visible_child_name("songs")
        if hasattr(self, "_sort_btn"):
            self._sort_btn.set_visible(True)
            self._update_sort_popover_content()

    def _on_playlist_play(self, plist):
        songs = []
        for sid in plist.song_ids:
            s = self.db.get_song(sid)
            if s:
                songs.append(s)
        if songs:
            for cb in self._play_song_cbs:
                cb(songs[0], songs)
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

