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

---

Digital Marketing Platform
