import hashlib
import json
import os
import time
import urllib.request
import urllib.parse
import urllib.error
import webbrowser
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "soundwave"
CONFIG_FILE = CONFIG_DIR / "lastfm.json"

# Default API credentials (can be overridden by user config)
DEFAULT_API_KEY = ""
DEFAULT_API_SECRET = ""
BASE_URL = "https://ws.audioscrobbler.com/2.0/"
AUTH_URL = "https://www.last.fm/api/auth/"


class LastFMError(Exception):
    pass


class LastFmScrobbler:
    def __init__(self):
        self.session_key: Optional[str] = None
        self.username: Optional[str] = None
        self.api_key: Optional[str] = None
        self.api_secret: Optional[str] = None
        self._np_timestamp: Optional[int] = None
        self._current_artist: Optional[str] = None
        self._current_title: Optional[str] = None
        self._load_config()

    @property
    def connected(self) -> bool:
        return self.session_key is not None

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def get_auth_token(self) -> Optional[str]:
        """Get an authorization token for Last.fm OAuth"""
        if not self.api_key or not self.api_secret:
            return None

        try:
            token_params = {
                "method": "auth.getToken",
                "api_key": self.api_key,
            }
            token_params["api_sig"] = self._sign(token_params)
            token_params["format"] = "json"

            token_data = self._request(token_params)
            return token_data["token"]
        except (LastFMError, KeyError, urllib.error.URLError) as e:
            print(f"Failed to get auth token: {e}")
            return None

    def complete_auth(self, token: str) -> bool:
        """Complete OAuth authentication after user approval"""
        if not self.api_key or not self.api_secret:
            return False

        try:
            session_params = {
                "method": "auth.getSession",
                "token": token,
                "api_key": self.api_key,
            }
            session_params["api_sig"] = self._sign(session_params)
            session_params["format"] = "json"

            session_data = self._request(session_params)
            session = session_data["session"]
            self.session_key = session["key"]
            self.username = session["name"]
            self._save_config()
            return True
        except (LastFMError, KeyError, urllib.error.URLError) as e:
            print(f"Failed to complete auth: {e}")
            return False

    def authenticate(self, username: str, password: str) -> bool:
        # OAuth 2.0 flow for Last.fm (old methods are deprecated)
        # This method is kept for compatibility but now uses OAuth
        return False  # OAuth requires browser interaction, not username/password

    def disconnect(self):
        self.session_key = None
        self.username = None
        self._np_timestamp = None
        self._current_artist = None
        self._current_title = None
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()

    def now_playing(self, artist: str, title: str, album: str = "",
                    duration: int = 0, track_number: int = 0):
        if not self.connected:
            return
        self._current_artist = artist
        self._current_title = title
        self._np_timestamp = int(time.time())

        params = {
            "method": "track.updateNowPlaying",
            "artist": artist,
            "track": title,
            "api_key": self.api_key,
            "sk": self.session_key,
        }
        if album:
            params["album"] = album
        if duration:
            params["duration"] = str(duration)
        if track_number:
            params["trackNumber"] = str(track_number)

        params["api_sig"] = self._sign(params)
        params["format"] = "json"

        try:
            self._request(params)
        except (LastFMError, urllib.error.URLError):
            pass

    def scrobble(self, artist: str, title: str, album: str = "",
                 duration: int = 0, track_number: int = 0):
        if not self.connected:
            return
        timestamp = int(time.time())

        params = {
            "method": "track.scrobble",
            "artist": artist,
            "track": title,
            "timestamp": str(timestamp),
            "api_key": self.api_key,
            "sk": self.session_key,
        }
        if album:
            params["album"] = album
        if duration:
            params["duration"] = str(duration)
        if track_number:
            params["trackNumber"] = str(track_number)

        params["api_sig"] = self._sign(params)
        params["format"] = "json"

        try:
            self._request(params)
        except (LastFMError, urllib.error.URLError):
            pass

    def _request(self, params: dict) -> dict:
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(BASE_URL, data=data)
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            result = json.loads(resp.read().decode())
            if result.get("error"):
                error_code = result.get("error")
                error_msg = result.get("message", "Unknown error")
                print(f"Last.fm API error {error_code}: {error_msg}")
                raise LastFMError(f"{error_msg} (code: {error_code})")
            return result
        except urllib.error.URLError as e:
            print(f"Last.fm network error: {e}")
            raise LastFMError(str(e))

    def _sign(self, params: dict) -> str:
        sorted_params = sorted(
            (k, v) for k, v in params.items() if k != "format"
        )
        sig_str = "".join(f"{k}{v}" for k, v in sorted_params)
        sig_str += self.api_secret or ""
        return hashlib.md5(sig_str.encode()).hexdigest()

    def _load_config(self):
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

    def _save_config(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "session_key": self.session_key,
            "username": self.username,
            "api_key": self.api_key,
            "api_secret": self.api_secret
        }
        CONFIG_FILE.write_text(json.dumps(data, indent=2))
