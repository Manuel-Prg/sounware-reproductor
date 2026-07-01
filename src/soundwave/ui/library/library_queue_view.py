"""Mixin: vista y lógica de la cola de reproducción."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, GLib, GObject

from soundwave.library.database.database import Song
from soundwave.ui.components.utils import clear_container


class LibraryQueueViewMixin:
    # ── Build ─────────────────────────────────────────────────────────────

    def _build_queue_view(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(16)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        toolbar.append(spacer)

        self._clear_queue_btn = Gtk.Button()
        self._clear_queue_btn.set_css_classes(["destructive-action"])
        self._clear_queue_btn.set_label("Limpiar cola")
        self._clear_queue_btn.connect("clicked", lambda b: self._on_clear_queue_clicked())
        toolbar.append(self._clear_queue_btn)

        main_box.append(toolbar)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)

        self._queue_list = Gtk.ListBox()
        self._queue_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._queue_list.set_css_classes(["songs-list"])
        self._queue_list.connect("row-activated", self._on_queue_row_activated)
        scrolled.set_child(self._queue_list)

        main_box.append(scrolled)
        self._stack.add_named(main_box, "queue")

    # ── Populate ──────────────────────────────────────────────────────────

    def _populate_queue(self):
        clear_container(self._queue_list)
        queue = self.player.get_queue()
        curr_idx = self.player.get_current_index()

        if hasattr(self, "_clear_queue_btn"):
            self._clear_queue_btn.set_sensitive(len(queue) > 0)

        if not queue:
            placeholder_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            placeholder_box.set_halign(Gtk.Align.CENTER)
            placeholder_box.set_valign(Gtk.Align.CENTER)
            placeholder_box.set_vexpand(True)
            placeholder_box.set_margin_top(48)

            icon = Gtk.Image.new_from_icon_name("list-drag-handle-symbolic")
            icon.set_pixel_size(48)
            icon.add_css_class("dim-label")
            placeholder_box.append(icon)

            label = Gtk.Label(label="La cola de reproducción está vacía")
            label.add_css_class("dim-label")
            label.set_css_classes(["title-4"])
            placeholder_box.append(label)

            row = Gtk.ListBoxRow()
            row.set_child(placeholder_box)
            row.set_selectable(False)
            row.set_activatable(False)
            self._queue_list.append(row)
            return

        for idx, song in enumerate(queue):
            is_current = (idx == curr_idx)
            self._queue_list.append(self._build_queue_row(song, is_current=is_current))

    def _build_queue_row(self, song: Song, is_current: bool = False) -> Adw.ActionRow:
        row = Adw.ActionRow()
        row.set_activatable(True)
        row.set_title(GLib.markup_escape_text(song.display_title))
        row.set_subtitle(GLib.markup_escape_text(
            f"{song.display_artist} · {song.display_album}"
        ))
        row._song = song

        if is_current:
            row.add_css_class("now-playing-row")
            play_icon = Gtk.Image.new_from_icon_name("media-playback-start-symbolic")
            play_icon.set_valign(Gtk.Align.CENTER)
            row.add_prefix(play_icon)
        else:
            handle_img = Gtk.Image.new_from_icon_name("list-drag-handle-symbolic")
            handle_img.set_valign(Gtk.Align.CENTER)
            handle_img.add_css_class("dim-label")
            row.add_prefix(handle_img)

            drag_source = Gtk.DragSource.new()
            drag_source.set_actions(Gdk.DragAction.MOVE)

            def on_drag_prepare(source, x, y, r=row):
                self._dragged_row = r
                return Gdk.ContentProvider.new_for_value("row")

            def on_drag_cancel(source, drag, reason):
                self._dragged_row = None
                return False

            drag_source.connect("prepare", on_drag_prepare)
            drag_source.connect("drag-cancel", on_drag_cancel)
            handle_img.add_controller(drag_source)

            drop_target = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)

            def on_enter(target, x, y, target_row=row):
                dragged_row = getattr(self, "_dragged_row", None)
                if dragged_row and dragged_row != target_row:
                    listbox = target_row.get_parent()
                    if listbox:
                        target_idx = target_row.get_index()
                        listbox.remove(dragged_row)
                        listbox.insert(dragged_row, target_idx)
                return Gdk.DragAction.MOVE

            def on_drop(target, value, x, y, target_row=row):
                listbox = target_row.get_parent()
                if listbox:
                    songs = []
                    child = listbox.get_first_child()
                    while child:
                        s = getattr(child, "_song", None)
                        if s:
                            songs.append(s)
                        child = child.get_next_sibling()
                    self.player.reorder_queue(songs)
                    self._dragged_row = None
                    return True
                return False

            drop_target.connect("enter", on_enter)
            drop_target.connect("drop", on_drop)
            row.add_controller(drop_target)

        # Favourite button
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

        menu_btn = Gtk.Button.new_from_icon_name("view-more-symbolic")
        menu_btn.set_valign(Gtk.Align.CENTER)
        menu_btn.set_css_classes(["flat", "circular"])
        menu_btn.set_tooltip_text("Más opciones")
        menu_btn.connect("clicked", lambda b, s=song: self._show_song_menu(b, s))
        row.add_suffix(menu_btn)

        remove_btn = Gtk.Button.new_from_icon_name("list-remove-symbolic")
        remove_btn.set_valign(Gtk.Align.CENTER)
        remove_btn.set_css_classes(["flat", "circular"])
        remove_btn.set_tooltip_text("Quitar de la cola")

        def on_remove_clicked(btn, r=row):
            idx = r.get_index()
            if idx != -1:
                self.player.remove_from_queue(idx)

        remove_btn.connect("clicked", on_remove_clicked)
        row.add_suffix(remove_btn)

        return row

    # ── Callbacks ─────────────────────────────────────────────────────────

    def _on_queue_row_activated(self, listbox, row):
        idx = row.get_index()
        if idx != -1 and getattr(row, "_song", None):
            self.player.play_index(idx)

    def _on_clear_queue_clicked(self):
        self.player.clear_queue()

    def _on_player_queue_changed(self, queue):
        if self._current_view_id == "queue":
            GLib.idle_add(self._populate_queue)
