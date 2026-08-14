"""Tier 3 entry point: push-to-talk voice on top of the exact same brain and
tools as the text CLI. Nothing about ConversationLoop changes here — only
what feeds it input (a transcript instead of typed text) and what happens
to its output (spoken aloud, in addition to printed).

Every per-utterance step past capturing audio (transcribing, running the
turn, waiting on a confirmation reply) happens on a worker thread, not on
pynput's listener thread. This matters for two things: it's what makes
Tier 6's confirmation gate possible in voice mode — on_confirm can block
its own thread waiting for your spoken yes/no without freezing key
detection — and, as a side effect, it's what makes barge-in actually work
mid-reply. Previously a turn ran directly inside the key-release callback,
which blocked pynput's single listener thread for the whole turn, so a
new key-press genuinely could not be dispatched until the reply finished —
interruption only ever worked between turns, never during one.
"""

import queue
import threading

from griffin.brain.loop import ConversationLoop
from griffin.brain.provider import ProviderError
from griffin.confirm import parse_yes_no
from griffin.config import ASSISTANT_NAME, PTT_KEY_NAME
from griffin.heartbeat.notices import print_startup_notices
from griffin.project_config import load_config
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
    print_startup_notices()

    confirmation_timeout = load_config().get("tools", {}).get("confirmation_timeout_seconds", 30)
    loop = ConversationLoop()
    try:
        player = TTSPlayer()
    except TtsError as exc:
        print(f"[can't start voice mode: {exc}]")
        return

    awaiting_confirmation = threading.Event()
    confirm_replies = queue.Queue()

    def on_confirm(tool_name, tool_input, description):
        prompt = f"Should I {description}? Say yes or no."
        print(f"\n{ASSISTANT_NAME} wants to: {description}")
        player.speak(prompt)
        awaiting_confirmation.set()
        try:
            reply_text = confirm_replies.get(timeout=confirmation_timeout)
        except queue.Empty:
            reply_text = ""
            print(f"\n[no answer within {confirmation_timeout}s — treating as declined]")
        finally:
            awaiting_confirmation.clear()
        approved = parse_yes_no(reply_text)
        print(f"[{'confirmed' if approved else 'declined'}]")
        return approved

    def on_start():
        # Barge-in: if Griffin is mid-reply, a new key-press means "stop and listen."
        player.interrupt()
        print("\n[listening...]", end="", flush=True)

    def handle_turn(text):
        print(f"{ASSISTANT_NAME}: ", end="", flush=True)
        chunker = SentenceChunker(on_sentence=player.speak)

        def on_text(chunk):
            print(chunk, end="", flush=True)
            chunker.feed(chunk)

        try:
            loop.send(
                text,
                on_text=on_text,
                on_tool_call=_on_tool_call,
                on_tool_result=_on_tool_result,
                on_confirm=on_confirm,
            )
            chunker.flush()
            print()
        except ProviderError as exc:
            print(f"\n[trouble reaching {ASSISTANT_NAME}'s brain: {exc}]")

    def process_utterance(wav_bytes):
        print("\r[transcribing...]  ")
        try:
            text = transcribe(wav_bytes)
        except SttError as exc:
            print(f"[trouble hearing you: {exc}]")
            return

        if not text:
            print("[heard nothing]")
            return

        # Shown so you can tell, at a glance, whether a wrong answer was
        # the ears mishearing you or the brain misunderstanding you.
        print(f"You said: {text}")

        if awaiting_confirmation.is_set():
            confirm_replies.put(text)
            return

        handle_turn(text)

    def on_stop(wav_bytes):
        # Hand off immediately so the listener thread is free again right
        # away — see the module docstring for why that matters.
        threading.Thread(target=process_utterance, args=(wav_bytes,), daemon=True).start()

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
