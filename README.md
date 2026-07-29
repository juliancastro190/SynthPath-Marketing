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

## Tier 3 — voice (push-to-talk)

Griffin can now hear and speak, wrapped around the exact same brain and
tools from Tiers 1–2. Hold a key, talk, release — Griffin transcribes what
you said, runs it through the normal conversation loop, and speaks the
reply back as it's generated.

Extra prerequisites beyond `pip install -r requirements.txt`:

- **`mpv`** installed and on your `PATH` (`brew install mpv` / `apt install
  mpv` / `choco install mpv`) — used to play streamed speech, and to let
  Griffin be interrupted instantly by killing playback.
- **Deepgram** and **ElevenLabs** API keys in `.env` (see `.env.example`).
- On macOS, grant your terminal **Accessibility** permission (System
  Settings → Privacy & Security) so the push-to-talk key can be detected
  globally.

Run:

```
.venv/bin/python voice_main.py
```

Hold the configured key (default: **right Ctrl** — set `GRIFFIN_PTT_KEY` in
`.env` to `ctrl_l`, `alt_r`, `alt_l`, or `space` instead), speak, and
release. What Griffin heard is printed as a transcript next to its spoken
reply, so you can tell at a glance whether a wrong answer was a mishearing
or a misunderstanding. Press the key again while Griffin is still talking
to interrupt it and start a new turn. The text interface (`main.py`) keeps
working exactly as before — it's the fastest way to debug the brain without
talking to your computer.

I haven't been able to test real microphone/speaker hardware or a live
Deepgram/ElevenLabs call in the sandbox this was built in — the mechanics
(recording → WAV, sentence-chunked streaming to TTS, interrupt-by-killing-
playback, key-hold detection) are unit-tested with mocks, but **you should
verify the actual voice round-trip yourself** per the checklist below.

---

Digital Marketing Platform
