"""Delegation — what turns Griffin from a single assistant into a small
team. Lets the orchestrator hand a task off to a specialist agent
(griffin/agents/team.py) instead of doing it itself. From the outer
conversation loop's point of view this is just another tool call: it runs
to completion and returns text. The specialist runs its own tool-call
rounds against its own scoped registry, with its own confirmation gate for
anything consequential it tries to do — Griffin never sees or approves the
specialist's intermediate tool calls, only the final answer.
"""

from griffin.agents.team import SPECIALISTS
from griffin.tools.registry import Tool, ToolError


def delegate_task(tool_input):
    name = (tool_input.get("specialist") or "").strip()
    task = (tool_input.get("task") or "").strip()
    if not task:
        raise ToolError("A delegated task needs a non-empty description.")

    specialist = SPECIALISTS.get(name)
    if specialist is None:
        available = ", ".join(sorted(SPECIALISTS))
        raise ToolError(f"No such specialist: '{name}'. Available: {available}.")

    try:
        return specialist.run_task(task)
    except Exception as exc:
        # Whatever went wrong inside the specialist's own loop (a
        # ProviderError, an unhandled exception in one of its tools) — the
        # orchestrator still needs a plain-language result back, not a
        # crash, exactly like any other tool failure.
        raise ToolError(f"{specialist.name} couldn't complete the task: {exc}")


def _roster_description():
    return "\n".join(f"- {agent.name}: {agent.description}" for agent in SPECIALISTS.values())


TOOLS = [
    Tool(
        name="delegate_task",
        description=(
            "Hand a task off to a specialist teammate instead of doing it yourself. Use this "
            "whenever a task squarely matches a specialist's job below — they have tools and "
            "context you don't. Wait for their reply, then relay or build on it; don't repeat "
            "work they already did.\n\nSpecialists:\n" + _roster_description()
        ),
        input_schema={
            "type": "object",
            "properties": {
                "specialist": {
                    "type": "string",
                    "description": "Which specialist to delegate to.",
                    "enum": sorted(SPECIALISTS),
                },
                "task": {
                    "type": "string",
                    "description": "The task, in plain language, for the specialist to do.",
                },
            },
            "required": ["specialist", "task"],
        },
        handler=delegate_task,
    ),
]
