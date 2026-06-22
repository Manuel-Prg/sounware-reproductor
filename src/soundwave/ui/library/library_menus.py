import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from soundwave.ui.library.library_dialogs import CreatePlaylistDialog


class LibraryMenusMixin:
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

    def add_toast(self, toast):
        self._toast_overlay.add_toast(toast)

