"""Drafts — capability #3: "draft messages for me."

Drafting only ever writes a draft for the user to review. Sending is a
consequential action per AGENT.md's confirmation list, so it deliberately
is not something this tool group can do yet — that arrives with the
confirmation gate in Tier 6, wired to an actual send capability.
"""

import uuid
from datetime import datetime, timezone

from griffin import storage
from griffin.tools.registry import Tool, ToolError

FILENAME = "drafts.json"


def _load():
    return storage.load(FILENAME, [])


def _save(drafts):
    storage.save(FILENAME, drafts)


def draft_message(tool_input):
    body = (tool_input.get("body") or "").strip()
    if not body:
        raise ToolError("A draft needs a non-empty body.")
    recipient = (tool_input.get("recipient") or "").strip() or None
    subject = (tool_input.get("subject") or "").strip() or None

    drafts = _load()
    draft = {
        "id": uuid.uuid4().hex[:8],
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    drafts.append(draft)
    _save(drafts)

    return (
        f'Draft saved [id={draft["id"]}] — nothing has been sent.\n'
        f'Recipient: {recipient or "(none)"}\n'
        f'Subject: {subject or "(none)"}\n\n{body}'
    )


def list_drafts(tool_input):
    drafts = _load()
    if not drafts:
        return "No saved drafts."
    lines = [
        f'- [{d["id"]}] to {d["recipient"] or "(no recipient)"}: {d["subject"] or "(no subject)"}'
        for d in drafts
    ]
    return "\n".join(lines)


TOOLS = [
    Tool(
        name="draft_message",
        description=(
            "Write a draft message (e.g. an email or text) for the user to "
            "review. This only saves a draft — it never sends anything, "
            "under any circumstances. Use this when the user asks you to "
            "write, draft, or compose a message on their behalf."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "description": "Who the message is for (name, address, etc). Optional.",
                },
                "subject": {"type": "string", "description": "Optional subject line."},
                "body": {"type": "string", "description": "The full message text."},
            },
            "required": ["body"],
        },
        handler=draft_message,
    ),
    Tool(
        name="list_drafts",
        description="List previously saved message drafts. Use this when the user asks to see drafts you've written.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=list_drafts,
    ),
]
