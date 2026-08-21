"""One-time setup for the publisher specialist (griffin/agents/publisher.py,
griffin/youtube/upload.py): authorizes Griffin to upload videos to your
YouTube channel, then prints the refresh token to paste into .env (or
Railway's environment variables) as YOUTUBE_REFRESH_TOKEN.

Run this locally, not on a server — it opens a browser for you to sign in
to the Google account that owns the channel and grant consent. It only
needs YOUTUBE_CLIENT_ID/YOUTUBE_CLIENT_SECRET already set (see
.env.example's Tier 11 section for how to get those from a Google Cloud
project); the refresh token is what this mints, not what it needs going in.
"""

import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from griffin.config import YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main():
    if not YOUTUBE_CLIENT_ID or not YOUTUBE_CLIENT_SECRET:
        print("Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env first — see .env.example's Tier 11 section.")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": YOUTUBE_CLIENT_ID,
            "client_secret": YOUTUBE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    print("\nAuthorized. Add this to your .env (and to Railway's env vars if the publisher runs there too):\n")
    print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")
    print(
        "\nNote: if your Google Cloud project's OAuth consent screen is still in "
        "'Testing' publishing status, this refresh token expires after 7 days — "
        "you'll need to re-run this script to get a new one at that point. "
        "Submitting the app for Google's verification removes that limit, but is "
        "real extra setup this project doesn't walk through; for personal use, "
        "re-running this occasionally is usually the simpler tradeoff."
    )


if __name__ == "__main__":
    main()
