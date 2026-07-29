"""Buffers streamed reply text into whole sentences.

The brain streams text token by token; ElevenLabs synthesizes best a
sentence at a time. This sits between them so Griffin can start speaking
the first sentence while the model is still writing the rest of the reply.
"""

import re

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


class SentenceChunker:
    def __init__(self, on_sentence):
        self.on_sentence = on_sentence
        self._buffer = ""

    def feed(self, text_chunk):
        self._buffer += text_chunk
        parts = _SENTENCE_BOUNDARY.split(self._buffer)
        if len(parts) == 1:
            return
        for sentence in parts[:-1]:
            sentence = sentence.strip()
            if sentence:
                self.on_sentence(sentence)
        self._buffer = parts[-1]

    def flush(self):
        """Call once the reply is fully streamed to emit any trailing text."""
        remaining = self._buffer.strip()
        self._buffer = ""
        if remaining:
            self.on_sentence(remaining)
