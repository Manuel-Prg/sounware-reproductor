"""Mixin: vista virtualizada de canciones (Gtk.ListView + Gio.ListStore)."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio, Pango

from soundwave.library.database.database import Song
from soundwave.ui.library.song_object import SongObject


class LibrarySongsViewMixin:
    # ── Build ─────────────────────────────────────────────────────────────

    def _build_songs_view(self):
        """Virtualised song list backed by Gio.ListStore + Gtk.ListView.
        Only the rows visible on screen are rendered, so performance is
        constant regardless of library size.
        """
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._songs_store = Gio.ListStore(item_type=SongObject)

        self._songs_selection = Gtk.SingleSelection(model=self._songs_store)
        self._songs_selection.set_autoselect(False)
        self._songs_selection.set_can_unselect(True)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup",  self._song_item_setup)
        factory.connect("bind",   self._song_item_bind)
        factory.connect("unbind", self._song_item_unbind)

        self._songs_list_view = Gtk.ListView(
            model=self._songs_selection,
            factory=factory,
        )
        self._songs_list_view.set_css_classes(["songs-list"])
        self._songs_list_view.set_single_click_activate(True)
        self._songs_list_view.connect("activate", self._on_listview_activated)

        scrolled.set_child(self._songs_list_view)
        self._stack.add_named(scrolled, "songs")

        # Legacy alias kept for code that still references _songs_list
        self._songs_list = self._songs_list_view

    def _build_search_view(self):
        """Virtualised search-results view (shares the same factory as songs)."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._search_store = Gio.ListStore(item_type=SongObject)
        search_sel = Gtk.SingleSelection(model=self._search_store)
        search_sel.set_autoselect(False)
        search_sel.set_can_unselect(True)
        self._search_selection = search_sel

        search_factory = Gtk.SignalListItemFactory()
        search_factory.connect("setup",  self._song_item_setup)
        search_factory.connect("bind",   self._song_item_bind)
        search_factory.connect("unbind", self._song_item_unbind)

        self._search_list_view = Gtk.ListView(
            model=search_sel,
            factory=search_factory,
        )
        self._search_list_view.set_css_classes(["songs-list"])
        self._search_list_view.set_single_click_activate(True)
        self._search_list_view.connect("activate", self._on_search_listview_activated)

        scrolled.set_child(self._search_list_view)
        self._stack.add_named(scrolled, "search")

        # Legacy alias
        self._search_list = self._search_list_view

    # ── SignalListItemFactory callbacks ───────────────────────────────────

    def _song_item_setup(self, factory, list_item):
        """Called once per recycled row slot — build the widget skeleton."""
        list_item.set_child(self._build_song_row_widget())

    def _song_item_bind(self, factory, list_item):
        """Called each time a recycled slot is assigned a new item."""
        song_obj = list_item.get_item()
        if song_obj is None:
            return
        self._bind_song_row(list_item.get_child(), song_obj.song)

    def _song_item_unbind(self, factory, list_item):
        """Called when a slot scrolls out of view — detach signal handlers."""
        row = list_item.get_child()
        if row and hasattr(row, "_cleanup"):
            row._cleanup()

    # ── Row widget ────────────────────────────────────────────────────────

    def _build_song_row_widget(self) -> Gtk.Box:
        """Build the widget skeleton for a song row using Gtk.Box (prevents ListBoxRow warnings)."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        row.set_spacing(12)
        row.set_margin_top(6)
        row.set_margin_bottom(6)
        row.set_margin_start(12)
        row.set_margin_end(12)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        text_box.set_hexpand(True)
        text_box.set_valign(Gtk.Align.CENTER)

        title_lbl = Gtk.Label(xalign=0.0)
        title_lbl.add_css_class("title")
        title_lbl.set_ellipsize(Pango.EllipsizeMode.END)

        subtitle_lbl = Gtk.Label(xalign=0.0)
        subtitle_lbl.add_css_class("subtitle")
        subtitle_lbl.add_css_class("dim-label")
        subtitle_lbl.set_ellipsize(Pango.EllipsizeMode.END)

        text_box.append(title_lbl)
        text_box.append(subtitle_lbl)
        row.append(text_box)

        fav_btn = Gtk.Button.new_from_icon_name("emblem-favorite-symbolic")
        fav_btn.set_valign(Gtk.Align.CENTER)
        fav_btn.set_css_classes(["flat", "circular"])
        row._fav_btn = fav_btn
        row.append(fav_btn)

        menu_btn = Gtk.Button.new_from_icon_name("view-more-symbolic")
        menu_btn.set_valign(Gtk.Align.CENTER)
        menu_btn.set_css_classes(["flat", "circular"])
        menu_btn.set_tooltip_text("Más opciones")
        row._menu_btn = menu_btn
        row.append(menu_btn)

        dur_lbl = Gtk.Label(label="")
        dur_lbl.add_css_class("dim-label")
        dur_lbl.set_valign(Gtk.Align.CENTER)
        row._dur_lbl = dur_lbl
        row.append(dur_lbl)

        row._title_lbl = title_lbl
        row._subtitle_lbl = subtitle_lbl
        row._cleanup = lambda: None  # placeholder
        return row

    def _bind_song_row(self, row: Gtk.Box, song: Song):
        """Attach data and signals to a recycled row widget."""
        row._title_lbl.set_markup(f"<b>{GLib.markup_escape_text(song.display_title)}</b>")
        row._subtitle_lbl.set_text(f"{song.display_artist} · {song.display_album}")

        if song.id == self._current_song_id:
            row.add_css_class("now-playing-row")
        else:
            row.remove_css_class("now-playing-row")

        fav_btn = row._fav_btn
        if song.rating >= 4:
            fav_btn.remove_css_class("song-fav-inactive")
            fav_btn.add_css_class("song-fav-active")
        else:
            fav_btn.remove_css_class("song-fav-active")
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

        fav_id = fav_btn.connect("clicked", on_fav_clicked)

        menu_btn = row._menu_btn
        menu_id = menu_btn.connect(
            "clicked", lambda b, s=song: self._show_song_menu(b, s)
        )

        if song.duration:
            m, s_rem = divmod(int(song.duration), 60)
            row._dur_lbl.set_label(f"{m}:{s_rem:02d}")
        else:
            row._dur_lbl.set_label("")

        row._song = song

        def cleanup():
            try:
                fav_btn.disconnect(fav_id)
            except Exception:
                pass
            try:
                menu_btn.disconnect(menu_id)
            except Exception:
                pass
            row._song = None

        row._cleanup = cleanup

    # ── Activation handlers ───────────────────────────────────────────────

    def _on_listview_activated(self, listview, position: int):
        """Handle activation (double-click / Enter) on the main songs ListView."""
        item = self._songs_store.get_item(position)
        if item is None:
            return
        song: Song = item.song
        queue = [obj.song for obj in self._songs_store]
        for cb in self._play_song_cbs:
            cb(song, queue)

    def _on_search_listview_activated(self, listview, position: int):
        item = self._search_store.get_item(position)
        if item is None:
            return
        song: Song = item.song
        queue = [obj.song for obj in self._search_store]
        for cb in self._play_song_cbs:
            cb(song, queue)

    def _on_song_activated(self, listbox, row):
        """Legacy handler kept for album-details and queue ListBoxes."""
        song = getattr(row, "_song", None)
        if song is None and hasattr(row, "get_child"):
            c = row.get_child()
            if c:
                song = getattr(c, "_song", None)
        if song is None:
            return
        queue = []
        child = listbox.get_first_child()
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
