"""Speech-to-text seam: the only place that talks to Deepgram.

One job — give it audio, get back text — so the transcriber can be swapped
later without touching anything else in the voice path.
"""

from deepgram import DeepgramClient

from griffin.config import DEEPGRAM_API_KEY

_client = None


class SttError(Exception):
    """Raised when transcription can't be completed. Safe to show the user."""


def _get_client():
    global _client
    if _client is None:
        if not DEEPGRAM_API_KEY:
            raise SttError("No DEEPGRAM_API_KEY set. Add it to .env.")
        _client = DeepgramClient(api_key=DEEPGRAM_API_KEY)
    return _client


def transcribe(wav_bytes):
    """Transcribe a WAV recording to text. Raises SttError on failure."""
    if not wav_bytes:
        return ""
    client = _get_client()
    try:
        response = client.listen.v1.media.transcribe_file(
            request=wav_bytes,
            model="nova-2",
            smart_format=True,
            language="en",
        )
        return response.results.channels[0].alternatives[0].transcript.strip()
    except SttError:
        raise
    except Exception as exc:
        raise SttError(f"couldn't transcribe that: {exc}")
