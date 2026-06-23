"""Artist-related operations for Last.fm service."""

from typing import Optional

from .lastfm_api import LastFMAPIClient
from .lastfm_error import LastFMError


class LastFMArtist:
    """Handles artist-related Last.fm operations."""

    def __init__(self, api_client: LastFMAPIClient):
        self.api_client = api_client

    def get_similar(self, artist: str, limit: int = 10) -> list:
        """Get similar artists for a given artist."""
        if not self.api_client.api_key:
            return []

        params = {
            "method": "artist.getSimilar",
            "artist": artist,
            "limit": str(limit),
            "api_key": self.api_client.api_key,
        }
        params["format"] = "json"

        try:
            data = self.api_client.request(params)
            artists = data.get("similarartists", {}).get("artist", [])
            if isinstance(artists, dict):
                artists = [artists]
            return artists
        except (LastFMError, Exception) as e:
            print(f"Failed to get similar artists: {e}")
            return []
