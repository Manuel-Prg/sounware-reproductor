"""Track-related operations for Last.fm service."""

import time
from typing import Optional

from .lastfm_api import LastFMAPIClient
from .lastfm_error import LastFMError


class LastFMTrack:
    """Handles track-related Last.fm operations."""

    def __init__(self, api_client: LastFMAPIClient, session_key: Optional[str] = None):
        self.api_client = api_client
        self.session_key = session_key
        self._np_timestamp = None
        self._current_artist = None
        self._current_title = None

    def now_playing(self, artist: str, title: str, album: str = "",
                    duration: int = 0, track_number: int = 0):
        """Update now playing status on Last.fm."""
        if not self.session_key:
            return

        self._current_artist = artist
        self._current_title = title
        self._np_timestamp = int(time.time())

        params = {
            "method": "track.updateNowPlaying",
            "artist": artist,
            "track": title,
            "api_key": self.api_client.api_key,
            "sk": self.session_key,
        }
        if album:
            params["album"] = album
        if duration:
            params["duration"] = str(duration)
        if track_number:
            params["trackNumber"] = str(track_number)

        params["api_sig"] = self.api_client.sign(params)
        params["format"] = "json"

        try:
            self.api_client.request(params)
        except (LastFMError, Exception):
            pass

    def scrobble(self, artist: str, title: str, album: str = "",
                 duration: int = 0, track_number: int = 0):
        """Scrobble a track to Last.fm."""
        if not self.session_key:
            return

        timestamp = int(time.time())

        params = {
            "method": "track.scrobble",
            "artist": artist,
            "track": title,
            "timestamp": str(timestamp),
            "api_key": self.api_client.api_key,
            "sk": self.session_key,
        }
        if album:
            params["album"] = album
        if duration:
            params["duration"] = str(duration)
        if track_number:
            params["trackNumber"] = str(track_number)

        params["api_sig"] = self.api_client.sign(params)
        params["format"] = "json"

        try:
            self.api_client.request(params)
        except (LastFMError, Exception):
            pass

    def love(self, artist: str, title: str) -> bool:
        """Love a track on Last.fm."""
        if not self.session_key:
            return False

        params = {
            "method": "track.love",
            "artist": artist,
            "track": title,
            "api_key": self.api_client.api_key,
            "sk": self.session_key,
        }
        params["api_sig"] = self.api_client.sign(params)
        params["format"] = "json"

        try:
            self.api_client.request(params)
            return True
        except (LastFMError, Exception) as e:
            print(f"Failed to love track: {e}")
            return False

    def unlove(self, artist: str, title: str) -> bool:
        """Unlove a track on Last.fm."""
        if not self.session_key:
            return False

        params = {
            "method": "track.unlove",
            "artist": artist,
            "track": title,
            "api_key": self.api_client.api_key,
            "sk": self.session_key,
        }
        params["api_sig"] = self.api_client.sign(params)
        params["format"] = "json"

        try:
            self.api_client.request(params)
            return True
        except (LastFMError, Exception) as e:
            print(f"Failed to unlove track: {e}")
            return False
