"""SpecialistAgent — the shape every team member shares.

A specialist is not a new kind of brain: it's Tier 1's conversation loop
plus Tier 2's tool registry (and Tier 6's confirmation gate, for free),
just pointed at a narrower job via its own system prompt and its own
scoped set of tools. Delegating to one (griffin/tools/delegate.py) is just
another tool call from the orchestrator's point of view — the specialist
runs its own tool-call rounds to completion on a fresh, empty history and
hands back only its final text reply. Specialists don't carry memory
between delegated tasks; Griffin's own memory store (Tier 4) is still the
one durable memory in the system.

A specialist's own tool calls happen inside a single delegate_task call, so
the outer loop's on_tool_call/on_tool_result hooks (what cli.py and
voice_cli.py wire up for Griffin's own tool use) never see them — from
Griffin's side, delegate_task looks like one call that takes a while and
then returns text. To keep that work visible instead of silent, run_task
prints its own `[name using tool: ...]` / `[name result: ...]` lines
directly to the console, same bracket format cli.py uses for Griffin,
regardless of which interface triggered the delegation. Every one of these
calls is also in data/audit.log (Tier 6) either way, live or not.
"""

from griffin.brain.loop import ConversationLoop


class SpecialistAgent:
    def __init__(self, name, description, system_prompt, build_registry, config=None):
        self.name = name
        self.description = description
        self._system_prompt = system_prompt
        self._build_registry = build_registry
        # None means "load config.yaml fresh per task" — same convention as
        # ConversationLoop itself. A fixed dict is mainly useful for tests.
        self._config = config

    def _confirm(self, tool_name, tool_input, description):
        # Delegation runs synchronously inside a tool call, with no access
        # to whichever interface (text CLI, voice) is driving the outer
        # turn, so this always falls back to a plain blocking prompt — the
        # safe default is asking, not skipping the gate because the fancier
        # per-interface confirm isn't reachable from here.
        answer = input(f"\n{self.name} wants to: {description}\nProceed? [y/N]: ").strip().lower()
        return answer in ("y", "yes")

    def _on_tool_call(self, name, tool_input):
        print(f"\n  [{self.name} using tool: {name}({tool_input})]")

    def _on_tool_result(self, name, result_text, is_error):
        tag = "error" if is_error else "result"
        print(f"  [{self.name} {tag}: {result_text}]")

    def run_task(self, task_text):
        """Run one delegated task to completion and return the specialist's
        final text reply (never raises ToolError/ProviderError itself —
        griffin/tools/delegate.py is what turns a failure into one). Prints
        its own tool activity live to the console as it goes — see the
        module docstring for why that can't just flow through the outer
        loop's own hooks."""
        loop = ConversationLoop(
            system_prompt=self._system_prompt,
            registry=self._build_registry(self._config),
            config=self._config,
        )
        chunks = []
        loop.send(
            task_text,
            on_text=chunks.append,
            on_tool_call=self._on_tool_call,
            on_tool_result=self._on_tool_result,
            on_confirm=self._confirm,
        )
        text = "".join(chunks).strip()
        return text or "(no reply)"
