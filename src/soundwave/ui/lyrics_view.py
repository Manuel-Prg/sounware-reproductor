import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Pango, GLib

import threading
from pathlib import Path
from typing import Optional

from soundwave.library.lyrics import get_lyrics, LyricsLine
from soundwave.library.database import Song
from soundwave.ui.utils import clear_container


class LyricsView(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._lyrics: list[LyricsLine] = []
        self._labels: list[Gtk.Label] = []      # referencia directa, sin iterar FlowBox
        self._song: Optional[Song] = None
        self._current_index = -1
        self._loading = False
        self._setup_ui()

    def _setup_ui(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._flow = Gtk.FlowBox()
        self._flow.set_max_children_per_line(1)
        self._flow.set_min_children_per_line(1)
        self._flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flow.set_halign(Gtk.Align.CENTER)
        self._flow.set_valign(Gtk.Align.START)
        self._flow.set_row_spacing(8)
        self._flow.set_margin_top(24)
        self._flow.set_margin_bottom(24)
        self._flow.set_margin_start(32)
        self._flow.set_margin_end(32)
        scrolled.set_child(self._flow)
        self.append(scrolled)

        self._placeholder = Gtk.Label(label="Selecciona una canción\npara ver su letra")
        self._placeholder.set_halign(Gtk.Align.CENTER)
        self._placeholder.set_valign(Gtk.Align.CENTER)
        self._placeholder.set_vexpand(True)
        self._placeholder.set_css_classes(["caption"])
        self._placeholder.set_opacity(0.6)
        self.append(self._placeholder)

    def load_song(self, song: Song):
        if self._loading:
            return
        self._song = song
        self._clear_lyrics()
        self._placeholder.set_label("Cargando letras...")
        self._placeholder.set_visible(True)
        self._loading = True

        artist   = song.display_artist
        title    = song.display_title
        album    = song.display_album
        duration = int(song.duration)
        song_path = Path(song.filepath) if song.filepath else None

        def fetch():
            lyrics = get_lyrics(artist, title, album, duration, song_path) or []
            GLib.idle_add(self._on_lyrics_loaded, lyrics)

        threading.Thread(target=fetch, daemon=True).start()

    def _on_lyrics_loaded(self, lyrics: list[LyricsLine]):
        self._loading = False
        self._lyrics = lyrics
        if not self._lyrics:
            self._placeholder.set_label("No se encontraron letras\npara esta canción")
            self._placeholder.set_visible(True)
            return

        self._placeholder.set_visible(False)
        for i, line in enumerate(self._lyrics):
            label = Gtk.Label()
            label.set_text(line.text)  # set_text escapa automáticamente &, <, > — nunca usar label= con texto de usuario
            label.set_wrap(True)
            label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            label.set_max_width_chars(40)
            label.set_xalign(0.5)
            label.set_yalign(0.5)
            label.set_halign(Gtk.Align.CENTER)
            label.set_valign(Gtk.Align.CENTER)
            label.set_justify(Gtk.Justification.CENTER)
            label.set_hexpand(True)
            label.set_css_classes(["lyrics-line", "lyrics-line-inactive"])
            self._flow.append(label)
            self._labels.append(label)  # guardar referencia directa

    def update_position(self, position_ms: int):
        if not self._lyrics:
            return

        # Buscar el índice activo
        idx = -1
        for i, line in enumerate(self._lyrics):
            if position_ms >= line.timestamp_ms:
                idx = i

        if idx == self._current_index:
            return
        self._current_index = idx

        # BUG FIX: FlowBox no es iterable con for child in self._flow.
        # Usar la lista _labels que construimos al cargar.
        for i, label in enumerate(self._labels):
            if i == idx:
                label.set_css_classes(["lyrics-line", "lyrics-line-active"])
            else:
                label.set_css_classes(["lyrics-line", "lyrics-line-inactive"])

        # Auto-scroll a la línea activa
        if 0 <= idx < len(self._labels):
            self._scroll_to_label(self._labels[idx])

    def _scroll_to_label(self, label: Gtk.Label):
        """Centra el scroll en la línea activa."""
        def do_scroll():
            # FlowBoxChild envuelve el label; necesitamos el child del FlowBox
            child = label.get_parent()  # FlowBoxChild
            if child is None:
                return
            adj = self.get_first_child()  # ScrolledWindow
            if not isinstance(adj, Gtk.ScrolledWindow):
                return
            vadj = adj.get_vadjustment()
            alloc = child.get_allocation()
            page = vadj.get_page_size()
            target = alloc.y - (page / 2) + (alloc.height / 2)
            vadj.set_value(max(0, min(target, vadj.get_upper() - page)))
        GLib.idle_add(do_scroll)

    def _clear_lyrics(self):
        clear_container(self._flow)
        self._lyrics = []
        self._labels = []
        self._current_index = -1