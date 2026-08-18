"""Renders a narration script to an audio file via ElevenLabs. Same
provider and voice ID as Griffin's live speech (voice/tts.py), but written
to disk for the video pipeline instead of streamed straight to a speaker.
"""

from elevenlabs.client import ElevenLabs

from griffin.config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID

MODEL_ID = "eleven_turbo_v2_5"
OUTPUT_FORMAT = "mp3_44100_128"

_client = None


class VoiceError(Exception):
    """Raised when narration audio can't be generated. Safe to show the user."""


def _get_client():
    global _client
    if _client is None:
        if not ELEVENLABS_API_KEY:
            raise VoiceError("No ELEVENLABS_API_KEY set. Add it to .env.")
        _client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    return _client


def render_narration(script_text, out_path, voice_id=None):
    """Generate narration audio for `script_text` and write it to `out_path` (mp3)."""
    client = _get_client()
    try:
        audio_stream = client.text_to_speech.stream(
            voice_id or ELEVENLABS_VOICE_ID,
            text=script_text,
            model_id=MODEL_ID,
            output_format=OUTPUT_FORMAT,
        )
        with open(out_path, "wb") as f:
            for chunk in audio_stream:
                f.write(chunk)
    except VoiceError:
        raise
    except Exception as exc:
        raise VoiceError(f"narration synthesis failed: {exc}")
    return out_path
