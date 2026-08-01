"""Etsy OAuth token storage and refresh.

Etsy's API is per-shop: there's no static API key that acts on your behalf
the way the Anthropic/Deepgram/ElevenLabs keys do. Connecting a shop means
running the one-time PKCE authorization flow (`etsy_connect.py`) to obtain
a refresh token, which is then exchanged for a short-lived access token
here — automatically, on demand, the same way a browser silently refreshes
a session cookie. Nothing in the tool layer (griffin/tools/etsy.py) or the
client (griffin/etsy/client.py) has to think about this; they just call
get_access_token().
"""

import time

import requests

from griffin import storage
from griffin.config import ETSY_API_KEY

TOKEN_FILENAME = "etsy_token.json"
TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"

# Refresh a little before actual expiry so a request never races the clock.
_EXPIRY_SAFETY_MARGIN_SECONDS = 60


class EtsyAuthError(Exception):
    """Raised when Etsy isn't connected yet, or a token refresh fails.

    The message is safe to show directly to the user.
    """


def _load():
    return storage.load(TOKEN_FILENAME, None)


def save_token(access_token, refresh_token, expires_in):
    storage.save(
        TOKEN_FILENAME,
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": time.time() + expires_in,
        },
    )


def is_connected():
    return _load() is not None


def _refresh(token):
    if not ETSY_API_KEY:
        raise EtsyAuthError(
            "No ETSY_API_KEY is set. Copy .env.example to .env and add your Etsy app's keystring."
        )
    try:
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": ETSY_API_KEY,
                "refresh_token": token["refresh_token"],
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        raise EtsyAuthError(f"Couldn't reach Etsy to refresh the connection: {exc}")

    if resp.status_code != 200:
        raise EtsyAuthError(
            "Etsy rejected the stored connection while refreshing it "
            f"({resp.status_code}) — run etsy_connect.py again to reconnect the shop."
        )

    data = resp.json()
    save_token(data["access_token"], data.get("refresh_token", token["refresh_token"]), data["expires_in"])
    return _load()


def get_access_token():
    """A currently-valid access token, refreshing first if it's stale.

    Raises EtsyAuthError if the shop has never been connected, or the
    stored refresh token no longer works.
    """
    token = _load()
    if token is None:
        raise EtsyAuthError(
            "No Etsy shop is connected yet. Run `.venv/bin/python etsy_connect.py` "
            "once to authorize Griffin against your shop."
        )
    if time.time() >= token["expires_at"] - _EXPIRY_SAFETY_MARGIN_SECONDS:
        token = _refresh(token)
    return token["access_token"]
