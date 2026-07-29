"""Tiny helper for turning captured microphone frames into a WAV blob."""

import io
import wave

import numpy as np

SAMPLE_RATE = 16000  # Hz — matches what Deepgram expects for 16-bit mono PCM.


def frames_to_wav_bytes(frames, sample_rate=SAMPLE_RATE):
    """`frames` is a list of int16 numpy arrays captured while the
    push-to-talk key was held. Returns a WAV file as bytes."""
    if frames:
        audio = np.concatenate(frames, axis=0).reshape(-1)
    else:
        audio = np.zeros((0,), dtype=np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()
