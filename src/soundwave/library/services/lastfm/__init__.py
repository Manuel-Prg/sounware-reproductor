"""Last.fm service package for Soundwave."""

import webbrowser
from typing import Optional

from .lastfm_error import LastFMError
from .lastfm_config import LastFMConfig, BASE_URL, AUTH_URL
from .lastfm_api import LastFMAPIClient
from .lastfm_user import LastFMUser
from .lastfm_track import LastFMTrack
from .lastfm_artist import LastFMArtist


class LastFmScrobbler:
    """Main Last.fm scrobbler that integrates all modular components."""

    def __init__(self):
        self.config = LastFMConfig()
        self.api_client = LastFMAPIClient(self.config.api_key, self.config.api_secret)
        self.user = LastFMUser(self.api_client, self.config.username)
        self.track = LastFMTrack(self.api_client, self.config.session_key)
        self.artist = LastFMArtist(self.api_client)

    @property
    def connected(self) -> bool:
        """Check if connected to Last.fm."""
        return self.config.connected

    @property
    def configured(self) -> bool:
        """Check if API credentials are configured."""
        return self.config.configured

    @property
    def session_key(self) -> Optional[str]:
        """Get session key."""
        return self.config.session_key

    @property
    def username(self) -> Optional[str]:
        """Get username."""
        return self.config.username

    @property
    def api_key(self) -> Optional[str]:
        """Get API key."""
        return self.config.api_key

    @property
    def api_secret(self) -> Optional[str]:
        """Get API secret."""
        return self.config.api_secret

    def get_auth_token(self) -> Optional[str]:
        """Get an authorization token for Last.fm OAuth."""
        if not self.api_key or not self.api_secret:
            return None

        try:
            token_params = {
                "method": "auth.getToken",
                "api_key": self.api_key,
            }
            token_params["api_sig"] = self.api_client.sign(token_params)
            token_params["format"] = "json"

            token_data = self.api_client.request(token_params)
            return token_data["token"]
        except (LastFMError, KeyError, Exception) as e:
            print(f"Failed to get auth token: {e}")
            return None

    def complete_auth(self, token: str) -> bool:
        """Complete OAuth authentication after user approval."""
        if not self.api_key or not self.api_secret:
            return False

        try:
            session_params = {
                "method": "auth.getSession",
                "token": token,
                "api_key": self.api_key,
            }
            session_params["api_sig"] = self.api_client.sign(session_params)
            session_params["format"] = "json"

            session_data = self.api_client.request(session_params)
            session = session_data["session"]
            self.config.session_key = session["key"]
            self.config.username = session["name"]
            self.config.save_config()

            # Update components with new session
            self.track.session_key = self.config.session_key
            self.user.username = self.config.username
            return True
        except (LastFMError, KeyError, Exception) as e:
            print(f"Failed to complete auth: {e}")
            return False

    def authenticate(self, username: str, password: str) -> bool:
        """OAuth 2.0 flow for Last.fm (old methods are deprecated)."""
        # This method is kept for compatibility but now uses OAuth
        return False  # OAuth requires browser interaction, not username/password

    def disconnect(self):
        """Disconnect from Last.fm."""
        self.config.clear_session()
        self.track.session_key = None
        self.user.username = None

    def now_playing(self, artist: str, title: str, album: str = "",
                    duration: int = 0, track_number: int = 0):
        """Update now playing status on Last.fm."""
        self.track.now_playing(artist, title, album, duration, track_number)

    def scrobble(self, artist: str, title: str, album: str = "",
                 duration: int = 0, track_number: int = 0):
        """Scrobble a track to Last.fm."""
        self.track.scrobble(artist, title, album, duration, track_number)

    def love_track(self, artist: str, title: str) -> bool:
        """Love a track on Last.fm."""
        return self.track.love(artist, title)

    def unlove_track(self, artist: str, title: str) -> bool:
        """Unlove a track on Last.fm."""
        return self.track.unlove(artist, title)

    def get_user_info(self) -> Optional[dict]:
        """Get user profile information from Last.fm."""
        return self.user.get_info()

    def get_recent_tracks(self, limit: int = 10) -> list:
        """Get recently played tracks from Last.fm."""
        return self.user.get_recent_tracks(limit)

    def get_top_artists(self, limit: int = 10, period: str = "overall") -> list:
        """Get user's top artists from Last.fm."""
        return self.user.get_top_artists(limit, period)

    def get_top_tracks(self, limit: int = 10, period: str = "overall") -> list:
        """Get user's top tracks from Last.fm."""
        return self.user.get_top_tracks(limit, period)

    def get_similar_artists(self, artist: str, limit: int = 10) -> list:
        """Get similar artists for a given artist."""
        return self.artist.get_similar(artist, limit)


__all__ = [
    "LastFmScrobbler",
    "LastFMError",
    "LastFMConfig",
    "BASE_URL",
    "AUTH_URL",
    "LastFMAPIClient",
    "LastFMUser",
    "LastFMTrack",
    "LastFMArtist",
]
