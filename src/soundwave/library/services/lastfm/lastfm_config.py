"""Configuration management for Last.fm service."""

import json
import os
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "soundwave"
CONFIG_FILE = CONFIG_DIR / "lastfm.json"

# Default API credentials (can be overridden by user config)
DEFAULT_API_KEY = ""
DEFAULT_API_SECRET = ""
BASE_URL = "https://ws.audioscrobbler.com/2.0/"
AUTH_URL = "https://www.last.fm/api/auth/"


class LastFMConfig:
    """Manages Last.fm configuration and credentials."""

    def __init__(self):
        self.session_key: Optional[str] = None
        self.username: Optional[str] = None
        self.api_key: Optional[str] = None
        self.api_secret: Optional[str] = None
        self._load_config()

    @property
    def connected(self) -> bool:
        """Check if connected to Last.fm."""
        return self.session_key is not None

    @property
    def configured(self) -> bool:
        """Check if API credentials are configured."""
        return bool(self.api_key and self.api_secret)

    def _load_config(self):
        """Load configuration from file and environment variables."""
        # Load from environment variables first (fallback)
        self.api_key = os.environ.get("SOUNDWAVE_LASTFM_API_KEY", DEFAULT_API_KEY)
        self.api_secret = os.environ.get("SOUNDWAVE_LASTFM_API_SECRET", DEFAULT_API_SECRET)

        # Then override from config file if exists
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text())
                self.session_key = data.get("session_key")
                self.username = data.get("username")
                self.api_key = data.get("api_key", self.api_key)
                self.api_secret = data.get("api_secret", self.api_secret)
            except (json.JSONDecodeError, KeyError):
                pass

    def save_config(self):
        """Save configuration to file."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "session_key": self.session_key,
            "username": self.username,
            "api_key": self.api_key,
            "api_secret": self.api_secret
        }
        CONFIG_FILE.write_text(json.dumps(data, indent=2))

    def clear_session(self):
        """Clear session data (disconnect)."""
        self.session_key = None
        self.username = None
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
