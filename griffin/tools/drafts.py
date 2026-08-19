"""Drafts — capability #3: "draft messages for me."

Drafting only ever writes a draft for the user to review; nothing here
sends anything. Sending (Tier 9, griffin/tools/send.py) is a separate,
confirmation-gated tool that acts on a draft saved here — get_draft and
mark_sent below are what let it look up a draft and record that it went
out, without duplicating this module's storage access.
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


def get_draft(draft_id):
    """Return the draft dict for `draft_id`, or None if no such draft."""
    for draft in _load():
        if draft["id"] == draft_id:
            return draft
    return None


def mark_sent(draft_id, when):
    """Record that a draft was sent (Tier 9's send_email calls this after
    a successful send). `when` is an ISO timestamp string."""
    drafts = _load()
    for draft in drafts:
        if draft["id"] == draft_id:
            draft["sent_at"] = when
            _save(drafts)
            return


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
        "sent_at": None,
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
        f'{" (sent " + d["sent_at"] + ")" if d.get("sent_at") else ""}'
        for d in drafts
    ]
    return "\n".join(lines)


TOOLS = [
    Tool(
        name="draft_message",
        description=(
            "Write a draft message (e.g. an email or text) for the user to "
            "review. This only saves a draft — it never sends by itself, "
            "under any circumstances. Sending (if the user approves) is the "
            "separate send_email tool, which acts on a saved draft. Use "
            "this when the user asks you to write, draft, or compose a "
            "message on their behalf."
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
