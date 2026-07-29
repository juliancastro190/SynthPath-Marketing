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
