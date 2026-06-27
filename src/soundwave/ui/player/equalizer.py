import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio

from pathlib import Path
from soundwave.player.engine import Player
from soundwave.player.equalizer import (
    BANDS_BY_MODE, BAND_MODES,
    get_preset_names, get_preset,
    GAIN_MIN, GAIN_MAX, clamp_gain, gains_for_engine,
)
from soundwave.player.headphone_presets import (
    get_headphone_preset_names, get_headphone_preset,
    import_autoeq_file,
)
from soundwave.library.config.config import load_settings, save_setting


class EqualizerDialog(Adw.Window):
    def __init__(self, player: Player, parent):
        super().__init__()
        self._player = player
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_title("Ecualizador")
        self.set_default_size(700, 500)

        self._loading_initial_state = True
        self._is_destroying = False
        self._band_mode: int = player._equalizer_n_bands  # current number of displayed bands
        self._bands: list[float] = []       # gains for current mode
        self._sliders: list[Gtk.Scale] = []
        self._labels: list[Gtk.Label] = []

        # Load initial gains from engine
        self._bands = list(player.get_equalizer_bands())

        self._build_ui()
        self._setup_initial_state()

        self.connect("destroy", self._on_destroy)

    # ──────────────────────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        # Band-mode selector
        mode_labels = ["3 bandas", "5 bandas", "10 bandas"]
        mode_store = Gtk.StringList.new(mode_labels)
        self._mode_dropdown = Gtk.DropDown(model=mode_store)
        self._mode_dropdown.set_selected(BAND_MODES.index(self._band_mode))
        self._mode_dropdown.set_tooltip_text("Número de bandas del ecualizador")
        self._mode_dropdown.connect("notify::selected", self._on_mode_changed)
        header.pack_start(self._mode_dropdown)

        # Import AutoEQ button
        import_btn = Gtk.Button()
        import_btn.set_icon_name("document-open-symbolic")
        import_btn.set_tooltip_text("Importar perfil AutoEQ (.txt)")
        import_btn.connect("clicked", self._on_import_autoeq)
        header.pack_end(import_btn)

        # Reset button
        reset_btn = Gtk.Button.new_from_icon_name("edit-undo-symbolic")
        reset_btn.set_tooltip_text("Resetear bandas")
        reset_btn.connect("clicked", self._on_reset)
        header.pack_end(reset_btn)

        # ── Main scroll container ──
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        scroll.set_vexpand(True)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        outer.set_margin_top(12)
        outer.set_margin_bottom(12)
        outer.set_margin_start(12)
        outer.set_margin_end(12)

        # Genre presets dropdown
        presets_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        presets_box.set_halign(Gtk.Align.CENTER)
        presets_box.append(Gtk.Label(label="Preset:"))
        presets = get_preset_names()
        preset_store = Gtk.StringList.new(["Personalizado"] + presets)
        self._preset_dropdown = Gtk.DropDown(model=preset_store)
        self._preset_dropdown.connect("notify::selected", self._on_preset_changed)
        presets_box.append(self._preset_dropdown)
        outer.append(presets_box)

        # Headphone presets dropdown
        hp_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hp_box.set_halign(Gtk.Align.CENTER)
        hp_box.append(Gtk.Label(label="Audífonos:"))
        self._hp_dropdown = Gtk.DropDown()
        self._hp_dropdown.connect("notify::selected", self._on_headphone_preset_changed)
        hp_box.append(self._hp_dropdown)
        delete_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        delete_btn.set_tooltip_text("Eliminar preset de audífonos")
        delete_btn.connect("clicked", self._on_delete_headphone_preset)
        hp_box.append(delete_btn)
        outer.append(hp_box)
        self._refresh_hp_dropdown()

        # ── Sliders ──
        self._sliders_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._sliders_box.set_hexpand(True)
        self._sliders_box.set_halign(Gtk.Align.CENTER)
        outer.append(self._sliders_box)
        self._rebuild_sliders()

        # Enable toggle
        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toggle_box.set_margin_top(8)
        toggle_box.set_halign(Gtk.Align.CENTER)
        self._enable_switch = Gtk.Switch()
        self._enable_switch.set_active(True)
        toggle_box.append(self._enable_switch)
        toggle_box.append(Gtk.Label(label="Activar ecualizador"))
        outer.append(toggle_box)

        scroll.set_child(outer)
        toolbar_view.set_content(scroll)

    # ──────────────────────────────────────────────────────────────
    # Slider management
    # ──────────────────────────────────────────────────────────────

    def _rebuild_sliders(self):
        """Clear and rebuild sliders for the current band mode."""
        child = self._sliders_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self._sliders_box.remove(child)
            child = nxt
        self._sliders.clear()
        self._labels.clear()

        freqs = BANDS_BY_MODE[self._band_mode]
        n = len(freqs)
        # Ensure self._bands has the right length
        if len(self._bands) != n:
            self._bands = [0.0] * n

        for i, (freq_name, _) in enumerate(freqs):
            band_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            band_box.set_size_request(max(30, min(50, 600 // n)), -1)

            value_label = Gtk.Label(label=f"{self._bands[i]:+.1f}")
            value_label.set_css_classes(["caption"])
            band_box.append(value_label)
            self._labels.append(value_label)

            slider = Gtk.Scale.new_with_range(
                Gtk.Orientation.VERTICAL, GAIN_MIN, GAIN_MAX, 0.5
            )
            slider.set_size_request(-1, 200)
            slider.set_inverted(True)
            slider.set_draw_value(False)
            slider.set_value(self._bands[i])
            slider.set_css_classes(["equalizer-slider"])
            slider._band_index = i
            slider.connect("change-value", self._on_slider_changed)
            band_box.append(slider)
            self._sliders.append(slider)

            freq_label = Gtk.Label(label=freq_name)
            freq_label.set_css_classes(["caption"])
            freq_label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
            band_box.append(freq_label)

            self._sliders_box.append(band_box)

    def _refresh_hp_dropdown(self):
        names = get_headphone_preset_names()
        hp_store = Gtk.StringList.new(["Ninguno"] + names)
        self._hp_dropdown.set_model(hp_store)
        self._hp_dropdown.set_selected(0)

    # ──────────────────────────────────────────────────────────────
    # Signal handlers
    # ──────────────────────────────────────────────────────────────

    def _on_mode_changed(self, dropdown, pspec):
        if getattr(self, "_is_destroying", False) or getattr(self, "_loading_initial_state", False):
            return
        idx = dropdown.get_selected()
        new_mode = BAND_MODES[idx]
        if new_mode == self._band_mode:
            return
        # Convert current bands to new mode via 10-band round-trip
        from soundwave.player.equalizer import _interpolate_gains
        src_freqs = [f for _, f in BANDS_BY_MODE[self._band_mode]]
        dst_freqs = [f for _, f in BANDS_BY_MODE[new_mode]]
        self._bands = _interpolate_gains(src_freqs, self._bands, dst_freqs)
        self._bands = [round(clamp_gain(g), 2) for g in self._bands]
        self._band_mode = new_mode
        self._rebuild_sliders()
        self._player.set_equalizer_bands(self._bands, self._band_mode)
        
        # Reset presets since we changed band layout
        save_setting("equalizer_preset", "Personalizado")
        save_setting("equalizer_headphone_preset", "Ninguno")
        self._preset_dropdown.set_selected(0)
        self._hp_dropdown.set_selected(0)

    def _on_slider_changed(self, slider, scroll, value):
        if getattr(self, "_is_destroying", False) or getattr(self, "_loading_initial_state", False):
            return
        i = slider._band_index
        self._bands[i] = clamp_gain(value)
        self._labels[i].set_label(f"{value:+.1f}")
        self._player.set_equalizer_bands(self._bands, self._band_mode)
        
        # Save selection settings
        save_setting("equalizer_preset", "Personalizado")
        save_setting("equalizer_headphone_preset", "Ninguno")
        
        # Deselect presets
        self._preset_dropdown.set_selected(0)
        self._hp_dropdown.set_selected(0)

    def _on_preset_changed(self, dropdown, pspec):
        if getattr(self, "_is_destroying", False) or getattr(self, "_loading_initial_state", False):
            return
        selected = dropdown.get_selected()
        if selected == 0:
            save_setting("equalizer_preset", "Personalizado")
            return  # "Personalizado"
        names = get_preset_names()
        name = names[selected - 1]
        self._bands = get_preset(name, self._band_mode)
        self._apply_bands_to_sliders()
        self._player.set_equalizer_bands(self._bands, self._band_mode)
        
        # Save selection settings
        save_setting("equalizer_preset", name)
        save_setting("equalizer_headphone_preset", "Ninguno")
        
        self._hp_dropdown.set_selected(0)

    def _on_headphone_preset_changed(self, dropdown, pspec):
        if getattr(self, "_is_destroying", False) or getattr(self, "_loading_initial_state", False):
            return
        selected = dropdown.get_selected()
        if selected == 0:
            save_setting("equalizer_headphone_preset", "Ninguno")
            return  # "Ninguno"
        names = get_headphone_preset_names()
        if selected - 1 >= len(names):
            return
        name = names[selected - 1]
        gains_stored = get_headphone_preset(name)  # stored as any-length
        if gains_stored is None:
            return
        # Resample to current mode
        from soundwave.player.equalizer import _interpolate_gains, BANDS_10
        stored_n = len(gains_stored)
        if stored_n in BANDS_BY_MODE:
            src_freqs = [f for _, f in BANDS_BY_MODE[stored_n]]
        else:
            src_freqs = [f for _, f in BANDS_10]
        dst_freqs = [f for _, f in BANDS_BY_MODE[self._band_mode]]
        self._bands = [round(clamp_gain(g), 2)
                       for g in _interpolate_gains(src_freqs, gains_stored, dst_freqs)]
        self._apply_bands_to_sliders()
        self._player.set_equalizer_bands(self._bands, self._band_mode)
        
        # Save selection settings
        save_setting("equalizer_preset", "Personalizado")
        save_setting("equalizer_headphone_preset", name)
        
        self._preset_dropdown.set_selected(0)

    def _on_delete_headphone_preset(self, btn):
        selected = self._hp_dropdown.get_selected()
        if selected == 0:
            return
        names = get_headphone_preset_names()
        if selected - 1 >= len(names):
            return
        name = names[selected - 1]
        from soundwave.player.headphone_presets import delete_headphone_preset
        delete_headphone_preset(name)
        
        # Reset saved settings
        save_setting("equalizer_headphone_preset", "Ninguno")
        
        self._refresh_hp_dropdown()

    def _on_reset(self, button):
        self._bands = [0.0] * self._band_mode
        # Ensure length matches
        self._bands = [0.0] * len(BANDS_BY_MODE[self._band_mode])
        self._apply_bands_to_sliders()
        self._player.set_equalizer_bands(self._bands, self._band_mode)
        
        # Save selection settings
        save_setting("equalizer_preset", "Personalizado")
        save_setting("equalizer_headphone_preset", "Ninguno")
        
        self._preset_dropdown.set_selected(0)
        self._hp_dropdown.set_selected(0)

    def _on_import_autoeq(self, btn):
        if hasattr(Gtk, "FileDialog"):
            dialog = Gtk.FileDialog.new()
            dialog.set_title("Importar perfil AutoEQ")
            f = Gtk.FileFilter()
            f.set_name("Archivos de texto AutoEQ (*.txt)")
            f.add_pattern("*.txt")
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(f)
            dialog.set_filters(filters)

            def on_file(dialog, result):
                try:
                    file = dialog.open_finish(result)
                    if file:
                        self._do_import_autoeq(Path(file.get_path()))
                except GLib.Error:
                    pass
            dialog.open(self, None, on_file)
        else:
            chooser = Gtk.FileChooserNative.new(
                "Importar perfil AutoEQ", self,
                Gtk.FileChooserAction.OPEN, "Importar", "Cancelar"
            )
            f = Gtk.FileFilter()
            f.set_name("Archivos de texto (*.txt)")
            f.add_pattern("*.txt")
            chooser.add_filter(f)
            self._chooser = chooser

            def on_response(dlg, resp):
                if resp == Gtk.ResponseType.ACCEPT:
                    file = dlg.get_file()
                    if file:
                        self._do_import_autoeq(Path(file.get_path()))
                self._chooser = None
            chooser.connect("response", on_response)
            chooser.show()

    def _do_import_autoeq(self, filepath: Path):
        preset_name = filepath.stem  # Use filename (without .txt) as preset name
        target_freqs = [f for _, f in BANDS_BY_MODE[self._band_mode]]
        try:
            gains = import_autoeq_file(str(filepath), preset_name, target_freqs)
            self._bands = [round(clamp_gain(g), 2) for g in gains]
            self._apply_bands_to_sliders()
            self._player.set_equalizer_bands(self._bands, self._band_mode)
            self._refresh_hp_dropdown()
            
            # Save selection settings
            save_setting("equalizer_preset", "Personalizado")
            save_setting("equalizer_headphone_preset", preset_name)
            
            # Select the newly imported preset
            names = get_headphone_preset_names()
            if preset_name in names:
                self._hp_dropdown.set_selected(names.index(preset_name) + 1)
            self._preset_dropdown.set_selected(0)
        except Exception as e:
            print(f"[EQ] Error importando AutoEQ: {e}")
            toast = Adw.Toast.new(f"Error al importar: {e}")
            toast.set_timeout(4)
            # Show a simple dialog instead
            info = Adw.MessageDialog(transient_for=self, modal=True)
            info.set_heading("Error al importar")
            info.set_body(str(e))
            info.add_response("ok", "OK")
            info.present()

    # ──────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────

    def _apply_bands_to_sliders(self):
        for i, slider in enumerate(self._sliders):
            if i < len(self._bands):
                slider.set_value(self._bands[i])
                self._labels[i].set_label(f"{self._bands[i]:+.1f}")

    def _setup_initial_state(self):
        self._loading_initial_state = True

        enabled = self._player.get_equalizer_enabled()
        self._enable_switch.set_active(enabled)
        self._enable_switch.connect("state-set", self._on_enable_toggled)
        self._set_controls_sensitive(enabled)

        # Restore saved presets from settings
        settings = load_settings()
        saved_preset = settings.get("equalizer_preset", "Personalizado")
        saved_hp_preset = settings.get("equalizer_headphone_preset", "Ninguno")

        presets = get_preset_names()
        if saved_preset in presets:
            self._preset_dropdown.set_selected(presets.index(saved_preset) + 1)
        else:
            self._preset_dropdown.set_selected(0)

        hp_names = get_headphone_preset_names()
        if saved_hp_preset in hp_names:
            self._hp_dropdown.set_selected(hp_names.index(saved_hp_preset) + 1)
        else:
            self._hp_dropdown.set_selected(0)

        self._loading_initial_state = False

    def _set_controls_sensitive(self, sensitive: bool):
        for slider in self._sliders:
            slider.set_sensitive(sensitive)
        self._preset_dropdown.set_sensitive(sensitive)
        self._hp_dropdown.set_sensitive(sensitive)
        self._mode_dropdown.set_sensitive(sensitive)

    def _on_enable_toggled(self, switch, state):
        if getattr(self, "_is_destroying", False) or getattr(self, "_loading_initial_state", False):
            return False
        self._player.set_equalizer_enabled(state)
        self._set_controls_sensitive(state)
        return False

    def _on_destroy(self, widget):
        self._is_destroying = True
