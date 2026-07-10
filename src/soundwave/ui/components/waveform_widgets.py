import gi
gi.require_version("cairo", "1.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk
try:
    import cairo
    import gi.repository.cairo
except ImportError:
    cairo = None

from typing import Optional, Callable
import math

from soundwave.ui.components.utils import draw_rounded_rect

CAIRO_SUPPORTED = False
try:
    import cairo
    import gi.repository.cairo
    CAIRO_SUPPORTED = True
except (ImportError, ModuleNotFoundError):
    CAIRO_SUPPORTED = False

class WaveformDrawingArea(Gtk.DrawingArea):
    def __init__(self, seek_callback: Optional[Callable[[float], None]] = None):
        super().__init__()
        self._seek_callback = seek_callback
        self._waveform_data: list[float] = []
        self._progress: float = 0.0
        self._hover_progress: Optional[float] = None
        self._sensitive: bool = False
        
        # Default styling colors
        self._accent_color: tuple[float, float, float] = (0.48, 0.28, 0.98)
        self._dim_color: tuple[float, float, float, float] = (0.7, 0.7, 0.7, 0.3)
        self._hover_color: tuple[float, float, float, float] = (0.48, 0.28, 0.98, 0.55)
        
        self.set_draw_func(self._draw_callback, None)
        self._setup_events()
        self.set_cursor_from_name("pointer")
        self.set_content_height(24)
        self.set_content_width(300)

    # pyrefly: ignore [bad-override]
    def set_cursor_from_name(self, cursor_name: str):
        try:
            display = Gdk.Display.get_default()
            cursor = Gdk.Cursor.new_from_name(cursor_name, None)
            self.set_cursor(cursor)
        except Exception:
            pass

    def _setup_events(self):
        motion = Gtk.EventControllerMotion.new()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)
        
        click = Gtk.GestureClick.new()
        click.connect("pressed", self._on_clicked)
        self.add_controller(click)
        
        drag = Gtk.GestureDrag.new()
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.add_controller(drag)

    def set_sensitive(self, sensitive: bool):
        self._sensitive = sensitive
        self.queue_draw()

    def get_sensitive(self) -> bool:
        return self._sensitive

    def set_waveform(self, data: list[float]):
        self._waveform_data = data
        self.queue_draw()

    def set_progress(self, progress: float):
        self._progress = max(0.0, min(1.0, progress))
        self.queue_draw()

    def set_accent_color(self, r: float, g: float, b: float):
        self._accent_color = (r, g, b)
        self._hover_color = (r, g, b, 0.55)
        self.queue_draw()

    def reset_colors(self):
        self._accent_color = (0.48, 0.28, 0.98)
        self._hover_color = (0.48, 0.28, 0.98, 0.55)
        self.queue_draw()

    def _on_motion(self, controller, x, y):
        if not self._sensitive:
            return
        width = self.get_width()
        if width > 0:
            self._hover_progress = max(0.0, min(1.0, x / width))
            self.queue_draw()

    def _on_leave(self, controller):
        self._hover_progress = None
        self.queue_draw()

    def _on_clicked(self, gesture, n_press, x, y):
        if not self._sensitive:
            return
        width = self.get_width()
        if width > 0:
            progress = max(0.0, min(1.0, x / width))
            self._progress = progress
            if self._seek_callback:
                self._seek_callback(progress)
            self.queue_draw()

    def _on_drag_update(self, gesture, offset_x, offset_y):
        if not self._sensitive:
            return
        success, start_x, start_y = gesture.get_start_point()
        if success:
            width = self.get_width()
            if width > 0:
                x = start_x + offset_x
                progress = max(0.0, min(1.0, x / width))
                self._hover_progress = progress
                self.queue_draw()

    def _on_drag_end(self, gesture, offset_x, offset_y):
        if not self._sensitive:
            return
        success, start_x, start_y = gesture.get_start_point()
        if success:
            width = self.get_width()
            if width > 0:
                x = start_x + offset_x
                progress = max(0.0, min(1.0, x / width))
                self._progress = progress
                if self._seek_callback:
                    self._seek_callback(progress)
        self._hover_progress = None
        self.queue_draw()

    def _draw_callback(self, area, cr, width, height, user_data):
        if width < 4 or height < 4:
            return
        if not self._sensitive:
            cr.set_source_rgba(0.5, 0.5, 0.5, 0.15)
            # Para el estado inactivo dibujamos un rectángulo plano y nítido de 4px de alto
            # para evitar advertencias de redondeo con floats infinitesimales en el inicio.
            cr.rectangle(0, height/2 - 2, width, 4)
            cr.fill()
            return

        waveform = self._waveform_data
        if not waveform:
            waveform = [
                0.25 + 0.15 * math.sin(i * 0.1) + 0.1 * math.cos(i * 0.25)
                for i in range(150)
            ]

        spacing = 1.0
        # Calculate how many bars can fit in the available width
        max_possible_bars = int((width + spacing) / (1.0 + spacing))
        if max_possible_bars < 1:
            max_possible_bars = 1

        num_bars = len(waveform)
        if num_bars > max_possible_bars:
            num_bars = max_possible_bars
            step = len(waveform) / num_bars
            waveform = [waveform[int(i * step)] for i in range(num_bars)]

        bar_width = (width - (num_bars - 1) * spacing) / num_bars
        if bar_width < 1.0:
            bar_width = 1.0
            
        max_h = height * 0.85
        
        for i in range(num_bars):
            val = waveform[i]
            bar_h = val * max_h
            if bar_h < 3.0:
                bar_h = 3.0
                
            x = i * (bar_width + spacing)
            y = (height - bar_h) / 2
            
            bar_progress = (i + 0.5) / num_bars
            
            if bar_progress <= self._progress:
                r, g, b = self._accent_color
                cr.set_source_rgb(r, g, b)
            elif self._hover_progress is not None and bar_progress <= self._hover_progress:
                r, g, b, a = self._hover_color
                cr.set_source_rgba(r, g, b, a)
            else:
                r, g, b, a = self._dim_color
                cr.set_source_rgba(r, g, b, a)
                
            if bar_width < 4.0 or bar_h < 4.0:
                cr.rectangle(x, y, bar_width, bar_h)
            else:
                draw_rounded_rect(cr, x, y, bar_width, bar_h, bar_width / 2.0)
            cr.fill()


