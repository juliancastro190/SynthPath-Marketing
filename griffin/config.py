import os

from dotenv import load_dotenv

load_dotenv()

ASSISTANT_NAME = os.environ.get("GRIFFIN_NAME", "Griffin")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL_NAME = os.environ.get("GRIFFIN_MODEL", "claude-sonnet-5")

# Tier 3 — voice
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")
# "local" (default): free, offline, the OS's own speech engine (SAPI5 on
# Windows) via pyttsx3 — no account needed. "elevenlabs": natural-sounding
# but every voice currently requires a paid ElevenLabs plan to use via the
# API, even the old free defaults.
TTS_PROVIDER = os.environ.get("TTS_PROVIDER", "local")
# Optional: a substring to match against installed local voice names (e.g.
# "David" on Windows) to pick a specific one. Unset tries to guess a
# male-sounding voice automatically; leave unset for the plain OS default.
LOCAL_TTS_VOICE = os.environ.get("LOCAL_TTS_VOICE")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
# "Rachel" — ElevenLabs' default premade voice. Placeholder until a voice is
# chosen; override with ELEVENLABS_VOICE_ID in .env at any time.
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
# Which key to hold to talk. One of: ctrl_r, ctrl_l, alt_r, alt_l, space.
# Defaults to right Ctrl so it never collides with normal typing.
PTT_KEY_NAME = os.environ.get("GRIFFIN_PTT_KEY", "ctrl_r")

# Discord bridge
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
# The owner's Discord user ID (a snowflake, from Developer Mode ->
# right-click your own profile -> Copy User ID). The bot ignores every
# message that isn't a DM from this exact user.
DISCORD_OWNER_ID = os.environ.get("DISCORD_OWNER_ID")
