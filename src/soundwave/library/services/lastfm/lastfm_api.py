"""Core API client for Last.fm service."""

import hashlib
import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional

from .lastfm_config import BASE_URL
from .lastfm_error import LastFMError


class LastFMAPIClient:
    """Core API client for Last.fm requests."""

    def __init__(self, api_key: Optional[str], api_secret: Optional[str]):
        self.api_key = api_key
        self.api_secret = api_secret

    def request(self, params: dict) -> dict:
        """Make a signed request to Last.fm API."""
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
        except urllib.error.HTTPError as e:
            error_detail = f"HTTP error {e.code}: {e.reason}"
            print(f"Last.fm HTTP error: {error_detail}")
            raise LastFMError(error_detail)
        except urllib.error.URLError as e:
            error_detail = f"Network error: {e.reason}"
            print(f"Last.fm network error: {error_detail}")
            raise LastFMError(error_detail)
        except json.JSONDecodeError as e:
            print(f"Last.fm JSON decode error: {e}")
            raise LastFMError(f"Invalid response format: {str(e)}")
        except TimeoutError as e:
            print(f"Last.fm timeout error: {e}")
            raise LastFMError("Request timed out. Please check your connection.")
        except Exception as e:
            print(f"Last.fm unexpected error: {e}")
            raise LastFMError(f"Unexpected error: {str(e)}")

    def sign(self, params: dict) -> str:
        """Generate MD5 signature for API request."""
        sorted_params = sorted(
            (k, v) for k, v in params.items() if k != "format"
        )
        sig_str = "".join(f"{k}{v}" for k, v in sorted_params)
        sig_str += self.api_secret or ""
        return hashlib.md5(sig_str.encode()).hexdigest()
