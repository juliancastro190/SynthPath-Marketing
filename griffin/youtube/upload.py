"""YouTube video upload — what the publisher specialist
(griffin/agents/publisher.py) actually calls. Uses the YouTube Data API
v3, not the pipeline's Reddit/ElevenLabs calls, so this is its own module
even though it lives under griffin/youtube/ alongside the rest of the
production pipeline.

A plain API key can't authorize uploading to a channel — YouTube requires
OAuth2 user consent for that. youtube_auth.py (repo root) is the one-time,
interactive flow that mints a refresh token; everything here just uses
that refresh token to get a fresh access token silently on every call, no
browser involved, which is what lets this run from Railway or the
heartbeat and not only an interactive terminal.
"""

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from griffin.config import YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


class UploadError(Exception):
    """Raised when a YouTube upload can't be authorized or fails. The
    message is safe to show the model and the user directly."""


def _require_config():
    missing = [
        name
        for name, value in (
            ("YOUTUBE_CLIENT_ID", YOUTUBE_CLIENT_ID),
            ("YOUTUBE_CLIENT_SECRET", YOUTUBE_CLIENT_SECRET),
            ("YOUTUBE_REFRESH_TOKEN", YOUTUBE_REFRESH_TOKEN),
        )
        if not value
    ]
    if missing:
        raise UploadError(
            "YouTube publishing isn't configured — missing " + ", ".join(missing) + " in .env. "
            "Run `python3 youtube_auth.py` once to set this up (see .env.example's Tier 11 section)."
        )


def _credentials():
    return Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri=TOKEN_URI,
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        scopes=SCOPES,
    )


def upload_video(video_path, title, description, privacy_status="private", tags=None):
    """Upload a finished video file to the authorized YouTube channel.
    Returns the new video's watch URL. Raises UploadError on any failure
    — an expired/revoked refresh token, a rejected upload, a missing
    file — with a message safe to show directly."""
    _require_config()
    creds = _credentials()
    try:
        creds.refresh(Request())
    except Exception as exc:
        raise UploadError(
            f"Couldn't refresh YouTube credentials — the refresh token may have expired or been "
            f"revoked (common if your Google Cloud OAuth app is still in 'Testing' status, where "
            f"tokens expire after 7 days). Re-run youtube_auth.py to get a new one: {exc}"
        )

    youtube = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {"title": title[:100], "description": description[:5000], "tags": tags or []},
        "status": {"privacyStatus": privacy_status, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    try:
        response = youtube.videos().insert(part="snippet,status", body=body, media_body=media).execute()
    except HttpError as exc:
        raise UploadError(f"YouTube rejected the upload: {exc}")

    return f"https://youtu.be/{response['id']}"
