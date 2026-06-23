import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw

from soundwave.ui.settings.general_page import GeneralPage
from soundwave.ui.settings.connections_page import ConnectionsPage
from soundwave.ui.settings.sync_page import SyncPage


class SettingsDialog(Adw.PreferencesWindow):
    def __init__(self, parent_window, lastfm):
        super().__init__(transient_for=parent_window, modal=True)
        self.parent_window = parent_window
        self.lastfm = lastfm

        self.set_title("Ajustes")
        self.set_default_size(480, 540)

        # Page 1: General
        self.general_page = GeneralPage(parent_window, self)
        self.add(self.general_page)

        # Page 2: Connections
        self.connections_page = ConnectionsPage(parent_window, self, lastfm)
        self.add(self.connections_page)

        # Page 3: Sincronización
        self.sync_page = SyncPage(parent_window, self)
        self.add(self.sync_page)

    def _show_error(self, message: str):
        toast = Adw.Toast.new(message)
        self.add_toast(toast)
