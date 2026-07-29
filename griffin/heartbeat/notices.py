"""The notice inbox: every notice a check has raised, held here until the
user explicitly dismisses it.

This is what guarantees nothing a check notices while you're away gets
lost — the CLI shows every *undismissed* notice at startup, not just ones
raised since the last time it happened to be open, so closing the app
(or the heartbeat noticing something at 3am) never silently drops it.
"""

import uuid
from datetime import datetime, timezone

from griffin import storage
from griffin.tools.registry import Tool, ToolError

FILENAME = "heartbeat_notices.json"


def _load():
    return storage.load(FILENAME, [])


def _save(notices):
    storage.save(FILENAME, notices)


def add_notice(check_name, message, severity="info"):
    """severity: "info" (calm log only) or "alert" (worth interrupting for,
    subject to quiet hours)."""
    notices = _load()
    notice = {
        "id": uuid.uuid4().hex[:8],
        "check_name": check_name,
        "message": message,
        "severity": severity,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "delivered_at": None,
        "dismissed_at": None,
    }
    notices.append(notice)
    _save(notices)
    return notice


def undismissed():
    return [n for n in _load() if not n["dismissed_at"]]


def mark_delivered(notice_ids):
    notice_ids = set(notice_ids)
    notices = _load()
    now = datetime.now(timezone.utc).isoformat()
    changed = False
    for n in notices:
        if n["id"] in notice_ids and not n["delivered_at"]:
            n["delivered_at"] = now
            changed = True
    if changed:
        _save(notices)


def dismiss(tool_input):
    notice_id = (tool_input.get("id") or "").strip()
    notices = _load()
    for n in notices:
        if n["id"] == notice_id:
            if n["dismissed_at"]:
                return f"Notice [{notice_id}] was already dismissed."
            n["dismissed_at"] = datetime.now(timezone.utc).isoformat()
            _save(notices)
            return f"Dismissed: {n['message']}"
    raise ToolError(f"No notice found with id '{notice_id}'.")


def print_startup_notices():
    """Print any undismissed notices and mark them delivered. Called by
    both the text and voice CLIs on startup so nothing a check noticed
    while you were away goes unseen, no matter which interface you happen
    to open first. Notices stay in the inbox (and reappear here) until
    explicitly dismissed — being shown once isn't the same as being
    handled."""
    pending = undismissed()
    if not pending:
        return
    print("While you were away:")
    for n in pending:
        print(f"  - [{n['id']}] {n['message']}")
    print()
    mark_delivered([n["id"] for n in pending])


def list_notices(tool_input):
    pending = undismissed()
    if not pending:
        return "No pending notices."
    return "\n".join(f'- [{n["id"]}] ({n["severity"]}) {n["message"]}' for n in pending)


TOOLS = [
    Tool(
        name="list_notices",
        description=(
            "List proactive notices Griffin's background checks have "
            "raised that haven't been dismissed yet. Use this if the user "
            "asks what's pending or what Griffin has noticed."
        ),
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=list_notices,
    ),
    Tool(
        name="dismiss_notice",
        description="Dismiss a proactive notice, given its id, once the user has seen and handled it (or doesn't care about it).",
        input_schema={
            "type": "object",
            "properties": {"id": {"type": "string", "description": "The notice's id."}},
            "required": ["id"],
        },
        handler=dismiss,
    ),
]
