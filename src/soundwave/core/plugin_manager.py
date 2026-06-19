import os
import sys
import importlib.util
import traceback
from pathlib import Path
from typing import Dict, Any

class PluginAPI:
    """
    API exposed to plugins. Provides access to core components of the application.
    """
    def __init__(self, app, player, db, window):
        self.app = app
        self.player = player
        self.db = db
        self.window = window


class PluginManager:
    """
    Manages loading, lifecycle, and unloading of python-based plugins.
    Plugins are stored in ~/.local/share/soundwave/plugins/
    """
    def __init__(self, app, player, db, window):
        self.app = app
        self.player = player
        self.db = db
        self.window = window
        self.plugins: Dict[str, Any] = {}
        self.plugin_dir = Path.home() / ".local" / "share" / "soundwave" / "plugins"

    def load_plugins(self):
        try:
            self.plugin_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Error al crear directorio de plugins: {e}", file=sys.stderr)
            return

        # Create demo plugin if no plugins are found
        self._maybe_create_demo_plugin()

        api = PluginAPI(self.app, self.player, self.db, self.window)

        for path in self.plugin_dir.glob("*.py"):
            if path.name.startswith("_"):
                continue
            name = path.stem
            try:
                spec = importlib.util.spec_from_file_location(name, path)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                
                # Register in sys.modules to allow potential imports inside plugins
                sys.modules[f"soundwave_plugins.{name}"] = module
                spec.loader.exec_module(module)

                # Initialize module-level or class-level plugins
                if hasattr(module, "initialize"):
                    module.initialize(api)
                    self.plugins[name] = module
                    print(f"[PluginManager] Plugin cargado con éxito: {name}")
                elif hasattr(module, "plugin_class"):
                    cls_name = getattr(module, "plugin_class")
                    if hasattr(module, cls_name):
                        cls = getattr(module, cls_name)
                        instance = cls()
                        if hasattr(instance, "initialize"):
                            instance.initialize(api)
                        self.plugins[name] = instance
                        print(f"[PluginManager] Plugin (clase) cargado con éxito: {name}")
            except Exception as e:
                print(f"[PluginManager] Error al cargar plugin {name}: {e}", file=sys.stderr)
                traceback.print_exc()

    def shutdown(self):
        for name, plugin in list(self.plugins.items()):
            if hasattr(plugin, "cleanup"):
                try:
                    plugin.cleanup()
                    print(f"[PluginManager] Plugin limpiado: {name}")
                except Exception as e:
                    print(f"[PluginManager] Error al limpiar plugin {name}: {e}", file=sys.stderr)
        self.plugins.clear()

    def _maybe_create_demo_plugin(self):
        # If any python plugins exist (other than demo), don't recreate demo
        py_files = [p for p in self.plugin_dir.glob("*.py") if not p.name.startswith("_")]
        if py_files:
            return

        demo_path = self.plugin_dir / "demo_plugin.py"
        content = """# Soundwave Demo Plugin
# Este es un plugin de demostración para Soundwave.
# Imprime información sobre la canción en reproducción en la consola.

import sys

def on_song_changed(song):
    if song:
        print(f"[DEMO PLUGIN] Reproduciendo: {song.display_title} - {song.display_artist}")
    else:
        print("[DEMO PLUGIN] Reproducción detenida")

def on_state_changed(state):
    print(f"[DEMO PLUGIN] Estado del reproductor cambiado: {state}")

def initialize(api):
    print("[DEMO PLUGIN] Inicializando Demo Plugin")
    # Conectar los eventos del reproductor
    api.player.connect_song(on_song_changed)
    api.player.connect_state(on_state_changed)

def cleanup():
    print("[DEMO PLUGIN] Limpiando recursos del plugin")
"""
        try:
            demo_path.write_text(content, encoding="utf-8")
            print(f"[PluginManager] Plugin de demostración creado en: {demo_path}")
        except Exception as e:
            print(f"[PluginManager] No se pudo crear el plugin de demostración: {e}", file=sys.stderr)
