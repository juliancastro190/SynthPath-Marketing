"""The conversation loop: the one entry point every kind of turn goes through.

A typed turn, a spoken turn (Tier 3), and a heartbeat-initiated turn (Tier 5)
should all call ConversationLoop.send(). Nothing about this loop is specific
to text — it just happens to be the first thing that calls it.
"""

from griffin.brain.provider import ProviderError, stream_reply
from griffin.config import ASSISTANT_NAME

SYSTEM_PROMPT = f"""You are {ASSISTANT_NAME}, a personal AI assistant.

Tone: warm, professional, and brief. Get to the point without being curt.

You help with three things above all else:
1. Reminders — remembering things and surfacing them at the right time.
2. Performing tasks on the user's behalf.
3. Drafting messages for the user to review and send.

You do not have tools yet, so for now you can only talk — if the user asks
you to do something that would require an action (send a message, set a
reminder, etc.), say so plainly rather than pretending to have done it.
"""


class ConversationLoop:
    """Holds in-memory conversation history and drives one turn at a time."""

    def __init__(self, system_prompt=SYSTEM_PROMPT):
        self.system_prompt = system_prompt
        self.history = []

    def send(self, user_text):
        """Send a user turn, yielding reply text as it streams in.

        On success, both the user turn and the full reply are appended to
        history. On failure, the user turn is rolled back so history never
        contains a question with no answer — the next attempt just retries
        the same turn.
        """
        self.history.append({"role": "user", "content": user_text})
        chunks = []
        try:
            for chunk in stream_reply(self.history, self.system_prompt):
                chunks.append(chunk)
                yield chunk
        except ProviderError:
            self.history.pop()
            raise
        else:
            self.history.append({"role": "assistant", "content": "".join(chunks)})
