import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio

from pathlib import Path
from typing import Optional

from soundwave.library.database import Database, Song
from soundwave.library.scanner import MusicScanner
from soundwave.library.album_art import get_art_path
from soundwave.player.engine import Player, PlayerState
from soundwave.ui.player_bar import PlayerBar
from soundwave.ui.library_view import LibraryView
from soundwave.ui.search_bar import SearchBar
from soundwave.ui.equalizer import EqualizerDialog
from soundwave.ui.mini_player import MiniPlayer


class SoundwaveWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, db: Database, player: Player):
        super().__init__(application=app)

        self.db = db
        self.player = player
        self.scanner = MusicScanner(db)
        self._scanner_cancellable: Optional[Gio.Cancellable] = None
        self._current_queue: list[Song] = []
        self._current_queue_source: str = "all"

        self.set_title("Soundwave")
        self.set_default_size(1100, 720)
        self._setup_css()

        # Main layout: vertical box
        self._main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self._main_box)

        # Search bar
        self._search_bar = SearchBar()
        self._search_bar.connect_search(self._on_search)
        self._main_box.append(self._search_bar)

        # Paned: sidebar + content
        self._paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self._paned.set_shrink_start_child(False)
        self._paned.set_shrink_end_child(False)
        self._main_box.append(self._paned)

        # Sidebar
        self._sidebar = self._build_sidebar()
        self._paned.set_start_child(self._sidebar)

        # Library view (main content)
        self._library_view = LibraryView(db, player)
        self._library_view.connect_play_song(self._on_play_song)
        self._library_view.connect_queue_song(self._on_queue_song)
        self._paned.set_end_child(self._library_view)

        # Player bar at bottom
        self._player_bar = PlayerBar(player)
        self._player_bar.connect_toggle_mini(self._on_toggle_mini)
        self._player_bar.connect_show_equalizer(self._on_show_equalizer)
        self._main_box.append(self._player_bar)

        # Mini player (hidden initially)
        self._mini_player = MiniPlayer(player)
        self._mini_player.connect_restore_window(self._on_restore_from_mini)

        # Set up keyboard shortcuts
        self._setup_shortcuts()

        # Scan directory picker on startup
        self._check_library()

        # Connect player signals for MPRIS last.fm integration
        self.player.connect_song(self._on_player_song_changed)

    def _setup_css(self):
        css_provider = Gtk.CssProvider()
        css = """
        .sidebar-row {
            border-radius: 8px;
            margin: 2px 8px;
        }
        .sidebar-row:selected {
            background-color: alpha(@accent_bg_color, 0.3);
        }
        .player-bar {
            background-color: @window_bg_color;
            border-top: 1px solid @borders;
        }
        .album-cover {
            border-radius: 6px;
        }
        .album-grid {
            margin: 12px;
        }
        .song-row {
            border-radius: 6px;
            padding: 6px 12px;
        }
        .song-row:hover {
            background-color: alpha(@accent_bg_color, 0.08);
        }
        .song-row:selected {
            background-color: alpha(@accent_bg_color, 0.2);
        }
        .equalizer-slider {
            min-height: 120px;
        }
        .volume-button {
            min-width: 32px;
        }
        .mini-player {
            background-color: @window_bg_color;
            border: 1px solid @borders;
        }
        """
        css_provider.load_from_string(css)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_sidebar(self) -> Gtk.Widget:
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar.set_size_request(220, -1)

        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label="Soundwave"))
        sidebar.append(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        sidebar.append(scrolled)

        self._sidebar_list = Gtk.ListBox()
        self._sidebar_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._sidebar_list.set_css_classes(["sidebar-list"])
        scrolled.set_child(self._sidebar_list)

        items = [
            ("music-library-symbolic", "Todas las canciones", "all"),
            ("album-symbolic", "Álbumes", "albums"),
            ("artist-symbolic", "Artistas", "artists"),
            ("genre-symbolic", "Géneros", "genres"),
        ]
        for icon_name, label, view_id in items:
            row = Adw.ActionRow()
            row.set_title(label)
            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(20)
            row.add_prefix(icon)
            row.set_css_classes(["sidebar-row"])
            row._view_id = view_id
            self._sidebar_list.append(row)

        self._sidebar_list.connect("row-activated", self._on_sidebar_row_activated)

        # Select first
        first = self._sidebar_list.get_row_at_index(0)
        if first:
            self._sidebar_list.select_row(first)
            self._current_view = "all"

        return sidebar

    def _build_toolbar_view(self) -> Adw.ToolbarView:
        tv = Adw.ToolbarView()
        return tv

    def _setup_shortcuts(self):
        ctrl = Gtk.ShortcutController()
        self.add_controller(ctrl)

        shortcuts = [
            ("space", lambda: self._player_bar._on_play_pause()),
            ("<Control>Right", lambda: self.player.next()),
            ("<Control>Left", lambda: self.player.previous()),
            ("<Control>f", lambda: self._search_bar.focus()),
            ("Escape", lambda: self._search_bar.clear()),
            ("<Control>m", lambda: self._on_toggle_mini()),
            ("<Control>e", lambda: self._on_show_equalizer()),
        ]
        for trigger_str, callback in shortcuts:
            trigger = Gtk.ShortcutTrigger.parse_string(trigger_str)
            action = Gtk.CallbackAction.new(callback)
            shortcut = Gtk.Shortcut()
            shortcut.set_trigger(trigger)
            shortcut.set_action(action)
            ctrl.add_shortcut(shortcut)

    def _check_library(self):
        stats = self.db.get_stats()
        if stats["total_songs"] == 0:
            self._show_welcome_dialog()

    def _show_welcome_dialog(self):
        dialog = Adw.AlertDialog(
            heading="¡Bienvenido a Soundwave!",
            body="Tu biblioteca está vacía. ¿Quieres escanear tu carpeta de música?",
        )
        dialog.add_response("cancel", "Ahora no")
        dialog.add_response("scan", "Escanear música")
        dialog.set_response_appearance("scan", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("scan")
        dialog.connect("response", self._on_welcome_response)
        dialog.present(self)

    def _on_welcome_response(self, dialog, response):
        if response == "scan":
            self._show_scan_dialog()

    def _show_scan_dialog(self):
        dialog = Adw.AlertDialog(
            heading="Seleccionar carpeta",
            body="Elige la carpeta donde tienes tu música.",
        )
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("browse", "Seleccionar carpeta")
        dialog.set_response_appearance("browse", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self._on_scan_response)
        dialog.present(self)

    def _on_scan_response(self, dialog, response):
        if response == "browse":
            self._open_folder_picker()

    def _open_folder_picker(self):
        def on_folder_selected(dialog, result):
            try:
                folder = dialog.select_folder_finish(result)
                if folder:
                    self._start_scan(Path(folder.get_path()))
            except GLib.Error:
                pass

        dialog = Gtk.FolderDialog()
        dialog.set_title("Seleccionar carpeta de música")
        dialog.select_folder(parent=self, cancellable=None, callback=on_folder_selected)

    def _start_scan(self, directory: Path):
        self._scan_dialog = Adw.AlertDialog(
            heading="Escaneando...",
            body="Buscando archivos de música...",
        )
        self._scan_dialog.add_response("cancel", "Cancelar")
        self._scan_dialog.connect("response", lambda d, r: self.scanner.cancel())
        self._scan_dialog.present(self)

        def scan_task():
            added, skipped = self.scanner.scan_directories(
                [directory],
                progress_cb=lambda done, total, msg: GLib.idle_add(
                    lambda: self._update_scan_progress(done, total, msg)
                )
            )
            GLib.idle_add(lambda: self._on_scan_complete(added, skipped))

        import threading
        thread = threading.Thread(target=scan_task, daemon=True)
        thread.start()

    def _update_scan_progress(self, done: int, total: int, msg: str):
        if done < total:
            self._scan_dialog.set_body(f"{done}/{total} - {msg}")
        return False

    def _on_scan_complete(self, added: int, skipped: int):
        self._scan_dialog.close()
        toast = Adw.Toast.new(f"Escaneo completo: {added} canciones añadidas")
        toast.set_timeout(3)
        if hasattr(self, "_player_bar") and self._player_bar:
            pass
        self._refresh_library()
        self._show_stats_notification(added)

    def _show_stats_notification(self, added: int):
        stats = self.db.get_stats()
        msg = f"{stats['total_songs']} canciones, {stats['total_artists']} artistas, {stats['total_albums']} álbumes"
        toast = Adw.Toast.new(msg)
        toast.set_timeout(3)
        self._player_bar.add_toast(toast)

    def _refresh_library(self):
        self._library_view.refresh()
        self._refresh_sidebar_counts()

    def _refresh_sidebar_counts(self):
        stats = self.db.get_stats()
        for i in range(self._sidebar_list.get_row_at_index(0) is not None and 4 or 0):
            row = self._sidebar_list.get_row_at_index(i)
            if row and i == 0:
                row.set_subtitle(str(stats["total_songs"]))

    # --- Sidebar navigation ---
    def _on_sidebar_row_activated(self, listbox, row):
        view_id = getattr(row, "_view_id", "all")
        self._current_view = view_id
        self._library_view.show_view(view_id)

    # --- Search ---
    def _on_search(self, query: str):
        if query:
            results = self.db.search_songs(query)
            self._library_view.show_search_results(results)
        else:
            self._library_view.show_view(self._current_view)

    # --- Playback ---
    def _on_play_song(self, song: Song, queue: list[Song]):
        self._current_queue = queue
        self.player.set_queue(queue, queue.index(song))

    def _on_queue_song(self, song: Song):
        self.player.add_to_queue(song)

    def _on_player_song_changed(self, song: Optional[Song]):
        if song and self._lastfm and self._lastfm.connected:
            self._lastfm.now_playing(
                song.display_artist, song.display_title, song.display_album,
                int(song.duration)
            )
        self._library_view.highlight_song(song)
        art_path = get_art_path(song.id, self.db) if song else None
        self._player_bar.set_artwork_from_path(art_path)
        self._mini_player.set_artwork_from_path(art_path)

    # --- Mini player ---
    def _on_toggle_mini(self):
        if self._mini_player.get_visible():
            self._on_restore_from_mini()
        else:
            self.set_visible(False)
            self._mini_player.set_visible(True)
            self._mini_player.present()

    def _on_restore_from_mini(self):
        self._mini_player.set_visible(False)
        self.set_visible(True)
        self.present()

    # --- Equalizer ---
    def _on_show_equalizer(self):
        dialog = EqualizerDialog(self.player, self)
        dialog.present()

    def set_lastfm(self, lastfm):
        self._lastfm = lastfm

    def get_player_bar(self):
        return self._player_bar
