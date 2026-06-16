import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from soundwave.player.engine import Player
from soundwave.player.equalizer import (
    BAND_FREQUENCIES, get_preset_names, get_preset,
    GAIN_MIN, GAIN_MAX, clamp_gain
)


class EqualizerDialog(Adw.Window):
    def __init__(self, player: Player, parent):
        super().__init__()
        self._player = player
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_title("Ecualizador")
        self.set_default_size(600, 400)

        self._bands = list(player.get_equalizer_bands())
        self._sliders: list[Gtk.Scale] = []
        self._labels: list[Gtk.Label] = []

        self._build_ui()

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        # Presets dropdown
        presets = get_preset_names()
        preset_store = Gtk.StringList.new(presets)
        self._preset_dropdown = Gtk.DropDown(model=preset_store)
        self._preset_dropdown.connect("notify::selected", self._on_preset_changed)
        header.set_title_widget(self._preset_dropdown)

        # Reset button
        reset_btn = Gtk.Button.new_from_icon_name("edit-undo-symbolic")
        reset_btn.set_tooltip_text("Resetear bandas")
        reset_btn.connect("clicked", self._on_reset)
        header.pack_end(reset_btn)

        # Main content
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)

        # Sliders box (horizontal)
        sliders_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        sliders_box.set_hexpand(True)
        sliders_box.set_halign(Gtk.Align.CENTER)

        for i, (freq_name, freq_hz) in enumerate(BAND_FREQUENCIES):
            band_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            band_box.set_size_request(50, -1)

            # Value label
            value_label = Gtk.Label(label="0.0")
            value_label.set_css_classes(["caption"])
            band_box.append(value_label)
            self._labels.append(value_label)

            # Vertical slider
            slider = Gtk.Scale.new_with_range(
                Gtk.Orientation.VERTICAL, GAIN_MIN, GAIN_MAX, 0.5
            )
            slider.set_size_request(40, 200)
            slider.set_inverted(True)
            slider.set_draw_value(False)
            slider.set_value(self._bands[i])
            slider.set_css_classes(["equalizer-slider"])
            slider._band_index = i
            slider.connect("change-value", self._on_slider_changed)
            band_box.append(slider)
            self._sliders.append(slider)

            # Frequency label
            freq_label = Gtk.Label(label=freq_name)
            freq_label.set_css_classes(["caption"])
            band_box.append(freq_label)

            sliders_box.append(band_box)

        box.append(sliders_box)

        # Enable toggle
        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toggle_box.set_margin_top(12)
        toggle_box.set_halign(Gtk.Align.CENTER)

        self._enable_switch = Gtk.Switch()
        self._enable_switch.set_active(True)
        toggle_box.append(self._enable_switch)
        toggle_box.append(Gtk.Label(label="Activar ecualizador"))

        box.append(toggle_box)

        toolbar_view.set_content(box)

    def _on_slider_changed(self, slider, scroll, value):
        i = slider._band_index
        self._bands[i] = clamp_gain(value)
        self._labels[i].set_label(f"{value:+.1f}")
        self._player.set_equalizer_bands(self._bands)
        self._preset_dropdown.set_selected(-1)

    def _on_preset_changed(self, dropdown, param):
        selected = dropdown.get_selected()
        presets = get_preset_names()
        if 0 <= selected < len(presets):
            self._bands = list(get_preset(presets[selected]))
            for i, slider in enumerate(self._sliders):
                slider.set_value(self._bands[i])
                self._labels[i].set_label(f"{self._bands[i]:+.1f}")
            self._player.set_equalizer_bands(self._bands)

    def _on_reset(self, button):
        self._bands = [0.0] * 10
        for i, slider in enumerate(self._sliders):
            slider.set_value(0.0)
            self._labels[i].set_label("0.0")
        self._player.set_equalizer_bands(self._bands)
        self._preset_dropdown.set_selected(-1)
