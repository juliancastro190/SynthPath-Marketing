"""The conversation loop: the one entry point every kind of turn goes through.

A typed turn, a spoken turn (Tier 3), and a heartbeat-initiated turn (Tier 5)
should all call ConversationLoop.send(). Nothing about this loop is specific
to text — it just happens to be the first thing that calls it. The model may
call several tools in a row before it's ready to answer; the loop keeps
running turns against the provider until it gets a non-tool-use reply.
"""

from griffin.brain.provider import ProviderError, run_turn, serialize_content_blocks
from griffin.config import ASSISTANT_NAME
from griffin.tools.registry import ToolError, build_default_registry

# Safety valve against a runaway back-and-forth with the model; a real turn
# should resolve in a handful of rounds at most.
MAX_TOOL_ROUNDS = 8

SYSTEM_PROMPT = f"""You are {ASSISTANT_NAME}, a personal AI assistant.

Tone: warm, professional, and brief. Get to the point without being curt.

You help with three things above all else:
1. Reminders — remembering things for the user.
2. Performing tasks on the user's behalf.
3. Drafting messages for the user to review.

You have tools for all three. Use a tool whenever it would actually
accomplish what the user asked, rather than just describing what you would
do. Drafting a message only ever saves a draft for the user to review —
you cannot send anything, so never imply that a message has gone out.
"""


class ConversationLoop:
    """Holds in-memory conversation history and drives one turn at a time."""

    def __init__(self, system_prompt=SYSTEM_PROMPT, registry=None):
        self.system_prompt = system_prompt
        self.registry = registry or build_default_registry()
        self.history = []

    def send(self, user_text, on_text=None, on_tool_call=None, on_tool_result=None):
        """Send a user turn, running tool-call rounds until the model has a
        final reply. `on_text` is called with reply text as it streams in;
        `on_tool_call`/`on_tool_result` are optional hooks for surfacing tool
        activity (the CLI uses them to print what's happening).

        On failure, the entire turn (including any tool rounds already run
        as part of it) is rolled back out of history, so the next attempt
        just retries the same user turn cleanly.
        """
        checkpoint = len(self.history)
        self.history.append({"role": "user", "content": user_text})

        try:
            for _ in range(MAX_TOOL_ROUNDS):
                final = run_turn(
                    self.history,
                    self.system_prompt,
                    tools=self.registry.to_anthropic_tools(),
                    on_text=on_text,
                )
                self.history.append(
                    {"role": "assistant", "content": serialize_content_blocks(final.content)}
                )

                if final.stop_reason != "tool_use":
                    return

                tool_results = []
                for block in final.content:
                    if block.type != "tool_use":
                        continue
                    if on_tool_call:
                        on_tool_call(block.name, block.input)
                    try:
                        result_text = self.registry.call(block.name, block.input)
                        is_error = False
                    except ToolError as exc:
                        result_text = str(exc)
                        is_error = True
                    if on_tool_result:
                        on_tool_result(block.name, result_text, is_error)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_text,
                            "is_error": is_error,
                        }
                    )
                self.history.append({"role": "user", "content": tool_results})
            else:
                if on_text:
                    on_text("\n[stopped: too many tool calls in a row]")
        except ProviderError:
            del self.history[checkpoint:]
            raise
