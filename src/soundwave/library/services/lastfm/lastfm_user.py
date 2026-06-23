"""User-related operations for Last.fm service."""

from typing import Optional

from .lastfm_api import LastFMAPIClient
from .lastfm_error import LastFMError


class LastFMUser:
    """Handles user-related Last.fm operations."""

    def __init__(self, api_client: LastFMAPIClient, username: Optional[str] = None):
        self.api_client = api_client
        self.username = username

    def get_info(self) -> Optional[dict]:
        """Get user profile information from Last.fm."""
        if not self.username:
            return None

        params = {
            "method": "user.getInfo",
            "user": self.username,
            "api_key": self.api_client.api_key,
        }
        params["format"] = "json"

        try:
            data = self.api_client.request(params)
            return data.get("user")
        except (LastFMError, Exception) as e:
            print(f"Failed to get user info: {e}")
            return None

    def get_recent_tracks(self, limit: int = 10) -> list:
        """Get recently played tracks from Last.fm."""
        if not self.username:
            return []

        params = {
            "method": "user.getRecentTracks",
            "user": self.username,
            "limit": str(limit),
            "api_key": self.api_client.api_key,
        }
        params["format"] = "json"

        try:
            data = self.api_client.request(params)
            tracks = data.get("recenttracks", {}).get("track", [])
            if isinstance(tracks, dict):
                tracks = [tracks]
            return tracks
        except (LastFMError, Exception) as e:
            print(f"Failed to get recent tracks: {e}")
            return []

    def get_top_artists(self, limit: int = 10, period: str = "overall") -> list:
        """Get user's top artists from Last.fm."""
        if not self.username:
            return []

        params = {
            "method": "user.getTopArtists",
            "user": self.username,
            "limit": str(limit),
            "period": period,
            "api_key": self.api_client.api_key,
        }
        params["format"] = "json"

        try:
            data = self.api_client.request(params)
            artists = data.get("topartists", {}).get("artist", [])
            if isinstance(artists, dict):
                artists = [artists]
            return artists
        except (LastFMError, Exception) as e:
            print(f"Failed to get top artists: {e}")
            return []

    def get_top_tracks(self, limit: int = 10, period: str = "overall") -> list:
        """Get user's top tracks from Last.fm."""
        if not self.username:
            return []

        params = {
            "method": "user.getTopTracks",
            "user": self.username,
            "limit": str(limit),
            "period": period,
            "api_key": self.api_client.api_key,
        }
        params["format"] = "json"

        try:
            data = self.api_client.request(params)
            tracks = data.get("toptracks", {}).get("track", [])
            if isinstance(tracks, dict):
                tracks = [tracks]
            return tracks
        except (LastFMError, Exception) as e:
            print(f"Failed to get top tracks: {e}")
            return []
