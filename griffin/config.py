import os

from dotenv import load_dotenv

load_dotenv()


def _env(name, default=None):
    # Strips whitespace (including a trailing newline) off every env var
    # read here. Live-hit this the hard way: a hosting platform's env-var
    # UI let a copy-pasted ANTHROPIC_API_KEY carry a trailing "\n" straight
    # into the value, which made every API request fail with a cryptic
    # "Illegal header value" deep inside httpx — nothing about DNS,
    # timeouts, or connectivity, which is exactly where that debugging
    # session spent most of its time before finding it. None of these
    # values are ever meaningfully whitespace-sensitive, so stripping
    # unconditionally is strictly safer, not just a one-off patch for the
    # key that happened to break first.
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip() or default


ASSISTANT_NAME = _env("GRIFFIN_NAME", "Griffin")
ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
MODEL_NAME = _env("GRIFFIN_MODEL", "claude-sonnet-5")

# Tier 3 — voice
DEEPGRAM_API_KEY = _env("DEEPGRAM_API_KEY")
ELEVENLABS_API_KEY = _env("ELEVENLABS_API_KEY")
# "Rachel" — ElevenLabs' default premade voice. Placeholder until a voice is
# chosen; override with ELEVENLABS_VOICE_ID in .env at any time.
ELEVENLABS_VOICE_ID = _env("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
# Which key to hold to talk. One of: ctrl_r, ctrl_l, alt_r, alt_l, space.
# Defaults to right Ctrl so it never collides with normal typing.
PTT_KEY_NAME = _env("GRIFFIN_PTT_KEY", "ctrl_r")

# Tier 7 — optional third-party observability (Helicone). Unset by default,
# which leaves every request going straight to Anthropic exactly as before;
# setting HELICONE_API_KEY proxies every model call (Griffin's and every
# specialist's, since they all go through the one provider seam) through
# Helicone instead, so it shows up as a live trace in Helicone's dashboard.
HELICONE_API_KEY = _env("HELICONE_API_KEY")
HELICONE_BASE_URL = _env("HELICONE_BASE_URL", "https://anthropic.helicone.ai")

# Tier 7 — YouTube specialist's Reddit story sourcing. Optional but
# recommended: Reddit increasingly 403s its unauthenticated JSON endpoint
# regardless of User-Agent, so without these, story fetching is unreliable
# (see griffin/youtube/reddit.py). A free "script" app at
# https://www.reddit.com/prefs/apps gives you both values — no Reddit
# login/password is used at runtime, just these two.
REDDIT_CLIENT_ID = _env("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = _env("REDDIT_CLIENT_SECRET")

# Tier 9 — the real send capability (griffin/tools/send.py), via Resend's
# HTTPS API. Originally plain SMTP — dropped after a live Tier 10 deploy
# proved cloud platforms commonly block outbound SMTP entirely (both
# Gmail's and iCloud's mail servers were unreachable from Railway on port
# 587, while Anthropic's and Discord's APIs worked fine from the same
# instance, because those are HTTPS). send_email is in config.yaml's
# requires_confirmation list, same as any other "sends a message" action;
# without RESEND_API_KEY set, send_email raises a clear error instead of
# silently failing.
RESEND_API_KEY = _env("RESEND_API_KEY")
# Resend's own placeholder sender for accounts without a verified domain —
# see .env.example for the real constraint this implies (can only send TO
# the address your Resend account is signed up with, until you verify a
# domain you own).
RESEND_FROM_ADDRESS = _env("RESEND_FROM_ADDRESS", "onboarding@resend.dev")

# Tier 10 — Discord bridge (griffin/discord_bridge.py, discord_main.py).
# Lets you chat with Griffin from Discord (phone or desktop) instead of
# only a local terminal. DISCORD_OWNER_ID is the only allowlisted user —
# the bridge ignores every message from anyone else, and every message
# outside a DM with you, as a hard security boundary (anyone who could
# reach it could spend your Anthropic credits or trigger send_email).
DISCORD_BOT_TOKEN = _env("DISCORD_BOT_TOKEN")
DISCORD_OWNER_ID = _env("DISCORD_OWNER_ID")
