import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio, Gdk

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
from soundwave.ui.settings import SettingsDialog
from soundwave.ui.lyrics_view import LyricsView


class SoundwaveWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, db: Database, player: Player):
        super().__init__(application=app)

        self.db = db
        self.player = player
        self.scanner = MusicScanner(db)
        self._scanner_cancellable: Optional[Gio.Cancellable] = None
        self._current_queue: list[Song] = []
        self._current_queue_source: str = "all"
        self._lastfm = None
        self._scrobbled_song_id: Optional[int] = None
        self._watcher = None

        self.set_title("Soundwave")
        self.set_default_size(1100, 720)
        self._setup_css()

        # Main layout: vertical box
        self._main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self._main_box)

        # Sidebar
        self._sidebar = self._build_sidebar()

        # Library view (main content)
        self._library_view = LibraryView(db, player)
        self._library_view.connect_play_song(self._on_play_song)
        self._library_view.connect_queue_song(self._on_queue_song)
        self._library_view.search_entry.connect("search-changed", self._on_search_changed)

        # SplitView: sidebar + content
        self._split_view = Adw.OverlaySplitView()
        self._split_view.set_sidebar(self._sidebar)
        self._split_view.set_content(self._library_view)
        self._split_view.set_min_sidebar_width(220)
        self._split_view.set_max_sidebar_width(280)
        self._split_view.set_vexpand(True)
        self._main_box.append(self._split_view)

        # Player bar at bottom
        self._player_bar = PlayerBar(player)
        self._player_bar.connect_toggle_mini(self._on_toggle_mini)
        self._player_bar.connect_show_equalizer(self._on_show_equalizer)
        self._player_bar.connect_toggle_fullscreen(self._toggle_fullscreen)
        self._player_bar.connect_toggle_sidebar(self._toggle_sidebar)
        self._player_bar.connect_navigate_album(self._on_navigate_to_album)
        self._player_bar.connect_toggle_lyrics(self._on_toggle_lyrics)
        self._main_box.append(self._player_bar)

        # Lyrics panel (hidden by default)
        self._lyrics_view = LyricsView()
        self._lyrics_view.set_visible(False)
        self._lyrics_view.set_size_request(-1, 320)
        self._main_box.append(self._lyrics_view)

        # Mini player (hidden initially)
        self._mini_player = MiniPlayer(player)
        self._mini_player.connect_restore_window(self._on_restore_from_mini)

        # Set up drag and drop
        self._setup_drag_drop()

        # Set up keyboard shortcuts
        self._setup_shortcuts()

        # Scan directory picker on startup
        self._check_library()

        # Connect player signals for MPRIS last.fm integration
        self.player.connect_song(self._on_player_song_changed)
        self.player.connect_position(self._on_player_position_changed)

        # Sync fullscreen button state when window state changes
        self.connect("notify::fullscreened", self._on_fullscreen_changed)

        # Configurar y arrancar FolderWatcher para directorios de música
        self._start_folder_watcher()
        self.connect("destroy", self._on_destroy)

    def _setup_css(self):
        css_provider = Gtk.CssProvider()
        css = """
        @define-color accent_bg_color #1DB954;
        @define-color accent_color #1DB954;
        @define-color accent_fg_color #ffffff;

        .navigation-sidebar {
            background-color: @view_bg_color;
            border-right: 1px solid @borders;
        }
        .navigation-sidebar headerbar {
            background: none;
            background-color: transparent;
            border-bottom: none;
            box-shadow: none;
        }
        .sidebar-row {
            border-radius: 99px;
            margin: 4px 12px;
            padding: 8px 16px;
        }
        .sidebar-row:selected {
            background-color: @accent_bg_color;
            color: #000000;
        }
        .player-bar {
            background-color: @window_bg_color;
            border-top: 1px solid @borders;
            padding: 10px 16px;
        }
        .album-grid, .artist-grid {
            margin: 16px;
        }
        .album-grid flowboxchild, .artist-grid flowboxchild {
            padding: 8px;
            border-radius: 12px;
            transition: all 0.2s ease;
        }
        .album-grid flowboxchild:hover, .artist-grid flowboxchild:hover {
            background-color: alpha(@accent_bg_color, 0.04);
        }
        .album-card, .artist-card {
            padding: 8px;
            background-color: transparent;
        }
        .album-card avatar, .artist-card avatar {
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            border-radius: 9999px;
        }
        .album-card:hover avatar, .artist-card:hover avatar {
            transform: scale(1.04);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.45);
        }
        .album-card-title, .artist-card-name {
            font-weight: bold;
            font-size: 13px;
            margin-top: 4px;
        }
        .album-card-subtitle, .artist-card-subtitle {
            font-size: 11px;
            color: alpha(currentColor, 0.6);
        }
        .album-play-btn {
            background-color: @accent_bg_color;
            color: #000000;
            border-radius: 99px;
            border: none;
            opacity: 0.0;
            transition: opacity 0.2s ease, transform 0.2s ease, background-color 0.2s ease;
        }
        .album-card:hover .album-play-btn {
            opacity: 1.0;
        }
        .album-play-btn:hover {
            background-color: #1ED760;
            transform: scale(1.1);
        }
        .genre-card {
            padding: 16px;
            border-radius: 12px;
            background-color: @card_bg_color;
            transition: all 0.2s ease;
        }
        .genre-card:hover {
            transform: scale(1.04);
            background-color: alpha(@accent_bg_color, 0.08);
        }
        .genre-icon-box {
            background-color: alpha(@accent_bg_color, 0.12);
            color: @accent_bg_color;
            padding: 8px;
            border-radius: 8px;
            margin-bottom: 8px;
        }
        .genre-name {
            font-weight: bold;
            font-size: 15px;
            margin-top: 4px;
        }
        .genre-count {
            font-size: 12px;
            color: alpha(currentColor, 0.6);
        }
        .song-row {
            border-radius: 8px;
            padding: 8px 16px;
            margin: 2px 8px;
            transition: background-color 0.2s ease;
        }
        .song-row:hover {
            background-color: alpha(@accent_bg_color, 0.04);
        }
        .song-row:selected {
            background-color: alpha(@accent_bg_color, 0.15);
        }
        .equalizer-slider {
            min-height: 120px;
        }
        .volume-button {
            min-width: 32px;
        }
        .mini-player {
            background-color: @window_bg_color;
        }
        .play-button-main {
            background-color: @accent_bg_color;
            color: #000000;
            border-radius: 50%;
            box-shadow: 0 4px 14px rgba(29, 185, 84, 0.3);
            transition: all 0.2s ease;
        }
        .play-button-main:hover {
            transform: scale(1.08);
            background-color: #1ED760;
            box-shadow: 0 6px 20px rgba(29, 185, 84, 0.45);
        }
        .green-deck-btn {
            background-color: @accent_bg_color;
            color: #000000;
            border-radius: 50%;
            box-shadow: 0 4px 14px rgba(29, 185, 84, 0.3);
            transition: all 0.2s ease;
        }
        .green-deck-btn:hover {
            transform: scale(1.08);
            background-color: #1ED760;
        }
        .now-playing-row {
            border-left: 3px solid @accent_bg_color;
            background-color: alpha(@accent_bg_color, 0.06);
        }
        scale.horizontal trough {
            min-height: 4px;
            border-radius: 2px;
            background-color: alpha(currentColor, 0.12);
        }
        scale.horizontal highlight {
            min-height: 4px;
            border-radius: 2px;
            background-color: @accent_bg_color;
        }
        scale.horizontal slider {
            min-height: 14px;
            min-width: 14px;
            border-radius: 50%;
            background-color: @accent_bg_color;
            box-shadow: 0 2px 6px rgba(29, 185, 84, 0.4);
        }
        .album-cover {
            border-radius: 6px;
        }
        .green-deck-header {
            background-color: @window_bg_color;
            border-bottom: 1px solid @borders;
        }
        .songs-list > row {
            border-radius: 8px;
            padding: 4px 12px;
            margin: 1px 8px;
            transition: background-color 0.15s ease;
        }
        .songs-list > row:hover {
            background-color: alpha(@accent_bg_color, 0.04);
        }
        .songs-list > row:selected {
            background-color: alpha(@accent_bg_color, 0.15);
        }
        .lyrics-line {
            font-size: 16px;
            padding: 4px 0;
            transition: all 0.3s ease;
        }
        .lyrics-line-inactive {
            color: alpha(@window_fg_color, 0.35);
        }
        .lyrics-line-active {
            color: @accent_bg_color;
            font-weight: bold;
            font-size: 18px;
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
        sidebar.add_css_class("navigation-sidebar")

        header = Adw.HeaderBar()
        header.add_css_class("green-deck-header")
        header.set_title_widget(Gtk.Label(label=""))  # Clear center title

        # Pack title label on the left (start)
        title_label = Gtk.Label(label="Soundwave")
        title_label.add_css_class("title")
        title_label.set_halign(Gtk.Align.START)
        title_label.set_margin_start(28)
        header.pack_start(title_label)

        # Pack collapse button first, then settings button, so they sit side-by-side at the end (right side)
        # of the sidebar header, leaving the start (left side) clear for system window controls.
        collapse_btn = Gtk.Button.new_from_icon_name("sidebar-hide-symbolic")
        collapse_btn.set_css_classes(["flat", "circular"])
        collapse_btn.set_tooltip_text("Colapsar barra lateral")
        collapse_btn.connect("clicked", lambda b: self._toggle_sidebar())
        collapse_btn.set_margin_end(12)
        header.pack_end(collapse_btn)

        settings_btn = Gtk.Button.new_from_icon_name("preferences-system-symbolic")
        settings_btn.set_css_classes(["flat", "circular"])
        settings_btn.set_tooltip_text("Ajustes")
        settings_btn.connect("clicked", lambda b: self._on_show_settings())
        header.pack_end(settings_btn)

        sidebar.append(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        sidebar.append(scrolled)

        self._sidebar_list = Gtk.ListBox()
        self._sidebar_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._sidebar_list.set_css_classes(["sidebar-list"])
        scrolled.set_child(self._sidebar_list)

        items = [
            ("audio-x-generic-symbolic", "Todas las canciones", "all"),
            ("media-optical-symbolic", "Álbumes", "albums"),
            ("avatar-default-symbolic", "Artistas", "artists"),
            ("folder-music-symbolic", "Géneros", "genres"),
        ]
        self._sidebar_count_labels = {}
        for icon_name, label, view_id in items:
            row = Adw.ActionRow()
            row.set_activatable(True)
            row.set_title(label)
            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(18)
            row.add_prefix(icon)
            row.set_css_classes(["sidebar-row"])
            row._view_id = view_id

            # Create a suffix label for the count
            count_label = Gtk.Label()
            count_label.add_css_class("dim-label")
            count_label.set_margin_end(6)
            row.add_suffix(count_label)
            self._sidebar_count_labels[view_id] = count_label

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

    def _setup_drag_drop(self):
        drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop_target.connect("accept", self._on_drag_accept)
        drop_target.connect("drop", self._on_drag_drop)
        self.add_controller(drop_target)

    def _on_drag_accept(self, drop_target, drop):
        return True

    def _on_drag_drop(self, drop_target, value, x, y):
        file = value
        if not file:
            return False
        path = file.get_path()
        if not path:
            return False
        from pathlib import Path
        p = Path(path)
        if p.is_dir():
            self._start_scan(p)
        elif p.suffix.lower() in (".mp3", ".flac", ".ogg", ".m4a", ".wav", ".wma", ".opus"):
            self._start_scan(p.parent)
        return True

    def _setup_shortcuts(self):
        ctrl = Gtk.ShortcutController()
        self.add_controller(ctrl)

        shortcuts = [
            ("space", lambda: self._player_bar._on_play_pause()),
            ("<Control>Right", lambda: self.player.next()),
            ("<Control>Left", lambda: self.player.previous()),
            ("<Control>f", lambda: self._library_view.search_entry.grab_focus()),
            ("Escape", lambda: self._library_view.search_entry.set_text("")),
            ("<Control>m", lambda: self._on_toggle_mini()),
            ("<Control>e", lambda: self._on_show_equalizer()),
            ("F11", lambda: self._toggle_fullscreen()),
            ("<Control>b", lambda: self._toggle_sidebar()),
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
        else:
            self._refresh_library()

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
        if hasattr(Gtk, "FileDialog"):
            dialog = Gtk.FileDialog.new()
            dialog.set_title("Seleccionar carpeta de música")

            def on_folder_selected(dialog, result, *args):
                try:
                    file = dialog.select_folder_finish(result)
                    if file:
                        self._start_scan(Path(file.get_path()))
                except GLib.Error as e:
                    print("Selección de carpeta cancelada o fallida:", e)

            dialog.select_folder(self, None, on_folder_selected)
        else:
            dialog = Gtk.FileChooserNative.new(
                title="Seleccionar carpeta de música",
                parent=self,
                action=Gtk.FileChooserAction.SELECT_FOLDER,
                accept_label="Seleccionar",
                cancel_label="Cancelar"
            )
            self._file_chooser = dialog

            def on_response(dialog, response_id):
                if response_id == Gtk.ResponseType.ACCEPT:
                    file = dialog.get_file()
                    if file:
                        self._start_scan(Path(file.get_path()))
                self._file_chooser = None

            dialog.connect("response", on_response)
            dialog.show()

    def _start_scan(self, directory: Path):
        # Guardar la carpeta seleccionada en la configuración para el watcher y futuros escaneos
        from soundwave.library.config import load_settings, save_setting
        settings = load_settings()
        dirs = settings.get("music_directories", [])
        dir_str = str(directory.resolve())
        if dir_str not in dirs:
            dirs.append(dir_str)
            save_setting("music_directories", dirs)

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
        # Reiniciar el watcher para que empiece a vigilar la nueva carpeta y subcarpetas
        self._start_folder_watcher()

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
        try:
            genres_count = self.db.conn.execute(
                "SELECT COUNT(DISTINCT CASE WHEN genre = '' OR genre IS NULL THEN 'Sin género' ELSE genre END) FROM songs"
            ).fetchone()[0]
        except Exception:
            genres_count = 0

        if hasattr(self, "_sidebar_count_labels"):
            self._sidebar_count_labels["all"].set_text(str(stats.get("total_songs", 0)))
            self._sidebar_count_labels["albums"].set_text(str(stats.get("total_albums", 0)))
            self._sidebar_count_labels["artists"].set_text(str(stats.get("total_artists", 0)))
            self._sidebar_count_labels["genres"].set_text(str(genres_count))

    # --- Sidebar navigation ---
    def _on_sidebar_row_activated(self, listbox, row):
        view_id = getattr(row, "_view_id", "all")
        self._current_view = view_id
        self._library_view.show_view(view_id)

    # --- Search ---
    def _on_search_changed(self, entry):
        query = entry.get_text().strip()
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

    def _on_player_position_changed(self, pos):
        if self._lyrics_view.get_visible():
            self._lyrics_view.update_position(pos.current_seconds * 1000)
        self._check_scrobble(pos)

    def _check_scrobble(self, pos):
        if not self._lastfm or not self._lastfm.connected:
            return
        song = self.player.get_current_song()
        if not song or song.id == self._scrobbled_song_id:
            return
        current_s = pos.current_seconds
        duration_s = pos.duration_seconds
        if duration_s <= 0:
            return
        half_duration = duration_s / 2
        if current_s >= min(half_duration, 240):
            self._lastfm.scrobble(
                song.display_artist, song.display_title,
                song.display_album, int(song.duration)
            )
            self._scrobbled_song_id = song.id

    def _on_player_song_changed(self, song: Optional[Song]):
        self._scrobbled_song_id = None
        if song and self._lastfm and self._lastfm.connected:
            self._lastfm.now_playing(
                song.display_artist, song.display_title, song.display_album,
                int(song.duration)
            )
        self._library_view.highlight_song(song)
        art_path = get_art_path(song.id, self.db) if song else None
        self._player_bar.set_artwork_from_path(art_path)
        self._mini_player.set_artwork_from_path(art_path)
        if self._lyrics_view.get_visible() and song:
            self._lyrics_view.load_song(song)

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

    # --- Fullscreen ---
    def _toggle_fullscreen(self):
        if self.is_fullscreen():
            self.unfullscreen()
        else:
            self.fullscreen()

    def _on_fullscreen_changed(self, *args):
        self._player_bar.set_fullscreen_state(self.is_fullscreen())

    # --- Sidebar toggle ---
    def _toggle_sidebar(self):
        shown = self._split_view.get_show_sidebar()
        self._split_view.set_show_sidebar(not shown)
        self._player_bar.set_sidebar_state(not shown)

    # --- Navigation from player bar ---
    def _on_navigate_to_album(self):
        song = self.player.get_current_song()
        if not song:
            return
        album_name = song.display_album
        album_artist = song.album_artist or song.artist or ""
        albums = self.db.get_albums()
        for a in albums:
            if a["album"] == album_name and (
                not album_artist or a.get("album_artist", "") == album_artist
            ):
                self._library_view._show_album_songs(a)
                break

    # --- Lyrics ---
    def _on_toggle_lyrics(self):
        visible = not self._lyrics_view.get_visible()
        self._lyrics_view.set_visible(visible)
        if visible and self.player.get_current_song():
            self._lyrics_view.load_song(self.player.get_current_song())

    # --- Equalizer ---
    def _on_show_equalizer(self):
        dialog = EqualizerDialog(self.player, self)
        dialog.present()

    # --- Settings ---
    def _on_show_settings(self):
        dialog = SettingsDialog(self, self._lastfm)
        dialog.present()

    def set_lastfm(self, lastfm):
        self._lastfm = lastfm

    def get_player_bar(self):
        return self._player_bar

    # --- Folder Watcher & Destructor ---
    def _start_folder_watcher(self):
        from soundwave.library.watcher import FolderWatcher
        from soundwave.library.config import load_settings

        if self._watcher:
            self._watcher.stop()

        def on_watcher_event(filepath: Path, event: str):
            print(f"[Watcher] Evento de sistema de archivos '{event}': {filepath}")
            if event in ("created", "modified"):
                self.scanner.scan_single_file(filepath)
            elif event == "deleted":
                self.db.remove_song_by_path(str(filepath))
            
            # Refrescar biblioteca en la UI
            GLib.idle_add(self._refresh_library)

        self._watcher = FolderWatcher(on_watcher_event)
        
        settings = load_settings()
        dirs = settings.get("music_directories", [])
        watch_paths = [Path(d) for d in dirs if Path(d).exists()]
        if watch_paths:
            self._watcher.start_watching(watch_paths)

    def _on_destroy(self, *args):
        if self._watcher:
            self._watcher.stop()
