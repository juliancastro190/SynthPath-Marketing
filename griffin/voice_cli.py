"""Tier 3 entry point: push-to-talk voice on top of the exact same brain and
tools as the text CLI. Nothing about ConversationLoop changes here — only
what feeds it input (a transcript instead of typed text) and what happens
to its output (spoken aloud, in addition to printed).
"""

from griffin.brain.loop import ConversationLoop
from griffin.brain.provider import ProviderError
from griffin.config import ASSISTANT_NAME, PTT_KEY_NAME
from griffin.voice.chunker import SentenceChunker
from griffin.voice.ptt import PushToTalkSession
from griffin.voice.stt import SttError, transcribe
from griffin.voice.tts import TTSPlayer, TtsError


def _on_tool_call(name, tool_input):
    print(f"\n  [using tool: {name}({tool_input})]")


def _on_tool_result(name, result_text, is_error):
    tag = "error" if is_error else "result"
    print(f"  [{name} {tag}: {result_text}]")


def run_voice():
    print(f"{ASSISTANT_NAME} voice mode. Hold [{PTT_KEY_NAME}] to talk, release to send.")
    print("Ctrl+C to quit. The text interface (main.py) still works if you'd rather type.\n")

    loop = ConversationLoop()
    try:
        player = TTSPlayer()
    except TtsError as exc:
        print(f"[can't start voice mode: {exc}]")
        return

    def on_start():
        # Barge-in: if Griffin is mid-reply, a new key-press means "stop and listen."
        player.interrupt()
        print("\n[listening...]", end="", flush=True)

    def on_stop(wav_bytes):
        print("\r[transcribing...]  ")
        try:
            text = transcribe(wav_bytes)
        except SttError as exc:
            print(f"[trouble hearing you: {exc}]")
            return

        if not text:
            print("[heard nothing]")
            return

        # Shown so you can tell, at a glance, whether a wrong answer was the
        # ears mishearing you or the brain misunderstanding you.
        print(f"You said: {text}")
        print(f"{ASSISTANT_NAME}: ", end="", flush=True)

        chunker = SentenceChunker(on_sentence=player.speak)

        def on_text(chunk):
            print(chunk, end="", flush=True)
            chunker.feed(chunk)

        try:
            loop.send(text, on_text=on_text, on_tool_call=_on_tool_call, on_tool_result=_on_tool_result)
            chunker.flush()
            print()
        except ProviderError as exc:
            print(f"\n[trouble reaching {ASSISTANT_NAME}'s brain: {exc}]")

    session = PushToTalkSession()
    try:
        session.run(on_start, on_stop)
    except KeyboardInterrupt:
        pass
    finally:
        player.shutdown()
        print("\nGoodbye.")


if __name__ == "__main__":
    run_voice()