class WaveformProgressBar(Gtk.Box):
    def __init__(self, seek_callback: Optional[Callable[[float], None]] = None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._seek_callback = seek_callback
        self._sensitive = False

        if CAIRO_SUPPORTED:
            self._drawing_area = WaveformDrawingArea(seek_callback=self._on_internal_seek)
            self._drawing_area.set_hexpand(True)
            self._drawing_area.set_valign(Gtk.Align.CENTER)
            self.append(self._drawing_area)
            self._scale = None
        else:
            # pyrefly: ignore [bad-assignment]
            self._drawing_area = None
            self._scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 1.0, 0.001)
            self._scale.set_draw_value(False)
            self._scale.set_hexpand(True)
            self._scale.set_valign(Gtk.Align.CENTER)
            self._scale.connect("change-value", self._on_scale_change_value)
            self.append(self._scale)

    def _on_internal_seek(self, progress: float):
        if self._seek_callback:
            self._seek_callback(progress)

    def _on_scale_change_value(self, scale, scroll, value):
        if self._seek_callback:
            self._seek_callback(value)
        return False

    def set_sensitive(self, sensitive: bool):
        self._sensitive = sensitive
        if self._drawing_area is not None:
            self._drawing_area.set_sensitive(sensitive)
        if self._scale is not None:
            self._scale.set_sensitive(sensitive)

    def get_sensitive(self) -> bool:
        return self._sensitive

    def set_waveform(self, data: list[float]):
        if self._drawing_area is not None:
            self._drawing_area.set_waveform(data)

    def set_progress(self, progress: float):
        if self._drawing_area is not None:
            self._drawing_area.set_progress(progress)
        if self._scale is not None:
            self._scale.set_value(progress)

    def set_accent_color(self, r: float, g: float, b: float):
        if self._drawing_area is not None:
            self._drawing_area.set_accent_color(r, g, b)

    def reset_colors(self):
        if self._drawing_area is not None:
            self._drawing_area.reset_colors()


