"""Estilos CSS del visualizador."""

from gi.repository import Gtk, Gdk

VISUALIZER_CSS = """
        .visualizer-bg {
            background-color: #080808;
        }
        .visualizer-art {
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            background-color: #242424;
            min-width: 300px;
            min-height: 300px;
        }
        .visualizer-art-image {
            border-radius: 16px;
            min-width: 300px;
            min-height: 300px;
        }
        .visualizer-title {
            font-size: 20pt;
            font-weight: bold;
            color: #ffffff;
            text-shadow: 0 2px 4px rgba(0,0,0,0.5);
        }
        .visualizer-artist {
            font-size: 13pt;
            color: rgba(255, 255, 255, 0.7);
            text-shadow: 0 2px 4px rgba(0,0,0,0.5);
        }
        .visualizer-artist:hover {
            color: #ffffff;
        }
        .discography-section {
            background-color: rgba(18, 18, 18, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            padding: 16px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
            transition: all 0.3s ease;
        }
        .discography-album-col {
            background-color: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 10px;
        }
        .discography-header-icon {
            color: #ffffff;
            opacity: 0.9;
        }
        .discography-header-title {
            font-size: 11pt;
            font-weight: bold;
            color: #ffffff;
        }
        .discography-header-subtitle {
            font-size: 8.5pt;
            color: rgba(255, 255, 255, 0.5);
        }
        .discography-listbox {
            background-color: transparent;
            border-radius: 12px;
        }
        .discography-album-icon {
            color: rgba(255, 255, 255, 0.7);
        }
        .discography-album-title {
            font-size: 9.5pt;
            font-weight: bold;
            color: rgba(255, 255, 255, 0.9);
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            padding-bottom: 4px;
        }
        .discography-song-row {
            background-color: transparent;
            border-radius: 8px;
            margin: 2px 0;
            transition: background-color 0.15s ease;
        }
        .discography-song-row:hover {
            background-color: rgba(255, 255, 255, 0.07);
        }
        .discography-song-icon {
            color: rgba(255, 255, 255, 0.45);
        }
        .discography-song-title {
            font-size: 9pt;
            color: rgba(255, 255, 255, 0.8);
        }
        .discography-song-duration {
            font-size: 8.5pt;
            color: rgba(255, 255, 255, 0.45);
        }
        .discography-song-row-current {
            background-color: rgba(255, 255, 255, 0.08);
        }
        .discography-song-icon-current {
            color: #1db954;
        }
        .discography-song-title-current {
            color: #1db954;
            font-weight: bold;
        }
        .discography-song-duration-current {
            color: #1db954;
        }
        .visualizer-audio-info {
            font-size: 10pt;
            color: rgba(255, 255, 255, 0.45);
            text-shadow: 0 1px 2px rgba(0,0,0,0.5);
            margin-top: 4px;
        }
"""


def load_visualizer_css():
    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(VISUALIZER_CSS.encode("utf-8"))
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 10,
    )
