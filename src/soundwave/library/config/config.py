import json
import os
from pathlib import Path
from typing import Any, Dict

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "soundwave"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

def load_settings() -> Dict[str, Any]:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except (json.JSONDecodeError, KeyError):
            pass
    return {}

def save_setting(key: str, value: Any) -> None:
    settings = load_settings()
    settings[key] = value
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2))
    except Exception as e:
        print(f"Error al guardar la configuración: {e}")

def apply_theme(theme: str) -> None:
    try:
        from gi.repository import Gtk, Adw
        settings = Gtk.Settings.get_default()
        style_manager = Adw.StyleManager.get_default()
        
        if settings:
            settings.set_property("gtk-icon-theme-name", "Adwaita")
        
        if theme == "light":
            if settings:
                settings.set_property("gtk-theme-name", "Adwaita")
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        elif theme == "dark":
            if settings:
                settings.set_property("gtk-theme-name", "Adwaita")
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else: # system
            if settings:
                settings.reset_property("gtk-theme-name")
            style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
    except Exception as e:
        print(f"Error al aplicar el tema {theme}: {e}")

