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

    def run_task(self, task_text):
        """Run one delegated task to completion and return the specialist's
        final text reply (never raises ToolError/ProviderError itself —
        griffin/tools/delegate.py is what turns a failure into one)."""
        loop = ConversationLoop(
            system_prompt=self._system_prompt,
            registry=self._build_registry(self._config),
            config=self._config,
        )
        chunks = []
        loop.send(task_text, on_text=chunks.append, on_confirm=self._confirm)
        text = "".join(chunks).strip()
        return text or "(no reply)"
