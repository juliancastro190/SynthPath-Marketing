"""One-time setup: authorize Griffin against your Etsy shop.

Etsy's API is per-shop, so unlike the Anthropic/Deepgram/ElevenLabs keys
there's no static secret to paste into .env — you have to grant consent
once through Etsy's own login page. This script runs that OAuth 2.0 (PKCE)
flow: it opens the authorization URL, catches the redirect on a throwaway
local server, exchanges the code for tokens, and saves them to
data/etsy_token.json. Everything after that is automatic — see
griffin/etsy/auth.py.

Run once:

    .venv/bin/python etsy_connect.py

Requires ETSY_API_KEY (your Etsy app's keystring) in .env already.
"""

import base64
import hashlib
import http.server
import secrets
import sys
import threading
import urllib.parse
import webbrowser

import requests

from griffin.config import ETSY_API_KEY
from griffin.etsy.auth import TOKEN_URL, save_token

REDIRECT_PORT = 3003
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"
AUTH_URL = "https://www.etsy.com/oauth/connect"
# Enough scope to browse listings/orders, publish and edit listings, and
# mark orders shipped — matches exactly the tools in griffin/tools/etsy.py.
SCOPES = "listings_r listings_w transactions_r transactions_w shops_r shops_w"


def _pkce_pair():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    result = {}

    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _CallbackHandler.result["code"] = query.get("code", [None])[0]
        _CallbackHandler.result["state"] = query.get("state", [None])[0]
        _CallbackHandler.result["error"] = query.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        body = (
            "Connected — you can close this tab and go back to the terminal."
            if _CallbackHandler.result.get("code")
            else "Something went wrong — check the terminal."
        )
        self.wfile.write(f"<html><body><p>{body}</p></body></html>".encode())

    def log_message(self, *args):
        pass  # keep the terminal clean; the script prints its own status


def main():
    if not ETSY_API_KEY:
        print("No ETSY_API_KEY is set. Copy .env.example to .env and add your Etsy app's keystring first.")
        sys.exit(1)

    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(16)
    params = {
        "response_type": "code",
        "client_id": ETSY_API_KEY,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    server = http.server.HTTPServer(("localhost", REDIRECT_PORT), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    print("Opening your browser to authorize Griffin against your Etsy shop...")
    print(f"If it doesn't open automatically, visit:\n\n{auth_url}\n")
    webbrowser.open(auth_url)

    thread.join(timeout=300)
    result = _CallbackHandler.result
    if not result.get("code"):
        print(f"Authorization failed or timed out: {result.get('error') or 'no code received'}")
        sys.exit(1)
    if result.get("state") != state:
        print("State mismatch on the redirect — aborting for safety. Please try again.")
        sys.exit(1)

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": ETSY_API_KEY,
            "redirect_uri": REDIRECT_URI,
            "code": result["code"],
            "code_verifier": verifier,
        },
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"Etsy rejected the token exchange ({resp.status_code}): {resp.text}")
        sys.exit(1)

    data = resp.json()
    save_token(data["access_token"], data["refresh_token"], data["expires_in"])
    # The numeric shop id is embedded as the leading segment of the access
    # token's user id (Etsy's user_id.shop_id convention only applies to
    # the access token's subject, not the shop) — safer to just ask.
    print("Connected. Griffin can now read and act on your Etsy shop.")
    print("If you haven't already, set ETSY_SHOP_ID in .env to your numeric shop id")
    print("(Shop Manager -> Settings -> Options, or the number in your shop's URL).")


if __name__ == "__main__":
    main()
