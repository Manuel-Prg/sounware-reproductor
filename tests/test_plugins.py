import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock
import sys

from soundwave.core.plugin_manager import PluginManager, PluginAPI


class TestPluginSystem(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.app_mock = MagicMock()
        self.player_mock = MagicMock()
        self.db_mock = MagicMock()
        self.window_mock = MagicMock()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        # Clean up loaded modules from sys.modules
        for key in list(sys.modules.keys()):
            if key.startswith("soundwave_plugins."):
                del sys.modules[key]

    def test_plugin_loading_and_lifecycle(self):
        # Create a mock plugin python file
        plugin_code = """
initialized = False
cleaned = False
api_received = None

def initialize(api):
    global initialized, api_received
    initialized = True
    api_received = api

def cleanup():
    global cleaned
    cleaned = True
"""
        plugin_file = Path(self.temp_dir) / "test_plugin.py"
        plugin_file.write_text(plugin_code, encoding="utf-8")

        # Instantiate PluginManager and override plugin_dir
        pm = PluginManager(self.app_mock, self.player_mock, self.db_mock, self.window_mock)
        pm.plugin_dir = Path(self.temp_dir)

        # Load
        pm.load_plugins()

        # Check loaded plugins
        self.assertIn("test_plugin", pm.plugins)
        plugin_module = pm.plugins["test_plugin"]
        self.assertTrue(plugin_module.initialized)
        self.assertIsNotNone(plugin_module.api_received)
        self.assertEqual(plugin_module.api_received.player, self.player_mock)

        # Shutdown
        pm.shutdown()
        self.assertTrue(plugin_module.cleaned)
        self.assertEqual(len(pm.plugins), 0)

    def test_class_plugin_loading(self):
        # Create a mock class-based plugin python file
        plugin_code = """
plugin_class = "MyPluginClass"

class MyPluginClass:
    def __init__(self):
        self.initialized = False
        self.cleaned = False
        self.api_received = None

    def initialize(self, api):
        self.initialized = True
        self.api_received = api

    def cleanup(self):
        self.cleaned = True
"""
        plugin_file = Path(self.temp_dir) / "class_plugin.py"
        plugin_file.write_text(plugin_code, encoding="utf-8")

        # Instantiate PluginManager and override plugin_dir
        pm = PluginManager(self.app_mock, self.player_mock, self.db_mock, self.window_mock)
        pm.plugin_dir = Path(self.temp_dir)

        # Load
        pm.load_plugins()

        # Check loaded plugins
        self.assertIn("class_plugin", pm.plugins)
        plugin_instance = pm.plugins["class_plugin"]
        self.assertTrue(plugin_instance.initialized)
        self.assertIsNotNone(plugin_instance.api_received)
        self.assertEqual(plugin_instance.api_received.player, self.player_mock)

        # Shutdown
        pm.shutdown()
        self.assertTrue(plugin_instance.cleaned)
        self.assertEqual(len(pm.plugins), 0)
