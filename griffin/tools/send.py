"""Send — Tier 9. The real, consequential half of "draft messages for me"
(Tier 2's drafts.py stops at saving a draft, deliberately). send_email
acts on an existing draft rather than taking fresh recipient/subject/body
directly: sending only ever happens to something that was already saved
and can be reviewed, never to text composed and dispatched in the same
breath. It's plain SMTP (stdlib smtplib, no new dependency) so it works
with whatever email account the user already has.

send_email is in config.yaml's requires_confirmation list — sending a
message is exactly the "never without asking first" case AGENT.md's
interview called out — so this tool only ever runs after the Tier 6 gate
approves it. That also means a heartbeat-triggered task (Tier 8) can never
send anything unattended: griffin/heartbeat/checks.py's team_task declines
every confirmation-gated call by default, this one included.
"""

import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from griffin.config import SMTP_FROM_ADDRESS, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USERNAME
from griffin.tools.drafts import get_draft, mark_sent
from griffin.tools.registry import Tool, ToolError


def _require_smtp_config():
    missing = [
        name
        for name, value in [
            ("SMTP_HOST", SMTP_HOST),
            ("SMTP_USERNAME", SMTP_USERNAME),
            ("SMTP_PASSWORD", SMTP_PASSWORD),
        ]
        if not value
    ]
    if missing:
        raise ToolError(
            "Email sending isn't configured — missing "
            + ", ".join(missing)
            + " in .env (see .env.example for setup, including Gmail app-password steps)."
        )


def send_email(tool_input):
    draft_id = (tool_input.get("draft_id") or "").strip()
    if not draft_id:
        raise ToolError("send_email needs a draft_id — draft the message first with draft_message.")

    draft = get_draft(draft_id)
    if draft is None:
        raise ToolError(f"No draft found with id '{draft_id}'. Use list_drafts to see saved drafts.")
    if draft.get("sent_at"):
        raise ToolError(f"Draft '{draft_id}' was already sent at {draft['sent_at']} — draft a new message to send again.")
    if not draft.get("recipient"):
        raise ToolError(f"Draft '{draft_id}' has no recipient. Update it (draft a new one with a recipient) before sending.")

    _require_smtp_config()

    message = EmailMessage()
    message["From"] = SMTP_FROM_ADDRESS
    message["To"] = draft["recipient"]
    message["Subject"] = draft.get("subject") or "(no subject)"
    message.set_content(draft["body"])

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)
    except smtplib.SMTPException as exc:
        raise ToolError(f"Sending failed: {exc}")
    except OSError as exc:
        raise ToolError(f"Couldn't reach the SMTP server ({SMTP_HOST}:{SMTP_PORT}): {exc}")

    sent_at = datetime.now(timezone.utc).isoformat()
    mark_sent(draft_id, sent_at)
    return f"Sent to {draft['recipient']} at {sent_at}. Subject: {draft.get('subject') or '(no subject)'}"


def _describe_send(tool_input):
    draft_id = (tool_input.get("draft_id") or "").strip()
    draft = get_draft(draft_id)
    if draft is None:
        return f"send draft '{draft_id}' (not found)"
    return (
        f'send this email to {draft.get("recipient") or "(no recipient)"}: '
        f'"{draft.get("subject") or "(no subject)"}"\n\n{draft["body"]}'
    )


TOOLS = [
    Tool(
        name="send_email",
        description=(
            "Send a previously saved draft (see draft_message/list_drafts) as a real email. "
            "This is the only tool that actually sends anything — always requires the user's "
            "explicit yes first. Needs a draft_id, not fresh text; draft the message first if "
            "one doesn't already exist."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "draft_id": {"type": "string", "description": "The id of the draft to send (from draft_message or list_drafts)."},
            },
            "required": ["draft_id"],
        },
        handler=send_email,
        describe=_describe_send,
    ),
]
