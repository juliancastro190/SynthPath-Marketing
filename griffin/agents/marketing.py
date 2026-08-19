"""Marketing specialist — writes copy, campaigns, and funnel strategy the
way jaredrhod actually runs it: never cold, always grounded in the
playbooks under Marketing/ at the repo root. This is the same material the
jaredrhod-marketing Claude Code skill uses; here it's exposed as a read
tool instead, since this agent runs on the raw Anthropic SDK rather than
inside Claude Code.
"""

import os

from griffin.agents.base import SpecialistAgent
from griffin.tools.drafts import TOOLS as DRAFT_TOOLS
from griffin.tools.registry import Tool, ToolError, ToolRegistry, apply_confirmation_flags
from griffin.tools.send import TOOLS as SEND_TOOLS

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLAYBOOK_DIR = os.path.join(_REPO_ROOT, "Marketing")

SYSTEM_PROMPT = """You are the marketing specialist on a small AI team, delegated a task by \
Griffin (the orchestrator) or its user. You write marketing copy, \
campaigns, emails, ads, and funnel strategy the way jaredrhod actually \
runs it — never cold, always grounded in the playbooks under Marketing/.

Before writing anything:
1. Call list_playbooks, then read_playbook with "jareds-takes.md" — the \
   core principles everything else sits on.
2. If the task touches the funnel or overall strategy, also read \
   "the-fundamentals.md".
3. Read whichever playbook matches the specific task: copy/headlines/sales \
   or opt-in pages -> "marketing-copywriting.md"; long-form sales letters \
   -> "marketing-sales-letter.md"; email sequences/broadcasts -> \
   "marketing-email.md"; paid ads -> "marketing-fb-ads.md"; lead magnets \
   -> "marketing-lead-magnets.md"; content marketing -> \
   "marketing-content.md"; metrics -> "marketing-analytics.md".

Skipping step 1 is exactly the generic-AI-slop failure mode this team \
exists to avoid — never produce marketing output cold.

Once you've written the piece, save it with draft_message so the user can \
review it. Also include the finished copy directly in your reply, not \
just the tool call, so whoever delegated the task can see it immediately.

send_email actually sends a saved draft — only call it when you've been \
explicitly told to send (a draft_id, or "send that"/"send it"), never on \
your own initiative right after drafting. It always requires the user's \
yes first regardless; call it and react to the outcome rather than asking \
yourself."""


def _list_playbooks():
    if not os.path.isdir(PLAYBOOK_DIR):
        return []
    return sorted(f for f in os.listdir(PLAYBOOK_DIR) if f.endswith(".md"))


def list_playbooks(tool_input):
    files = _list_playbooks()
    return "\n".join(f"- {f}" for f in files) if files else "No playbooks found."


def read_playbook(tool_input):
    name = (tool_input.get("name") or "").strip()
    files = _list_playbooks()
    if name not in files:
        raise ToolError(f"No such playbook: '{name}'. Available: {', '.join(files) or '(none)'}.")
    with open(os.path.join(PLAYBOOK_DIR, name), encoding="utf-8") as f:
        return f.read()


MARKETING_TOOLS = [
    Tool(
        name="list_playbooks",
        description="List the available jaredrhod marketing playbook filenames.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=list_playbooks,
    ),
    Tool(
        name="read_playbook",
        description=(
            "Read one marketing playbook file by name (see list_playbooks). Always read "
            "jareds-takes.md first, before writing anything."
        ),
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Filename, e.g. 'jareds-takes.md'."}},
            "required": ["name"],
        },
        handler=read_playbook,
    ),
]


def build_marketing_registry(config=None):
    tools = [*MARKETING_TOOLS, *DRAFT_TOOLS, *SEND_TOOLS]
    apply_confirmation_flags(tools, config)
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


def build_marketing_agent(config=None):
    return SpecialistAgent(
        name="marketing",
        description=(
            "Writes marketing copy, campaigns, emails, ads, lead magnets, and funnel "
            "strategy, grounded in the jaredrhod playbooks. Saves finished pieces as drafts, "
            "and can send an approved draft as a real email."
        ),
        system_prompt=SYSTEM_PROMPT,
        build_registry=build_marketing_registry,
        config=config,
    )
