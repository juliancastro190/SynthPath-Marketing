"""The tool registry: the one place tools get registered and looked up.

Adding a new capability should mean writing one self-contained tool module
and registering it in `build_default_registry` below — never editing the
conversation loop itself.
"""

from dataclasses import dataclass
from typing import Callable


class ToolError(Exception):
    """Raised by a tool handler. The message is safe to show the model and the user."""


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], str]
    # Flagged here, enforced by Tier 6's confirmation gate: does calling this
    # tool send, spend, delete, or change a setting? None of the Tier 2 tools
    # do yet (drafting a message deliberately stops short of sending it), but
    # every tool declares this explicitly so the gate has something to read.
    requires_confirmation: bool = False


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def to_anthropic_tools(self):
        """The registry rendered as the `tools` param the model sees each turn."""
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in self._tools.values()
        ]

    def requires_confirmation(self, name):
        return self._tools[name].requires_confirmation

    def call(self, name, tool_input):
        """Run a tool by name. Never raises anything but ToolError."""
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(f"No such tool: '{name}'.")
        try:
            return tool.handler(tool_input)
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError(f"The '{name}' tool failed: {exc}")


def build_default_registry():
    # Imported lazily to avoid a circular import: each tool module (and the
    # memory store, and the heartbeat's notice inbox) imports Tool/ToolError
    # from this module at the top of its file.
    from griffin.heartbeat import notices
    from griffin.memory import store as memory
    from griffin.tools import drafts, reminders, tasks

    registry = ToolRegistry()
    for tool in [*reminders.TOOLS, *tasks.TOOLS, *drafts.TOOLS, *memory.TOOLS, *notices.TOOLS]:
        registry.register(tool)
    return registry
