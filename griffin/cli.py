"""Tier 1 entry point: a plain-text REPL for talking to Griffin.

Kept alive forever, even after voice (Tier 3) works — it's the fastest way
to debug the brain without talking to your computer.
"""

from griffin.brain.loop import ConversationLoop
from griffin.brain.provider import ProviderError
from griffin.config import ASSISTANT_NAME


def run_repl():
    print(f"{ASSISTANT_NAME} is ready. Type a message and press Enter. Ctrl+C to quit.\n")
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
            for chunk in loop.send(user_text):
                print(chunk, end="", flush=True)
            print()
        except ProviderError as exc:
            print(f"\n[trouble reaching {ASSISTANT_NAME}'s brain: {exc}]")


if __name__ == "__main__":
    run_repl()
