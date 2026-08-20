import os

from dotenv import load_dotenv

load_dotenv()

ASSISTANT_NAME = os.environ.get("GRIFFIN_NAME", "Griffin")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL_NAME = os.environ.get("GRIFFIN_MODEL", "claude-sonnet-5")

# Tier 3 — voice
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
# "Rachel" — ElevenLabs' default premade voice. Placeholder until a voice is
# chosen; override with ELEVENLABS_VOICE_ID in .env at any time.
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
# Which key to hold to talk. One of: ctrl_r, ctrl_l, alt_r, alt_l, space.
# Defaults to right Ctrl so it never collides with normal typing.
PTT_KEY_NAME = os.environ.get("GRIFFIN_PTT_KEY", "ctrl_r")

# Tier 7 — optional third-party observability (Helicone). Unset by default,
# which leaves every request going straight to Anthropic exactly as before;
# setting HELICONE_API_KEY proxies every model call (Griffin's and every
# specialist's, since they all go through the one provider seam) through
# Helicone instead, so it shows up as a live trace in Helicone's dashboard.
HELICONE_API_KEY = os.environ.get("HELICONE_API_KEY")
HELICONE_BASE_URL = os.environ.get("HELICONE_BASE_URL", "https://anthropic.helicone.ai")

# Tier 7 — YouTube specialist's Reddit story sourcing. Optional but
# recommended: Reddit increasingly 403s its unauthenticated JSON endpoint
# regardless of User-Agent, so without these, story fetching is unreliable
# (see griffin/youtube/reddit.py). A free "script" app at
# https://www.reddit.com/prefs/apps gives you both values — no Reddit
# login/password is used at runtime, just these two.
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET")

# Tier 9 — the real send capability (griffin/tools/send.py). Plain SMTP,
# not a third-party API: works with any provider (Gmail, Outlook, a
# personal domain's mailbox), needs no new account, and uses only the
# standard library (smtplib) — no new dependency. send_email is in
# config.yaml's requires_confirmation list, same as any other "sends a
# message" action; without these set, send_email raises a clear error
# telling you to fill them in rather than silently failing.
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
# Defaults to the login username — most providers require the From address
# to match the authenticated account anyway. Override if yours differs.
SMTP_FROM_ADDRESS = os.environ.get("SMTP_FROM_ADDRESS") or SMTP_USERNAME

# Tier 10 — Discord bridge (griffin/discord_bridge.py, discord_main.py).
# Lets you chat with Griffin from Discord (phone or desktop) instead of
# only a local terminal. DISCORD_OWNER_ID is the only allowlisted user —
# the bridge ignores every message from anyone else, and every message
# outside a DM with you, as a hard security boundary (anyone who could
# reach it could spend your Anthropic credits or trigger send_email).
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
DISCORD_OWNER_ID = os.environ.get("DISCORD_OWNER_ID")
