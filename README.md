# Griffin

A voice-first AI assistant, built tier by tier. See `AGENT.md` for the full
spec (identity, capabilities, stack, and safety rules).

## Tier 1 — text conversation loop

Setup:

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # then add your ANTHROPIC_API_KEY
```

Run:

```
.venv/bin/python main.py
```

Type a message and press Enter. Griffin streams its reply and remembers the
conversation until you quit (Ctrl+C) — restarting forgets everything; durable
memory arrives in Tier 4.

## Tier 2 — tools

Griffin can now act, not just talk, via a small tool registry
(`griffin/tools/registry.py`). The first three tools map straight to the
three capabilities from the interview:

- `add_reminder` / `list_reminders` / `complete_reminder`
- `add_task` / `list_tasks` / `complete_task`
- `draft_message` / `list_drafts` — saves a draft only; nothing is ever sent

State persists as plain JSON under `data/` (git-ignored) so reminders/tasks/
drafts survive a restart even though the conversation itself doesn't yet.
When the model calls a tool, the CLI prints what it called and the result so
you can see the tool use as it happens — try:

```
You: remind me to call the dentist tomorrow
You: what's on my reminder list?
You: draft a message to Sam saying I'll be late
```

If a tool fails (e.g. completing a reminder id that doesn't exist), Griffin
gets a plain-language error back and explains it to you instead of crashing.

---

Digital Marketing Platform
