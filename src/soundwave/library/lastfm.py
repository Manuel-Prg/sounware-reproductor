import hashlib
import json
import os
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "soundwave"
CONFIG_FILE = CONFIG_DIR / "lastfm.json"

API_KEY = "d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0"
API_SECRET = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
BASE_URL = "https://ws.audioscrobbler.com/2.0/"


class LastFMError(Exception):
    pass


class LastFmScrobbler:
    def __init__(self):
        self.session_key: Optional[str] = None
        self.username: Optional[str] = None
        self._np_timestamp: Optional[int] = None
        self._current_artist: Optional[str] = None
        self._current_title: Optional[str] = None
        self._load_config()

    @property
    def connected(self) -> bool:
        return self.session_key is not None

    def authenticate(self, username: str, password: str) -> bool:
        password_hash = hashlib.md5(password.encode()).hexdigest()
        params = {
            "method": "auth.getMobileSession",
            "username": username,
            "authToken": password_hash,
            "api_key": API_KEY,
        }
        params["api_sig"] = self._sign(params)
        params["format"] = "json"

        try:
            data = self._request(params)
            session = data["session"]
            self.session_key = session["key"]
            self.username = session["name"]
            self._save_config()
            return True
        except (LastFMError, KeyError, urllib.error.URLError):
            return False

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
            "api_key": API_KEY,
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
            "api_key": API_KEY,
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
                raise LastFMError(result.get("message", "Unknown error"))
            return result
        except urllib.error.URLError as e:
            raise LastFMError(str(e))

    def _sign(self, params: dict) -> str:
        sorted_params = sorted(
            (k, v) for k, v in params.items() if k != "format"
        )
        sig_str = "".join(f"{k}{v}" for k, v in sorted_params)
        sig_str += API_SECRET
        return hashlib.md5(sig_str.encode()).hexdigest()

    def _load_config(self):
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text())
                self.session_key = data.get("session_key")
                self.username = data.get("username")
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_config(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {"session_key": self.session_key, "username": self.username}
        CONFIG_FILE.write_text(json.dumps(data, indent=2))
