"""Send — Tier 9. The real, consequential half of "draft messages for me"
(Tier 2's drafts.py stops at saving a draft, deliberately). send_email
acts on an existing draft rather than taking fresh recipient/subject/body
directly: sending only ever happens to something that was already saved
and can be reviewed, never to text composed and dispatched in the same
breath.

Originally plain SMTP (stdlib smtplib) — that turned out to be a dead
end once this ran on Railway (Tier 10): live-tested, both Gmail's and
iCloud's mail servers were unreachable on port 587 from that deployed
instance ("Network is unreachable" / a hard timeout), while the exact
same instance talks to Anthropic's API and Discord's gateway fine,
because those are HTTPS. Cloud platforms commonly block outbound SMTP
entirely as an anti-spam policy — no code fix works around that. Resend's
API is plain HTTPS (via `requests`, no new dependency), so it works
identically on a laptop or on Railway.

send_email is in config.yaml's requires_confirmation list — sending a
message is exactly the "never without asking first" case AGENT.md's
interview called out — so this tool only ever runs after the Tier 6 gate
approves it. That also means a heartbeat-triggered task (Tier 8) can never
send anything unattended: griffin/heartbeat/checks.py's team_task declines
every confirmation-gated call by default, this one included.
"""

from datetime import datetime, timezone

import requests

from griffin.config import RESEND_API_KEY, RESEND_FROM_ADDRESS
from griffin.tools.drafts import get_draft, mark_sent
from griffin.tools.registry import Tool, ToolError

RESEND_API_URL = "https://api.resend.com/emails"


def _require_resend_config():
    if not RESEND_API_KEY:
        raise ToolError(
            "Email sending isn't configured — missing RESEND_API_KEY in .env "
            "(see .env.example for setup)."
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

    _require_resend_config()

    payload = {
        "from": RESEND_FROM_ADDRESS,
        "to": [draft["recipient"]],
        "subject": draft.get("subject") or "(no subject)",
        "text": draft["body"],
    }
    try:
        response = requests.post(
            RESEND_API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            timeout=15,
        )
    except requests.RequestException as exc:
        raise ToolError(f"Couldn't reach Resend's API: {exc}")

    if response.status_code >= 400:
        # Resend's error responses are JSON with a "message" field when
        # possible — most common cause here: RESEND_FROM_ADDRESS is the
        # unverified-domain placeholder (onboarding@resend.dev) and the
        # recipient isn't the address the Resend account itself is signed
        # up with, which that placeholder can only send to.
        try:
            detail = response.json().get("message", response.text)
        except ValueError:
            detail = response.text
        raise ToolError(f"Resend rejected the send ({response.status_code}): {detail[:300]}")

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
