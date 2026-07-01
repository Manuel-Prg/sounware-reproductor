import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, Pango, GLib, Gio, GObject

from pathlib import Path
from typing import Optional

from soundwave.library.database.database import Song, UNKNOWN_ARTIST, UNKNOWN_ALBUM, NO_GENRE
from soundwave.library.metadata.album_art import get_art_path, CACHE_DIR as ART_CACHE_DIR


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

        # If we are viewing inside a custom playlist, add drag handle and remove button
        if playlist_id is not None:
            # 1. Add drag handle on the left
            handle_img = Gtk.Image.new_from_icon_name("list-drag-handle-symbolic")
            handle_img.set_valign(Gtk.Align.CENTER)
            handle_img.add_css_class("dim-label")
            row.add_prefix(handle_img)
            
            # 2. Attach DragSource to the handle
            drag_source = Gtk.DragSource.new()
            drag_source.set_actions(Gdk.DragAction.MOVE)
            
            def on_drag_prepare(source, x, y, r=row):
                self._dragged_row = r
                return Gdk.ContentProvider.new_for_value("row")
            drag_source.connect("prepare", on_drag_prepare)
            
            def on_drag_cancel(source, drag, reason):
                self._dragged_row = None
                return False
            drag_source.connect("drag-cancel", on_drag_cancel)
            
            handle_img.add_controller(drag_source)
            
            # 3. Attach DropTarget to the whole action row
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
            drop_target.connect("enter", on_enter)
            
            def on_drop(target, value, x, y, target_row=row):
                listbox = target_row.get_parent()
                if listbox:
                    song_ids = []
                    child = listbox.get_first_child()
                    while child:
                        s = getattr(child, "_song", None)
                        if s:
                            song_ids.append(s.id)
                        child = child.get_next_sibling()
                    
                    # Update DB
                    self.db.reorder_playlist(playlist_id, song_ids)
                    
                    # Update position cache
                    self._playlist_pos_cache = {sid: idx for idx, sid in enumerate(song_ids)}
                    self._playlist_pos_cache_id = playlist_id
                    
                    # Update current list of songs
                    new_all_songs = []
                    for sid in song_ids:
                        s = self.db.get_song(sid)
                        if s:
                            new_all_songs.append(s)
                    self._all_songs = new_all_songs
                    
                    self._dragged_row = None
                    return True
                return False
            drop_target.connect("drop", on_drop)
            row.add_controller(drop_target)

            # 4. Remove button
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
        box.set_valign(Gtk.Align.START)

        overlay = Gtk.Overlay()
        overlay.set_halign(Gtk.Align.CENTER)
        overlay.set_valign(Gtk.Align.CENTER)

        # Try to find art for this album using representative_song_id directly (extremely fast)
        art_texture = None
        rep_id = album.get("representative_song_id")
        if rep_id is not None:
            # Check cache first
            for ext in (".jpg", ".png"):
                cached = ART_CACHE_DIR / f"{rep_id}{ext}"
                if cached.exists():
                    try:
                        art_texture = Gdk.Texture.new_from_filename(str(cached))
                        break
                    except Exception:
                        pass
            # If not in cache, check DB
            if not art_texture:
                try:
                    art_path = get_art_path(rep_id, self.db)
                    if art_path and art_path.exists():
                        art_texture = Gdk.Texture.new_from_filename(str(art_path))
                except Exception:
                    pass

        # Get view mode
        view_mode = getattr(self, "_album_view_mode", "circle")

        if view_mode == "grid":
            if art_texture:
                img_container = Gtk.Box()
                img_container.set_size_request(120, 120)
                img_container.set_halign(Gtk.Align.CENTER)
                img_container.set_valign(Gtk.Align.CENTER)
                img_container.add_css_class("album-cover-container")
                
                img = Gtk.Image.new_from_paintable(art_texture)
                img.set_size_request(120, 120)
                img.set_halign(Gtk.Align.CENTER)
                img.set_valign(Gtk.Align.CENTER)
                img_container.append(img)
                
                provider = Gtk.CssProvider()
                provider.load_from_string(".album-cover-container { border-radius: 8px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3); transition: transform 0.2s ease, box-shadow 0.2s ease; }")
                img_container.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                overlay.set_child(img_container)
            else:
                fallback = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                fallback.set_size_request(120, 120)
                fallback.set_halign(Gtk.Align.CENTER)
                fallback.set_valign(Gtk.Align.CENTER)
                fallback.add_css_class("album-fallback-square")
                
                initials = album["album"][:2] if album["album"] else "?"
                lbl = Gtk.Label(label=initials.upper())
                lbl.set_halign(Gtk.Align.CENTER)
                lbl.set_valign(Gtk.Align.CENTER)
                lbl.set_hexpand(True)
                lbl.set_vexpand(True)
                fallback.append(lbl)
                
                import hashlib
                colors = ["#FF512F", "#3cba92", "#ee0979", "#11998e", "#E94057", "#9733EE", "#1f4037", "#00c6ff"]
                h = int(hashlib.md5(album["album"].encode("utf-8")).hexdigest(), 16)
                bg_color = colors[h % len(colors)]
                
                provider = Gtk.CssProvider()
                provider.load_from_string(f".album-fallback-square {{ background-color: {bg_color}; color: #ffffff; border-radius: 8px; font-weight: 800; font-size: 28px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3); transition: transform 0.2s ease, box-shadow 0.2s ease; }}")
                fallback.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                overlay.set_child(fallback)
        else:
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
        
        def on_play_clicked(btn, a=album):
            album_songs = self.db.get_songs_by_album(a["album"], a.get("album_artist", ""))
            if album_songs:
                first = album_songs[0]
                for cb in self._play_song_cbs:
                    cb(first, album_songs)
                    
        play_btn.connect("clicked", on_play_clicked)
        overlay.add_overlay(play_btn)

        box.append(overlay)

        # Title
        title = Gtk.Label(label=album["album"])
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.set_max_width_chars(16)
        title.set_lines(1)
        title.set_xalign(0.5)
        title.add_css_class("album-card-title")
        box.append(title)

        # Subtitle (Artist)
        artist_name = album.get("album_artist", "")
        if artist_name == UNKNOWN_ARTIST:
            artist_name = "Artista desconocido"
        artist = Gtk.Label(label=artist_name)
        artist.set_ellipsize(Pango.EllipsizeMode.END)
        artist.set_max_width_chars(18)
        artist.set_lines(1)
        artist.set_xalign(0.5)
        artist.add_css_class("album-card-subtitle")
        box.append(artist)

        # Click handler
        gesture = Gtk.GestureClick()
        gesture.set_button(0)  # Listen to all mouse buttons
        gesture.connect("pressed", lambda g, n, x, y, a=album: self._on_album_card_pressed(g, n, x, y, a))
        box.add_controller(gesture)

        return box

    def _build_artist_card(self, artist: dict) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.set_size_request(140, -1)
        card.add_css_class("artist-card")
        card.set_valign(Gtk.Align.START)

        # Find artist cover using representative_song_id directly (extremely fast)
        art_texture = None
        rep_id = artist.get("representative_song_id")
        if rep_id is not None:
            # Check cache first
            for ext in (".jpg", ".png"):
                cached = ART_CACHE_DIR / f"{rep_id}{ext}"
                if cached.exists():
                    try:
                        art_texture = Gdk.Texture.new_from_filename(str(cached))
                        break
                    except Exception:
                        pass
            # If not in cache, check DB
            if not art_texture:
                try:
                    art_path = get_art_path(rep_id, self.db)
                    if art_path and art_path.exists():
                        art_texture = Gdk.Texture.new_from_filename(str(art_path))
                except Exception:
                    pass

        avatar = Adw.Avatar(size=120, text=artist["artist"], show_initials=True)
        if art_texture:
            avatar.set_custom_image(art_texture)

        avatar.set_halign(Gtk.Align.CENTER)
        card.append(avatar)

        # Name
        name = Gtk.Label(label=artist["artist"])
        name.set_ellipsize(Pango.EllipsizeMode.END)
        name.set_max_width_chars(16)
        name.set_lines(1)
        name.set_xalign(0.5)
        name.add_css_class("artist-card-name")
        card.append(name)

        # Subtitle
        subtitle_text = f"{artist['album_count']} álb. · {artist['song_count']} canc."
        subtitle = Gtk.Label(label=subtitle_text)
        subtitle.set_ellipsize(Pango.EllipsizeMode.END)
        subtitle.set_max_width_chars(18)
        subtitle.set_lines(1)
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
        overlay.set_valign(Gtk.Align.START)
        
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
                    from soundwave.library.metadata.album_art import _export_art_to_tmp
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

    def _build_album_list_row(self, album: dict) -> Gtk.ListBoxRow:
        row = Adw.ActionRow()
        row.set_activatable(True)
        row.set_title(GLib.markup_escape_text(album["album"]))
        
        artist_name = album.get("album_artist", "")
        if artist_name == UNKNOWN_ARTIST:
            artist_name = "Artista desconocido"
        row.set_subtitle(GLib.markup_escape_text(artist_name))
        
        # Prefix thumbnail (40x40)
        art_texture = None
        rep_id = album.get("representative_song_id")
        if rep_id is not None:
            # Check cache first
            for ext in (".jpg", ".png"):
                cached = ART_CACHE_DIR / f"{rep_id}{ext}"
                if cached.exists():
                    try:
                        art_texture = Gdk.Texture.new_from_filename(str(cached))
                        break
                    except Exception:
                        pass
            # If not in cache, check DB
            if not art_texture:
                try:
                    art_path = get_art_path(rep_id, self.db)
                    if art_path and art_path.exists():
                        art_texture = Gdk.Texture.new_from_filename(str(art_path))
                except Exception:
                    pass
                    
        thumbnail = Gtk.Box()
        thumbnail.set_size_request(40, 40)
        thumbnail.set_halign(Gtk.Align.CENTER)
        thumbnail.set_valign(Gtk.Align.CENTER)
        
        if art_texture:
            img = Gtk.Image.new_from_paintable(art_texture)
            img.set_size_request(40, 40)
            thumbnail.append(img)
            thumbnail.add_css_class("album-list-thumb")
            provider = Gtk.CssProvider()
            provider.load_from_string(".album-list-thumb { border-radius: 4px; }")
            thumbnail.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        else:
            initials = album["album"][:1] if album["album"] else "?"
            lbl = Gtk.Label(label=initials.upper())
            thumbnail.append(lbl)
            thumbnail.add_css_class("album-list-thumb-fallback")
            
            import hashlib
            colors = ["#FF512F", "#3cba92", "#ee0979", "#11998e", "#E94057", "#9733EE", "#1f4037", "#00c6ff"]
            h = int(hashlib.md5(album["album"].encode("utf-8")).hexdigest(), 16)
            bg_color = colors[h % len(colors)]
            
            provider = Gtk.CssProvider()
            provider.load_from_string(f".album-list-thumb-fallback {{ background-color: {bg_color}; color: #ffffff; border-radius: 4px; font-weight: bold; font-size: 14px; }}")
            thumbnail.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            
        row.add_prefix(thumbnail)
        
        # Song count suffix
        song_count = album.get("song_count") or 0
        count_lbl = Gtk.Label(label=f"{song_count} canciones" if song_count != 1 else "1 canción")
        count_lbl.add_css_class("dim-label")
        row.add_suffix(count_lbl)
        
        # Play button suffix
        play_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        play_btn.set_valign(Gtk.Align.CENTER)
        play_btn.set_css_classes(["flat", "circular"])
        play_btn.set_tooltip_text("Reproducir álbum")
        
        def on_play_clicked(btn, a=album):
            album_songs = self.db.get_songs_by_album(a["album"], a.get("album_artist", ""))
            if album_songs:
                first = album_songs[0]
                for cb in self._play_song_cbs:
                    cb(first, album_songs)
                    
        play_btn.connect("clicked", on_play_clicked)
        row.add_suffix(play_btn)
        
        row.connect("activated", lambda r, a=album: self._on_album_clicked(a))
        
        # Right click/context menu handler
        gesture = Gtk.GestureClick()
        gesture.set_button(3)
        gesture.connect("pressed", lambda g, n, x, y, a=album: self._show_album_context_menu(g, a))
        row.add_controller(gesture)
        
        row._album = album
        return row
