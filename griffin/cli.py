"""Tier 1 entry point: a plain-text REPL for talking to Griffin.

Kept alive forever, even after voice (Tier 3) works — it's the fastest way
to debug the brain without talking to your computer.
"""

from griffin.brain.loop import ConversationLoop
from griffin.brain.provider import ProviderError
from griffin.config import ASSISTANT_NAME
from griffin.heartbeat.notices import print_startup_notices


def _on_tool_call(name, tool_input):
    print(f"\n  [using tool: {name}({tool_input})]")


def _on_tool_result(name, result_text, is_error):
    tag = "error" if is_error else "result"
    print(f"  [{name} {tag}: {result_text}]")


def _on_confirm(tool_name, tool_input, description):
    # A normal blocking prompt is fine here — unlike a background action
    # with no one watching, you're sitting at the keyboard right now.
    answer = input(f"\n{ASSISTANT_NAME} wants to: {description}\nProceed? [y/N]: ").strip().lower()
    return answer in ("y", "yes")


def run_repl():
    print(f"{ASSISTANT_NAME} is ready. Type a message and press Enter. Ctrl+C to quit.\n")
    print_startup_notices()
    loop = ConversationLoop()

    while True:
        try:
            user_text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_text:
            continue

        print(f"{ASSISTANT_NAME}: ", end="", flush=True)
        try:
            loop.send(
                user_text,
                on_text=lambda chunk: print(chunk, end="", flush=True),
                on_tool_call=_on_tool_call,
                on_tool_result=_on_tool_result,
                on_confirm=_on_confirm,
            )
            print()
        except ProviderError as exc:
            print(f"\n[trouble reaching {ASSISTANT_NAME}'s brain: {exc}]")


if __name__ == "__main__":
    run_repl()
