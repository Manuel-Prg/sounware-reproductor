import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, Pango, GLib, Gio

from pathlib import Path
from typing import Optional

from soundwave.library.database import Song, UNKNOWN_ARTIST, UNKNOWN_ALBUM, NO_GENRE
from soundwave.library.album_art import get_art_path, CACHE_DIR as ART_CACHE_DIR


class LibraryCardsMixin:
    def _build_song_row(self, song: Song, playlist_id: Optional[int] = None) -> Adw.ActionRow:
        row = Adw.ActionRow()
        row.set_activatable(True)
        row.set_title(GLib.markup_escape_text(song.display_title))
        row.set_subtitle(GLib.markup_escape_text(f"{song.display_artist} · {song.display_album}"))
        
        # Add Favorite toggle button
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

        # Context menu button for other actions (Add to playlist, etc)
        menu_btn = Gtk.Button.new_from_icon_name("view-more-symbolic")
        menu_btn.set_valign(Gtk.Align.CENTER)
        menu_btn.set_css_classes(["flat", "circular"])
        menu_btn.set_tooltip_text("Más opciones")
        menu_btn.connect("clicked", lambda b, s=song: self._show_song_menu(b, s))
        row.add_suffix(menu_btn)

        # If we are viewing inside a custom playlist, add a "remove from playlist" button
        if playlist_id is not None:
            remove_btn = Gtk.Button.new_from_icon_name("list-remove-symbolic")
            remove_btn.set_valign(Gtk.Align.CENTER)
            remove_btn.set_css_classes(["flat", "circular"])
            remove_btn.set_tooltip_text("Quitar de esta lista")
            
            def on_remove_clicked(btn, pid=playlist_id, sid=song.id):
                self.db.remove_from_playlist(pid, sid)
                toast = Adw.Toast.new("Canción quitada de la lista")
                self.add_toast(toast)
                # Re-fetch updated playlist and refresh view
                updated_pl = None
                for pl in self.db.get_playlists():
                    if pl.id == pid:
                        updated_pl = pl
                        break
                if updated_pl:
                    self._show_playlist_songs(updated_pl)
                else:
                    self.show_view("playlists")
                    
            remove_btn.connect("clicked", on_remove_clicked)
            row.add_suffix(remove_btn)

        if song.duration:
            m, s = divmod(int(song.duration), 60)
            row.add_suffix(Gtk.Label(label=f"{m}:{s:02d}"))

        row._song = song
        return row

    def _build_album_card(self, album: dict) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_size_request(140, -1)
        box.add_css_class("album-card")

        overlay = Gtk.Overlay()

        # Try to find art for this album (check cache first, then DB)
        songs = self.db.get_songs_by_album(album["album"], album.get("album_artist", ""))
        art_texture = None
        for s in songs:
            for ext in (".jpg", ".png"):
                cached = ART_CACHE_DIR / f"{s.id}{ext}"
                if cached.exists():
                    art_texture = Gdk.Texture.new_from_filename(str(cached))
                    break
            if art_texture:
                break
        if not art_texture:
            for s in songs:
                art_path = get_art_path(s.id, self.db) if s.id is not None else None
                if art_path and art_path.exists():
                    art_texture = Gdk.Texture.new_from_filename(str(art_path))
                    break

        avatar = Adw.Avatar(size=120, text=album["album"], show_initials=True)
        if art_texture:
            avatar.set_custom_image(art_texture)

        avatar.set_halign(Gtk.Align.CENTER)
        overlay.set_child(avatar)

        # Floating Play Button in the center (visible on hover)
        play_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        play_btn.set_css_classes(["album-play-btn", "circular"])
        play_btn.set_halign(Gtk.Align.CENTER)
        play_btn.set_valign(Gtk.Align.CENTER)
        play_btn.set_size_request(44, 44)
        album_songs = songs
        play_btn.connect("clicked", lambda b, a=album, s=album_songs: (
            s and [cb(s[0], s) for cb in self._play_song_cbs]
        ))
        overlay.add_overlay(play_btn)

        box.append(overlay)

        # Title
        title = Gtk.Label(label=album["album"])
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.set_max_width_chars(16)
        title.set_xalign(0.5)
        title.add_css_class("album-card-title")
        box.append(title)

        # Subtitle (Artist)
        artist_name = album.get("album_artist", "") or UNKNOWN_ARTIST
        artist = Gtk.Label(label=artist_name)
        artist.set_ellipsize(Pango.EllipsizeMode.END)
        artist.set_max_width_chars(18)
        artist.set_xalign(0.5)
        artist.add_css_class("album-card-subtitle")
        box.append(artist)

        # Click handler - play album (left click) or context menu (right click)
        gesture = Gtk.GestureClick()
        gesture.set_button(0)  # Listen to all mouse buttons
        gesture.connect("pressed", lambda g, n, x, y, a=album: self._on_album_card_pressed(g, n, x, y, a))
        box.add_controller(gesture)

        return box

    def _build_artist_card(self, artist: dict) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.set_size_request(140, -1)
        card.add_css_class("artist-card")

        # Let's find an album cover to use as the artist's avatar image
        songs = self.db.get_songs_by_artist(artist["artist"])
        art_texture = None
        for s in songs:
            art_path = get_art_path(s.id, self.db) if s.id is not None else None
            if art_path and art_path.exists():
                art_texture = Gdk.Texture.new_from_filename(str(art_path))
                break

        avatar = Adw.Avatar(size=120, text=artist["artist"], show_initials=True)
        if art_texture:
            avatar.set_custom_image(art_texture)

        avatar.set_halign(Gtk.Align.CENTER)
        card.append(avatar)

        # Name
        name = Gtk.Label(label=artist["artist"])
        name.set_ellipsize(Pango.EllipsizeMode.END)
        name.set_max_width_chars(16)
        name.set_xalign(0.5)
        name.add_css_class("artist-card-name")
        card.append(name)

        # Subtitle
        subtitle_text = f"{artist['album_count']} álb. · {artist['song_count']} canc."
        subtitle = Gtk.Label(label=subtitle_text)
        subtitle.set_ellipsize(Pango.EllipsizeMode.END)
        subtitle.set_max_width_chars(18)
        subtitle.set_xalign(0.5)
        subtitle.add_css_class("artist-card-subtitle")
        card.append(subtitle)

        # Click gesture to open artist's songs
        gesture = Gtk.GestureClick()
        gesture.connect("pressed", lambda g, n, x, y, name=artist["artist"]: self._on_artist_selected_name(name))
        card.add_controller(gesture)

        return card

    def _build_genre_card(self, g: dict) -> Gtk.Widget:
        import hashlib
        
        # Gtk.Overlay allows us to overlay text on top of a background image/icon
        overlay = Gtk.Overlay()
        overlay.add_css_class("genre-card")
        
        # Calculate a stable hash based on the genre name to pick a gradient index (0-7)
        genre_name = g["genre"]
        genre_hash = int(hashlib.md5(genre_name.encode("utf-8")).hexdigest(), 16)
        gradient_idx = genre_hash % 8
        
        if genre_name == NO_GENRE or genre_name == "Sin género":
            overlay.add_css_class("genre-card-no-genre")
        else:
            overlay.add_css_class(f"genre-card-grad-{gradient_idx}")
            
        overlay.set_size_request(160, 110)
        
        # Decorative semi-transparent icon in the bottom right corner
        icon = Gtk.Image.new_from_icon_name("folder-music-symbolic")
        icon.set_pixel_size(64)
        icon.set_halign(Gtk.Align.END)
        icon.set_valign(Gtk.Align.END)
        icon.add_css_class("genre-card-bg-icon")
        overlay.add_overlay(icon)
        
        # Vertical Box to hold titles with proper margins
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_valign(Gtk.Align.FILL)
        
        # Genre Name (Bold, white/contrasted, with custom css class)
        name_label = Gtk.Label(label=genre_name)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_max_width_chars(14)
        name_label.set_xalign(0)
        name_label.add_css_class("genre-card-name")
        content.append(name_label)

        # Song Count (Smaller, semi-transparent label)
        count_label = Gtk.Label(label=f"{g['count']} canciones")
        count_label.set_xalign(0)
        count_label.add_css_class("genre-card-count")
        content.append(count_label)
        
        overlay.set_child(content)

        # Click handler
        gesture = Gtk.GestureClick()
        gesture.connect("pressed", lambda gesture, n_press, x, y, name=genre_name: self._on_genre_selected(name))
        overlay.add_controller(gesture)

        return overlay

    # --- Event handlers ---
    def _on_album_card_pressed(self, gesture, n_press, x, y, album):
        button = gesture.get_current_button()
        if button == 1:  # Left click
            self._on_album_clicked(album)
        elif button == 3:  # Right click
            self._show_album_context_menu(gesture, album)

    def _show_album_context_menu(self, gesture, album):
        popover = Gtk.Popover()
        popover.set_parent(gesture.get_widget())

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        
        play_btn = Gtk.Button(label="Reproducir álbum")
        play_btn.set_has_frame(False)
        play_btn.set_halign(Gtk.Align.START)
        play_btn.connect("clicked", lambda b: (popover.popdown(), self._on_album_clicked(album)))
        box.append(play_btn)

        change_cover_btn = Gtk.Button(label="Cambiar carátula...")
        change_cover_btn.set_has_frame(False)
        change_cover_btn.set_halign(Gtk.Align.START)
        change_cover_btn.connect("clicked", lambda b: (popover.popdown(), self._prompt_custom_cover(album)))
        box.append(change_cover_btn)

        popover.set_child(box)
        popover.popup()

    def _prompt_custom_cover(self, album):
        if hasattr(Gtk, "FileDialog"):
            dialog = Gtk.FileDialog.new()
            dialog.set_title("Seleccionar carátula para el álbum")
            
            filter_img = Gtk.FileFilter()
            filter_img.set_name("Imágenes")
            filter_img.add_mime_type("image/jpeg")
            filter_img.add_mime_type("image/png")
            
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(filter_img)
            dialog.set_filters(filters)

            def on_file_selected(dialog, result, *args):
                try:
                    file = dialog.open_finish(result)
                    if file:
                        self._apply_custom_cover(album, Path(file.get_path()))
                except GLib.Error as e:
                    print("Selección de carátula cancelada o fallida:", e)
            dialog.open(self.get_root(), None, on_file_selected)
        else:
            dialog = Gtk.FileChooserNative.new(
                title="Seleccionar carátula para el álbum",
                parent=self.get_root(),
                action=Gtk.FileChooserAction.OPEN,
                accept_label="Seleccionar",
                cancel_label="Cancelar"
            )
            filter_img = Gtk.FileFilter()
            filter_img.set_name("Imágenes")
            filter_img.add_mime_type("image/jpeg")
            filter_img.add_mime_type("image/png")
            dialog.add_filter(filter_img)

            self._file_chooser = dialog
            def on_response(dialog, response_id):
                if response_id == Gtk.ResponseType.ACCEPT:
                    file = dialog.get_file()
                    if file:
                        self._apply_custom_cover(album, Path(file.get_path()))
                self._file_chooser = None
            dialog.connect("response", on_response)
            dialog.show()

    def _apply_custom_cover(self, album, file_path: Path):
        try:
            img_bytes = file_path.read_bytes()
            songs = self.db.get_songs_by_album(album["album"], album.get("album_artist", ""))
            if not songs:
                return

            ART_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            for s in songs:
                if s.id is not None:
                    cache_path = ART_CACHE_DIR / f"{s.id}.jpg"
                    cache_path.write_bytes(img_bytes)
                    from soundwave.library.album_art import _export_art_to_tmp
                    _export_art_to_tmp(s.id, cache_path)

            first_song_path = Path(songs[0].filepath)
            album_dir = first_song_path.parent
            if album_dir.exists():
                local_cover = album_dir / "cover.jpg"
                try:
                    local_cover.write_bytes(img_bytes)
                except Exception as e:
                    print(f"No se pudo guardar la carátula local en {album_dir}: {e}")

            self._populate_albums()

            root = self.get_root()
            if root and hasattr(root, "add_toast"):
                root.add_toast("Carátula aplicada al álbum correctamente")
                
            # If current playing song is in this album, update art
            if self.player.current_song:
                curr = self.player.current_song
                if curr.album == album["album"]:
                    if root and hasattr(root, "refresh_current_artwork"):
                        root.refresh_current_artwork()
        except Exception as e:
            print(f"Error al aplicar la carátula personalizada: {e}")

    # --- Playlist Support ---
