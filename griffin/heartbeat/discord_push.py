"""Best-effort proactive delivery for heartbeat alerts via a Discord DM,
using Discord's plain REST API rather than a full gateway connection — the
heartbeat process doesn't need to stay connected to Discord's websocket
just to send an occasional outbound notification.

This is purely an additional live-delivery channel. The notice inbox
(heartbeat/notices.py) is always the source of truth regardless of
whether this succeeds — a failed push here never loses a notice, it just
means you'll see it the next time you open a CLI or the Discord bot
instead of immediately.
"""

import requests

from griffin.config import ASSISTANT_NAME, DISCORD_BOT_TOKEN, DISCORD_OWNER_ID

API_BASE = "https://discord.com/api/v10"
TIMEOUT_SECONDS = 10


def send_dm(text):
    """Best-effort: True on success, False on any failure (not configured,
    network error, API error). Never raises — a notification failure must
    never take down the heartbeat loop."""
    if not DISCORD_BOT_TOKEN or not DISCORD_OWNER_ID:
        return False
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}", "Content-Type": "application/json"}
    try:
        channel_resp = requests.post(
            f"{API_BASE}/users/@me/channels",
            json={"recipient_id": DISCORD_OWNER_ID},
            headers=headers,
            timeout=TIMEOUT_SECONDS,
        )
        channel_resp.raise_for_status()
        channel_id = channel_resp.json()["id"]

        message_resp = requests.post(
            f"{API_BASE}/channels/{channel_id}/messages",
            json={"content": f"**{ASSISTANT_NAME}:** {text}"},
            headers=headers,
            timeout=TIMEOUT_SECONDS,
        )
        message_resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        print(f"[heartbeat] Discord push failed (notice is still filed): {exc}")
        return False
