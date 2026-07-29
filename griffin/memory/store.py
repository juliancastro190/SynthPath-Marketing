"""Long-term memory: durable facts about the user that survive a restart.

One fact per entry, written as a plain statement — small and legible so
they're easy to review, correct, or delete by hand in data/memory.json.
This is deliberately not a place for passing chatter; the in-session
conversation history already covers that. Facts get loaded into the
system prompt as background knowledge, never as instructions the model
should obey — see loop.py's memory framing.
"""

import uuid
from datetime import datetime, timezone

from griffin import storage
from griffin.tools.registry import Tool, ToolError

FILENAME = "memory.json"


def _load():
    return storage.load(FILENAME, [])


def _save(facts):
    storage.save(FILENAME, facts)


def list_facts():
    """All stored facts, in the order they were learned. Used to build the
    system prompt at the start of every turn — not exposed as a tool since
    the model already has this in context without asking."""
    return _load()


def add_fact(tool_input):
    text = (tool_input.get("text") or "").strip()
    if not text:
        raise ToolError("A memory needs non-empty text.")

    facts = _load()
    fact = {
        "id": uuid.uuid4().hex[:8],
        "text": text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    facts.append(fact)
    _save(facts)
    return f'Remembered: "{text}" [id={fact["id"]}]'


def update_fact(tool_input):
    fact_id = (tool_input.get("id") or "").strip()
    text = (tool_input.get("text") or "").strip()
    if not text:
        raise ToolError("An updated memory needs non-empty text.")

    facts = _load()
    for fact in facts:
        if fact["id"] == fact_id:
            fact["text"] = text
            _save(facts)
            return f'Updated memory [{fact_id}]: "{text}"'
    raise ToolError(f"No memory found with id '{fact_id}'.")


def remove_fact(tool_input):
    fact_id = (tool_input.get("id") or "").strip()
    facts = _load()
    remaining = [f for f in facts if f["id"] != fact_id]
    if len(remaining) == len(facts):
        raise ToolError(f"No memory found with id '{fact_id}'.")
    _save(remaining)
    return f"Forgot memory [{fact_id}]."


def list_facts_tool(tool_input):
    facts = _load()
    if not facts:
        return "No stored memories."
    return "\n".join(f'- [{f["id"]}] {f["text"]}' for f in facts)


TOOLS = [
    Tool(
        name="remember",
        description=(
            "Save a durable fact about the user for future conversations — "
            "a preference, identity, or decision. Use this when the user "
            "tells you something worth carrying forward long-term, e.g. "
            "'I prefer morning meetings' or 'my dog's name is Biscuit.' "
            "Not for one-off details only relevant to this conversation — "
            "the ordinary conversation history already covers those."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The fact to remember, as a single plain statement.",
                },
            },
            "required": ["text"],
        },
        handler=add_fact,
    ),
    Tool(
        name="update_memory",
        description="Correct or replace a previously stored memory, given its id, when it's become stale or wrong.",
        input_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "The memory's id."},
                "text": {"type": "string", "description": "The corrected statement."},
            },
            "required": ["id", "text"],
        },
        handler=update_fact,
    ),
    Tool(
        name="forget",
        description="Remove a previously stored memory, given its id. Use when the user asks you to forget something, or it's no longer true.",
        input_schema={
            "type": "object",
            "properties": {"id": {"type": "string", "description": "The memory's id."}},
            "required": ["id"],
        },
        handler=remove_fact,
    ),
    Tool(
        name="list_memories",
        description=(
            "List everything currently remembered about the user, with ids. "
            "Use this if the user asks what you remember about them, or "
            "before calling update_memory/forget if you don't already have "
            "the id handy."
        ),
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=list_facts_tool,
    ),
]
