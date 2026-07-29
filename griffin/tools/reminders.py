"""Reminders — capability #1: "remind me of stuff."

This only records and lists reminders; it doesn't yet proactively notify
the user at the right time — that's the heartbeat's job (Tier 5).
"""

import uuid
from datetime import datetime, timezone

from griffin import storage
from griffin.tools.registry import Tool, ToolError

FILENAME = "reminders.json"


def _load():
    return storage.load(FILENAME, [])


def _save(reminders):
    storage.save(FILENAME, reminders)


def add_reminder(tool_input):
    text = (tool_input.get("text") or "").strip()
    if not text:
        raise ToolError("A reminder needs non-empty text.")
    when = (tool_input.get("when") or "").strip() or None

    reminders = _load()
    reminder = {
        "id": uuid.uuid4().hex[:8],
        "text": text,
        "when": when,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "done": False,
    }
    reminders.append(reminder)
    _save(reminders)

    when_note = f" (for {when})" if when else ""
    return f'Reminder saved{when_note}: "{text}" [id={reminder["id"]}]'


def list_reminders(tool_input):
    include_done = bool(tool_input.get("include_done", False))
    reminders = _load()
    if not include_done:
        reminders = [r for r in reminders if not r["done"]]
    if not reminders:
        return "No reminders." if include_done else "No open reminders."
    lines = []
    for r in reminders:
        note = f' (for {r["when"]})' if r["when"] else ""
        note += " (done)" if r["done"] else ""
        lines.append(f'- [{r["id"]}] {r["text"]}{note}')
    return "\n".join(lines)


def complete_reminder(tool_input):
    reminder_id = (tool_input.get("id") or "").strip()
    reminders = _load()
    for r in reminders:
        if r["id"] == reminder_id:
            r["done"] = True
            _save(reminders)
            return f'Marked reminder [{reminder_id}] as done: "{r["text"]}"'
    raise ToolError(f"No reminder found with id '{reminder_id}'.")


TOOLS = [
    Tool(
        name="add_reminder",
        description=(
            "Save a new reminder for the user. Use this when they ask to be "
            "reminded of something, e.g. 'remind me to call the dentist "
            "tomorrow.' This only records the reminder for later — it does "
            "not yet actively notify the user when the time comes."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "What to be reminded of."},
                "when": {
                    "type": "string",
                    "description": (
                        "Optional freeform time or date this reminder is for, "
                        "e.g. 'tomorrow morning' or '2026-08-01'."
                    ),
                },
            },
            "required": ["text"],
        },
        handler=add_reminder,
    ),
    Tool(
        name="list_reminders",
        description=(
            "List the user's reminders. Use this when they ask what they're "
            "reminded of, or what's on their list."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "include_done": {
                    "type": "boolean",
                    "description": "Include reminders already marked done. Defaults to false.",
                },
            },
            "required": [],
        },
        handler=list_reminders,
    ),
    Tool(
        name="complete_reminder",
        description=(
            "Mark a reminder as done, given its id (from add_reminder or "
            "list_reminders). Use when the user says they've handled "
            "something or no longer need to be reminded."
        ),
        input_schema={
            "type": "object",
            "properties": {"id": {"type": "string", "description": "The reminder's id."}},
            "required": ["id"],
        },
        handler=complete_reminder,
    ),
]
