"""Text-to-speech seam: the only place that talks to ElevenLabs.

One job — give it text, play it aloud — so the voice or the provider can
change in one place. Sentences are queued and spoken one at a time in a
background thread so the brain never blocks on audio playback, and
`interrupt()` can cut off what's currently playing plus drop anything
queued behind it, which is what lets the user barge in mid-reply.

Playback is piped into `mpv` rather than decoded in-process: it's a small,
well-supported dependency, it starts playing before the whole clip has
arrived (ElevenLabs streams), and killing the subprocess is an instant,
reliable way to interrupt speech.
"""

import queue
import shutil
import subprocess
import threading

from elevenlabs.client import ElevenLabs

from griffin.config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID

MODEL_ID = "eleven_turbo_v2_5"
OUTPUT_FORMAT = "mp3_44100_128"

_client = None


class TtsError(Exception):
    """Raised when speech synthesis or playback can't proceed. Safe to show the user."""


def _get_client():
    global _client
    if _client is None:
        if not ELEVENLABS_API_KEY:
            raise TtsError("No ELEVENLABS_API_KEY set. Add it to .env.")
        _client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    return _client


class TTSPlayer:
    def __init__(self, voice_id=None):
        if shutil.which("mpv") is None:
            raise TtsError(
                "mpv is not installed — it's required to play speech "
                "(e.g. `brew install mpv` or `apt install mpv`)."
            )
        self.voice_id = voice_id or ELEVENLABS_VOICE_ID
        self._queue = queue.Queue()
        self._current_proc = None
        self._proc_lock = threading.Lock()
        self._stopped = threading.Event()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def speak(self, text):
        """Queue a sentence to be spoken. Non-blocking."""
        text = text.strip()
        if text:
            self._queue.put(text)

    def interrupt(self):
        """Stop whatever's playing right now and drop anything queued behind it."""
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        with self._proc_lock:
            proc = self._current_proc
        if proc and proc.poll() is None:
            proc.terminate()

    def shutdown(self):
        self.interrupt()
        self._stopped.set()
        self._queue.put(None)  # wake the worker so it notices _stopped
        self._worker.join(timeout=2)

    def _run(self):
        while not self._stopped.is_set():
            text = self._queue.get()
            if text is None:
                continue
            try:
                self._speak_one(text)
            except TtsError as exc:
                print(f"\n[trouble speaking: {exc}]")

    def _speak_one(self, text):
        proc = subprocess.Popen(
            ["mpv", "--no-video", "--really-quiet", "-"],
            stdin=subprocess.PIPE,
        )
        with self._proc_lock:
            self._current_proc = proc
        try:
            client = _get_client()
            audio_stream = client.text_to_speech.stream(
                self.voice_id,
                text=text,
                model_id=MODEL_ID,
                output_format=OUTPUT_FORMAT,
            )
            for chunk in audio_stream:
                if proc.poll() is not None:
                    break  # interrupted
                proc.stdin.write(chunk)
                proc.stdin.flush()
        except BrokenPipeError:
            pass  # interrupted mid-write — not an error
        except Exception as exc:
            raise TtsError(f"speech synthesis failed: {exc}")
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass
            proc.wait(timeout=5)
            with self._proc_lock:
                if self._current_proc is proc:
                    self._current_proc = None
