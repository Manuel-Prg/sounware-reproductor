import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Pango


def build_mini_player_ui(window, player, on_seek_callback, on_repeat_callback, on_restore_callback):
    # Main container with horizontal layout
    window._main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
    window._main_box.set_css_classes(["mini-player"])
    window._main_box.set_margin_start(12)
    window._main_box.set_margin_end(12)
    window._main_box.set_margin_top(12)
    window._main_box.set_margin_bottom(12)

    # Left Column: Cover Art
    art_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    art_box.set_valign(Gtk.Align.CENTER)

    window._art_image = Gtk.Picture()
    window._art_image.set_size_request(116, 116)
    window._art_image.set_content_fit(Gtk.ContentFit.COVER)
    window._art_image.set_css_classes(["mini-player-art"])
    art_box.append(window._art_image)
    window._main_box.append(art_box)

    # Right Column: Song metadata, playback controls, and timeline
    right_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    right_column.set_hexpand(True)
    right_column.set_valign(Gtk.Align.CENTER)

    # Top row: Title/Artist + Window Management (minimize, restore, close)
    top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    
    info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    info_box.set_hexpand(True)
    
    window._title_label = Gtk.Label(label="Soundwave")
    window._title_label.set_ellipsize(Pango.EllipsizeMode.END)
    window._title_label.set_xalign(0)
    window._title_label.set_css_classes(["mini-player-title"])
    
    window._artist_label = Gtk.Label(label="Sin reproducción")
    window._artist_label.set_ellipsize(Pango.EllipsizeMode.END)
    window._artist_label.set_xalign(0)
    window._artist_label.set_css_classes(["mini-player-artist"])
    
    info_box.append(window._title_label)
    info_box.append(window._artist_label)
    top_row.append(info_box)

    # Compact Window controls
    win_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    win_controls.set_valign(Gtk.Align.START)
    
    restore_btn = Gtk.Button.new_from_icon_name("go-up-symbolic")
    restore_btn.set_css_classes(["flat", "circular", "mini-player-win-btn"])
    restore_btn.set_size_request(24, 24)
    restore_btn.set_tooltip_text("Restaurar ventana")
    restore_btn.connect("clicked", lambda b: on_restore_callback())
    win_controls.append(restore_btn)

    close_btn = Gtk.Button.new_from_icon_name("window-close-symbolic")
    close_btn.set_css_classes(["flat", "circular", "mini-player-win-btn"])
    close_btn.set_size_request(24, 24)
    close_btn.set_tooltip_text("Cerrar")
    close_btn.connect("clicked", lambda b: on_restore_callback())
    win_controls.append(close_btn)
    
    top_row.append(win_controls)
    right_column.append(top_row)

    # Media Control Buttons
    controls_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    controls_row.set_halign(Gtk.Align.START)
    controls_row.set_valign(Gtk.Align.CENTER)

    window._prev_button = Gtk.Button.new_from_icon_name("media-skip-backward-symbolic")
    window._prev_button.set_css_classes(["flat", "circular", "mini-player-ctrl-btn"])
    window._prev_button.set_size_request(32, 32)
    window._prev_button.connect("clicked", lambda b: player.previous())
    controls_row.append(window._prev_button)

    window._play_button = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
    window._play_button.set_css_classes(["mini-player-play-btn", "circular"])
    window._play_button.set_size_request(38, 38)
    window._play_button.connect("clicked", lambda b: player.play_pause())
    controls_row.append(window._play_button)

    window._next_button = Gtk.Button.new_from_icon_name("media-skip-forward-symbolic")
    window._next_button.set_css_classes(["flat", "circular", "mini-player-ctrl-btn"])
    window._next_button.set_size_request(32, 32)
    window._next_button.connect("clicked", lambda b: player.next())
    controls_row.append(window._next_button)

    window._repeat_btn = Gtk.Button.new_from_icon_name("media-playlist-repeat-symbolic")
    window._repeat_btn.set_css_classes(["flat", "circular", "mini-player-ctrl-btn"])
    window._repeat_btn.set_size_request(32, 32)
    window._repeat_btn.connect("clicked", on_repeat_callback)
    controls_row.append(window._repeat_btn)
    
    right_column.append(controls_row)

    # Progress / Timeline slider
    progress_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    progress_row.set_valign(Gtk.Align.CENTER)

    window._time_label = Gtk.Label(label="0:00")
    window._time_label.set_css_classes(["mini-player-time"])
    progress_row.append(window._time_label)

    window._progress_scale = Gtk.Scale.new_with_range(
        Gtk.Orientation.HORIZONTAL, 0.0, 100.0, 0.1
    )
    window._progress_scale.set_hexpand(True)
    window._progress_scale.set_draw_value(False)
    window._progress_scale.set_css_classes(["mini-player-scale"])
    window._progress_scale.connect("change-value", on_seek_callback)
    progress_row.append(window._progress_scale)

    window._duration_label = Gtk.Label(label="0:00")
    window._duration_label.set_css_classes(["mini-player-time"])
    progress_row.append(window._duration_label)

    right_column.append(progress_row)
    window._main_box.append(right_column)

    # Enable dragging by wrapping content inside WindowHandle
    handle = Gtk.WindowHandle()
    handle.set_child(window._main_box)
    handle.add_css_class("mini-player-handle")
    window.set_child(handle)
