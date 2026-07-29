"""Push-to-talk: hold a key, capture microphone audio, release to stop.

Push-to-talk means the harness never has to guess when the user started or
finished speaking, and the microphone is only ever open while the key is
held — so Griffin can never hear (and react to) its own voice.
"""

import sounddevice as sd
from pynput import keyboard

from griffin.config import PTT_KEY_NAME
from griffin.voice.audio import SAMPLE_RATE, frames_to_wav_bytes

_KEY_MAP = {
    "ctrl_r": keyboard.Key.ctrl_r,
    "ctrl_l": keyboard.Key.ctrl_l,
    "alt_r": keyboard.Key.alt_r,
    "alt_l": keyboard.Key.alt_l,
    "space": keyboard.Key.space,
}


def resolve_ptt_key(name=PTT_KEY_NAME):
    try:
        return _KEY_MAP[name]
    except KeyError:
        valid = ", ".join(_KEY_MAP)
        raise ValueError(f"Unknown GRIFFIN_PTT_KEY '{name}'. Valid options: {valid}.")


class PushToTalkSession:
    """Runs a blocking keyboard listener. Call `run(on_start, on_stop)`.

    `on_start()` fires the moment the key is pressed. `on_stop(wav_bytes)`
    fires with the recorded audio the moment the key is released.
    """

    def __init__(self, key=None):
        self.key = key or resolve_ptt_key()
        self._recording = False
        self._frames = []
        self._stream = None
        self._on_start = None
        self._on_stop = None

    def run(self, on_start, on_stop):
        self._on_start = on_start
        self._on_stop = on_stop
        with keyboard.Listener(on_press=self._on_press, on_release=self._on_release) as listener:
            listener.join()

    def _on_press(self, key):
        if key == self.key and not self._recording:
            self._start_recording()

    def _on_release(self, key):
        if key == self.key and self._recording:
            self._stop_recording()

    def _start_recording(self):
        self._recording = True
        self._frames = []
        if self._on_start:
            self._on_start()
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=self._audio_callback
        )
        self._stream.start()

    def _audio_callback(self, indata, frame_count, time_info, status):
        self._frames.append(indata.copy())

    def _stop_recording(self):
        self._recording = False
        self._stream.stop()
        self._stream.close()
        wav_bytes = frames_to_wav_bytes(self._frames)
        self._frames = []
        if self._on_stop:
            self._on_stop(wav_bytes)
