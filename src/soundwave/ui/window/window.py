import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio, Gdk

from pathlib import Path
from typing import Optional

from soundwave.library.database.database import Database, Song
from soundwave.library.scanner.scanner import MusicScanner
from soundwave.library.metadata.album_art import get_art_path
from soundwave.player.engine import Player, PlayerState
from soundwave.ui.player.player_bar import PlayerBar
from soundwave.ui.library.library_view import LibraryView
from soundwave.ui.components.search_bar import SearchBar
from soundwave.ui.player.equalizer import EqualizerDialog
from soundwave.ui.player.mini_player import MiniPlayer
from soundwave.ui.settings import SettingsDialog
from soundwave.ui.lyrics_view import LyricsView
from soundwave.ui.window.window_styles import setup_window_css
from soundwave.ui.window.window_sidebar import WindowSidebarMixin
from soundwave.ui.window.window_library_scan import WindowLibraryScanMixin


class SoundwaveWindow(Adw.ApplicationWindow, WindowSidebarMixin, WindowLibraryScanMixin):
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
        self._player_bar = PlayerBar(player, db, self._lastfm)
        self._player_bar.connect_toggle_mini(self._on_toggle_mini)
        self._player_bar.connect_show_equalizer(self._on_show_equalizer)
        self._player_bar.connect_toggle_fullscreen(self._toggle_fullscreen)
        self._player_bar.connect_toggle_sidebar(self._toggle_sidebar)
        self._player_bar.connect_navigate_album(self._on_toggle_visualizer)
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

        # Scan directory picker on startup (onboarding checked first)
        GLib.idle_add(self._check_onboarding)

        # Connect player signals for MPRIS last.fm integration
        self.player.connect_song(self._on_player_song_changed)
        self.player.connect_position(self._on_player_position_changed)
        self.player.connect_queue(self._on_player_queue_changed)

        # Sync fullscreen button state when window state changes
        self.connect("notify::fullscreened", self._on_fullscreen_changed)

        # Configurar y arrancar FolderWatcher para directorios de música
        self._start_folder_watcher()
        self._run_silent_background_scan()
        self.connect("destroy", self._on_destroy)

        # Prompt user on first run about auto album art download
        GLib.idle_add(self._maybe_prompt_art_download)

    def apply_accent_color(self, hex_code: str):
        self._setup_css()

    def _setup_css(self):
        provider = getattr(self, "_css_provider", None)
        self._css_provider = setup_window_css(self, provider)

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

        try:
            playlists_count = len(self.db.get_playlists())
        except Exception:
            playlists_count = 0

        if hasattr(self, "_sidebar_count_labels"):
            self._sidebar_count_labels["all"].set_text(str(stats.get("total_songs", 0)))
            
            queue_len = len(self.player.get_queue())
            self._sidebar_count_labels["queue"].set_text(str(queue_len) if queue_len > 0 else "")

            self._sidebar_count_labels["albums"].set_text(str(stats.get("total_albums", 0)))
            self._sidebar_count_labels["artists"].set_text(str(stats.get("total_artists", 0)))
            self._sidebar_count_labels["genres"].set_text(str(genres_count))
            self._sidebar_count_labels["playlists"].set_text(str(playlists_count))

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
        song = self.player.get_current_song()
        if not song or song.id == self._scrobbled_song_id:
            return
        current_s = pos.current_seconds
        duration_s = pos.duration_seconds
        if duration_s <= 0:
            return
        half_duration = duration_s / 2
        if current_s >= min(half_duration, 240):
            # Update local play count and last played timestamp
            self.db.update_play_count(song.id)

            # Scrobble to Last.fm if connected
            if self._lastfm and self._lastfm.connected:
                self._lastfm.scrobble(
                    song.display_artist, song.display_title,
                    song.display_album, int(song.duration)
                )
            self._scrobbled_song_id = song.id

    def _on_player_queue_changed(self, queue):
        GLib.idle_add(self._refresh_sidebar_counts)

    def _on_player_song_changed(self, song: Optional[Song]):
        self._scrobbled_song_id = None
        if song and self._lastfm and self._lastfm.connected:
            self._lastfm.now_playing(
                song.display_artist, song.display_title, song.display_album,
                int(song.duration)
            )
        self._library_view.highlight_song(song)
        art_path = get_art_path(song.id, self.db) if (song and song.id is not None) else None
        self._player_bar.set_artwork_from_path(art_path)
        self._mini_player.set_artwork_from_path(art_path)
        if self._lyrics_view.get_visible() and song:
            self._lyrics_view.load_song(song)

        # If no cover found and auto-download is enabled, fetch it in the background
        if song and song.id is not None and art_path is None:
            from soundwave.library.config.config import load_settings
            if load_settings().get("download_missing_art", False):
                self._start_art_download_for_song(song.id)

        if not song and self._current_view == "visualizer":
            # Switch back to target view (e.g. previous view or "all")
            target_view = getattr(self, "_previous_view", "all")
            if target_view == "visualizer":
                target_view = "all"
            idx = 0
            while True:
                row = self._sidebar_list.get_row_at_index(idx)
                if not row:
                    break
                if getattr(row, "_view_id", "") == target_view:
                    self._sidebar_list.select_row(row)
                    self._on_sidebar_row_activated(self._sidebar_list, row)
                    break
                idx += 1

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

    def _on_toggle_visualizer(self):
        if not self.player.get_current_song():
            return

        if self._current_view == "visualizer":
            target_view = getattr(self, "_previous_view", "all")
            if target_view == "visualizer":
                target_view = "all"

            idx = 0
            while True:
                row = self._sidebar_list.get_row_at_index(idx)
                if not row:
                    break
                if getattr(row, "_view_id", "") == target_view:
                    self._sidebar_list.select_row(row)
                    self._on_sidebar_row_activated(self._sidebar_list, row)
                    break
                idx += 1
        else:
            self._previous_view = self._current_view
            self._current_view = "visualizer"
            self._sidebar_list.select_row(None)
            self._library_view.show_view("visualizer")

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
        self._player_bar.set_lastfm(lastfm)

    def get_player_bar(self):
        return self._player_bar

    # --- Folder Watcher & Destructor ---
    def _start_folder_watcher(self):
        from soundwave.library.scanner.watcher import FolderWatcher
        from soundwave.library.config.config import load_settings

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

    def _run_silent_background_scan(self):
        from soundwave.library.config.config import load_settings
        settings = load_settings()
        dirs = settings.get("music_directories", [])
        if not dirs:
            return
        
        directories = [Path(d) for d in dirs if Path(d).exists()]
        if not directories:
            return

        def scan_task():
            try:
                # Silent scan in the background
                added, skipped = self.scanner.scan_directories(directories)
                removed = self.scanner.remove_missing_files()
                if added > 0 or removed > 0:
                    GLib.idle_add(self._refresh_library)
            except Exception as e:
                print(f"[Silent Startup Scan] Error: {e}")

        import threading
        thread = threading.Thread(target=scan_task, daemon=True)
        thread.start()

    def _on_destroy(self, *args):
        if self._watcher:
            self._watcher.stop()

    # ──────────────────────────────────────────────────────────
    # Album art auto-download
    # ──────────────────────────────────────────────────────────

    def _maybe_prompt_art_download(self):
        from soundwave.library.config.config import load_settings, save_setting
        settings = load_settings()
        if "download_missing_art" in settings:
            return False  # Already configured, no prompt needed

        dialog = Adw.MessageDialog(transient_for=self, modal=True)
        dialog.set_heading("Descargar carátulas faltantes")
        dialog.set_body(
            "¿Deseas que Soundwave busque automáticamente en internet las carátulas "
            "de álbumes que no las tengan en tus archivos?\n\n"
            "También puedes activar o desactivar esto más tarde desde Ajustes."
        )
        dialog.add_response("no", "No, gracias")
        dialog.add_response("yes", "Sí, buscar")
        dialog.set_response_appearance("yes", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("yes")
        dialog.set_close_response("no")

        def on_response(dialog, response):
            enabled = response == "yes"
            save_setting("download_missing_art", enabled)
            if enabled:
                self.add_toast("Descarga de carátulas activada. Se buscará al reproducir canciones.")
            dialog.destroy()

        dialog.connect("response", on_response)
        dialog.present()
        return False  # Don't repeat

    def _start_art_download_for_song(self, song_id: int):
        import threading
        db_path = self.db.db_path

        def do_download():
            try:
                from soundwave.library.metadata.album_art import download_and_cache_album_art
                from soundwave.library.database.database import Database
                thread_db = Database(db_path)
                try:
                    art_path = download_and_cache_album_art(song_id, thread_db)
                finally:
                    thread_db.close()
                if art_path and art_path.exists():
                    GLib.idle_add(self._on_art_downloaded_for_song, song_id, art_path)
            except Exception as e:
                print(f"[Window] Error descargando carátula: {e}")
        threading.Thread(target=do_download, daemon=True).start()

    def _on_art_downloaded_for_song(self, song_id: int, art_path):
        current_song = self.player.get_current_song()
        if current_song and current_song.id == song_id:
            self._player_bar.set_artwork_from_path(art_path)
            self._mini_player.set_artwork_from_path(art_path)
            if getattr(self._library_view, "_visualizer_view", None) is not None:
                self._library_view._visualizer_view.update_song(current_song)
        self._library_view._populate_albums()
        return False

    def add_toast(self, message: str):
        toast = Adw.Toast.new(message)
        toast.set_timeout(4)
        try:
            self._library_view._toast_overlay.add_toast(toast)
        except Exception as e:
            print(f"[Toast] {message} (no se pudo mostrar: {e})")

    def refresh_current_artwork(self):
        song = self.player.get_current_song()
        if song and song.id is not None:
            from soundwave.library.metadata.album_art import get_art_path
            art_path = get_art_path(song.id, self.db)
            self._player_bar.set_artwork_from_path(art_path)
            self._mini_player.set_artwork_from_path(art_path)
            if getattr(self._library_view, "_visualizer_view", None) is not None:
                self._library_view._visualizer_view.update_song(song)

    def _check_onboarding(self):
        from soundwave.library.config.config import load_settings
        settings = load_settings()
        if not settings.get("onboarding_completed", False):
            from soundwave.ui.window.onboarding import OnboardingWindow
            dialog = OnboardingWindow(self)
            dialog.present()
        else:
            self._check_library()
        return False
