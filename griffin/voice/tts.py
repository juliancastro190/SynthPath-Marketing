"""Text-to-speech seam: the only place that turns text into audio.

Two backends behind the same shape (speak/interrupt/shutdown), picked by
`create_tts_player()` based on TTS_PROVIDER in .env — this is exactly what
the seam was built for: swapping the voice/provider without touching
voice_cli.py or anything upstream of it.

- "local" (default): pyttsx3 over the OS's own speech engine (SAPI5 on
  Windows, NSSpeechSynthesizer on macOS, espeak on Linux). Free, offline,
  no account or API key, more robotic-sounding.
- "elevenlabs": streamed, natural-sounding, but every voice — including
  the old defaults — currently requires a paid ElevenLabs plan to use via
  the API; a free-tier account gets a 402 on every request.

Both raise TtsError on failure so voice_cli.py doesn't need to know which
backend is active.
"""

import queue
import shutil
import subprocess
import threading

from griffin.config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, LOCAL_TTS_VOICE, TTS_PROVIDER


class TtsError(Exception):
    """Raised when speech synthesis or playback can't proceed. Safe to show the user."""


# ---------------------------------------------------------------------------
# Local backend (pyttsx3 / OS speech engine) — free, offline, default.
# ---------------------------------------------------------------------------


class LocalTTSPlayer:
    def __init__(self, voice_hint=None):
        try:
            import pyttsx3
        except ImportError:
            raise TtsError("pyttsx3 is not installed — run `pip install -r requirements.txt`.")
        try:
            self._engine = pyttsx3.init()
        except Exception as exc:
            raise TtsError(f"couldn't start the local speech engine: {exc}")

        self._select_voice(voice_hint if voice_hint is not None else LOCAL_TTS_VOICE)
        self._queue = queue.Queue()
        self._speaking = threading.Event()
        self._stopped = threading.Event()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def _select_voice(self, hint):
        try:
            voices = self._engine.getProperty("voices") or []
        except Exception:
            return
        if not voices:
            return

        if hint:
            hint_lower = hint.lower()
            for v in voices:
                if hint_lower in (v.name or "").lower() or hint_lower in (v.id or "").lower():
                    self._engine.setProperty("voice", v.id)
                    return
            print(f"[local tts] no installed voice matched '{hint}' — using the default instead]")
            return

        # No preference given: guess a male-sounding voice so the default
        # experience isn't tied to whichever voice happens to be first.
        for v in voices:
            gender = (getattr(v, "gender", None) or "").lower()
            name = (v.name or "").lower()
            if "male" in gender and "female" not in gender:
                self._engine.setProperty("voice", v.id)
                return
            if any(n in name for n in ("david", "mark", "guy")):
                self._engine.setProperty("voice", v.id)
                return
        # No male-sounding match found — leave pyttsx3's own default in place.

    def speak(self, text):
        text = text.strip()
        if text:
            self._queue.put(text)

    def interrupt(self):
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        if self._speaking.is_set():
            try:
                self._engine.stop()
            except Exception:
                pass

    def shutdown(self):
        self.interrupt()
        self._stopped.set()
        self._queue.put(None)
        self._worker.join(timeout=2)

    def _run(self):
        while not self._stopped.is_set():
            text = self._queue.get()
            if text is None:
                continue
            self._speaking.set()
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as exc:
                print(f"\n[trouble speaking: {exc}]")
            finally:
                self._speaking.clear()


# ---------------------------------------------------------------------------
# ElevenLabs backend — natural-sounding, streamed, requires a paid plan.
# ---------------------------------------------------------------------------

_ELEVEN_MODEL_ID = "eleven_turbo_v2_5"
_ELEVEN_OUTPUT_FORMAT = "mp3_44100_128"

_eleven_client = None


def _get_elevenlabs_client():
    global _eleven_client
    if _eleven_client is None:
        if not ELEVENLABS_API_KEY:
            raise TtsError("No ELEVENLABS_API_KEY set. Add it to .env.")
        from elevenlabs.client import ElevenLabs

        _eleven_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    return _eleven_client


class ElevenLabsTTSPlayer:
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
            client = _get_elevenlabs_client()
            audio_stream = client.text_to_speech.stream(
                self.voice_id,
                text=text,
                model_id=_ELEVEN_MODEL_ID,
                output_format=_ELEVEN_OUTPUT_FORMAT,
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


def create_tts_player():
    """The one place that decides which backend voice_cli.py gets."""
    if TTS_PROVIDER == "elevenlabs":
        return ElevenLabsTTSPlayer()
    return LocalTTSPlayer()
