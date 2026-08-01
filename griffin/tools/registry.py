"""The tool registry: the one place tools get registered and looked up.

Adding a new capability should mean writing one self-contained tool module
and registering it in `build_default_registry` below — never editing the
conversation loop itself.
"""

from dataclasses import dataclass
from typing import Callable, Optional


class ToolError(Exception):
    """Raised by a tool handler. The message is safe to show the model and the user."""


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], str]
    # Whether this tool must get the user's explicit yes before running is
    # decided by config.yaml's tools.requires_confirmation list (Tier 6),
    # not hardcoded here — build_default_registry applies it below. This
    # default only matters for tools built outside that path (e.g. tests).
    requires_confirmation: bool = False
    # Optional: given the tool's input, describe in plain language what
    # it's about to do — shown to the user by the confirmation gate. Falls
    # back to a generic rendering of the call if not provided.
    describe: Optional[Callable[[dict], str]] = None


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

    def describe(self, name, tool_input):
        """A plain-language description of what a call is about to do,
        for the confirmation gate to show the user."""
        tool = self._tools.get(name)
        if tool is None:
            return f"{name}({tool_input})"
        if tool.describe is not None:
            try:
                return tool.describe(tool_input)
            except Exception:
                pass
        return f"call {name} with {tool_input}"

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


def build_default_registry(config=None):
    # Imported lazily to avoid a circular import: each tool module (and the
    # memory store, and the heartbeat's notice inbox) imports Tool/ToolError
    # from this module at the top of its file.
    from griffin.heartbeat import notices
    from griffin.memory import store as memory
    from griffin.project_config import load_config
    from griffin.tools import drafts, etsy, reminders, tasks

    config = config if config is not None else load_config()
    confirm_names = set(config.get("tools", {}).get("requires_confirmation", []))

    registry = ToolRegistry()
    for tool in [*reminders.TOOLS, *tasks.TOOLS, *drafts.TOOLS, *memory.TOOLS, *notices.TOOLS, *etsy.TOOLS]:
        # Tool objects are module-level singletons reused across calls, so
        # this must set the flag both ways rather than only ever turning
        # it on — otherwise a later build with a different config could
        # inherit a stale True from an earlier one.
        tool.requires_confirmation = tool.name in confirm_names
        registry.register(tool)
    return registry
