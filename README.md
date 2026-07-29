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
conversation until you quit (Ctrl+C) — restarting forgot everything before
Tier 4 added durable memory below.

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
verify the actual voice round-trip yourself** once you're on a machine with
a mic and speakers.

## Tier 4 — memory

Griffin now remembers durable facts about you across restarts, separate
from the in-session conversation history. Facts live as plain JSON in
`data/memory.json` — one fact per entry, so it's easy to open, correct, or
delete by hand. They're loaded into the system prompt fresh at the start of
every turn, framed explicitly as background knowledge rather than
instructions, so a stored fact can never quietly bypass your judgment or
the confirmation gate arriving in Tier 6.

Tools: `remember` / `update_memory` / `forget` / `list_memories`. Try:

```
You: remember that I prefer morning meetings
You: what do you remember about me?
```

Then quit (Ctrl+C) and run `main.py` again — Griffin should already know
it without being told twice. Open `data/memory.json`, hand-edit a fact, and
run again to confirm your edit sticks.

`griffin/storage.py` (moved from `griffin/tools/storage.py`) is the shared
plain-JSON persistence helper — reminders, tasks, drafts, and memory all
use it, since it was the same few lines of logic either way.

## Tier 5 — heartbeat

Griffin can now notice things without being asked, via a background loop
that's completely separate from the conversation loop — `heartbeat_main.py`
runs on its own, independent of whether `main.py` or `voice_main.py` happens
to be open. What gets checked and how often lives in `heartbeat.yaml`, not
in code:

```
poll_interval_seconds: 30
quiet_hours: { start: "22:00", end: "08:00" }
checks:
  - name: stale_open_items
    type: stale_open_items
    interval_seconds: 300
    stale_after_minutes: 1440   # 24h
    alert_threshold: 3          # more than this -> worth interrupting for
```

The one built-in check (`griffin/heartbeat/checks.py`) looks for reminders
or tasks that have sat open a long time. Below the threshold it's just a
quiet log entry; above it, it's an "alert" — printed live to the
heartbeat's own terminal (unless it's quiet hours) and, either way, filed
into `data/heartbeat_notices.json` so it's never lost. Both `main.py` and
`voice_main.py` show every undismissed notice under "While you were away"
at startup, whether or not you were watching the heartbeat run — that's
the guarantee that nothing noticed while you're gone gets dropped. Notices
stay pending (and keep reappearing at startup) until you dismiss them:

```
You: what's pending?
You: dismiss that
```

The schedule itself survives restarts too (`data/heartbeat_state.json`
tracks when each check is next due), and a check that's still running
when its next tick comes up gets skipped rather than stacked.

Run it (in its own terminal, alongside `main.py` if you like):

```
.venv/bin/python heartbeat_main.py
```

To try it quickly: lower `stale_after_minutes` and `alert_threshold` to 0
in `heartbeat.yaml`, add a task or reminder, and watch an alert print
within one `interval_seconds`. I verified the full mechanics myself in this
sandbox — no hardware needed here — including genuine restart-safety (a
fresh `HeartbeatRunner` reading persisted schedule state from disk doesn't
refire early), the no-pile-up guard under a deliberately slow check, quiet
hours suppressing the live print while still filing the notice, and the
full "seed a notice → see it in `main.py` → dismiss it → gone next run"
loop end-to-end against the real `data/` directory.

The kill switch to pause all of this at once, plus folding `heartbeat.yaml`
into a single project-wide config, arrives in Tier 6.

---

Digital Marketing Platform
