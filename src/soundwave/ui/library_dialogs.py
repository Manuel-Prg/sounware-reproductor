import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


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


