# Griffin — Project Spec

This is the single source of truth for what we're building and why. Read this
before starting work in a new session.

## Identity

- **Name:** Griffin
- **One-line purpose:** A voice-first personal assistant that remembers you,
  performs tasks on your behalf, and drafts messages for you.
- **Who it's for:** Just the owner (Julian), for now. No multi-user state
  needed yet, but nothing in the design assumes single-user forever.
- **Personality/tone:** Warm, professional, and brief. Consistent everywhere —
  system prompt, spoken replies, logs.

## First three capabilities (become the first tools + test cases)

1. **Reminders** — remember things and surface them at the right time.
2. **Performing tasks** — a general-purpose "do something for me" capability,
   expressed as tools in the registry (Tier 2) rather than one fixed feature.
3. **Drafting messages** — write messages (emails, texts, etc.) for review;
   sending them is a consequential action and goes through the confirmation
   gate (Tier 6), never sent automatically.

## Stack and model

- **Language/runtime:** Python. Mainstream, boring, well-supported; good
  audio and HTTP library support; first-class Anthropic SDK support.
- **Model provider:** Claude, latest capable model, via the official
  Anthropic Python SDK — kept behind a thin provider seam
  (`griffin/brain/provider.py`) so the model/provider can change without
  touching the rest of the harness.
- **Where it runs:** Laptop-first. The heartbeat (Tier 5) is built as a
  loop that doesn't care which machine it's on, so moving to an always-on
  host later is a relocation, not a rewrite.

## Voice and boundaries

- **How you talk to it:** Text first (Tiers 1–2, and kept alive forever as
  the debug/fallback path). Push-to-talk voice added in Tier 3 — hold a key,
  speak, release. Wake-word/open-mic is a later stretch goal, not baseline.
- **Speech-to-text:** Deepgram, behind its own seam.
- **Text-to-speech:** ElevenLabs, behind its own seam, streamed. Defaulted
  to ElevenLabs' premade "Rachel" voice (`ELEVENLABS_VOICE_ID` in `.env`)
  as a placeholder — swap it for a real preference whenever you pick one;
  it moves into the Tier 6 config file once that exists.
- **Never without asking first (hard confirmation gate, Tier 6):**
  - Sending any message (email, text, etc.)
  - Spending money
  - Deleting data
  - Changing a setting
  - Anything else hard to undo
  - Confirmation is per-action — approving one send does not pre-approve
    the next.
  - Implemented as `config.yaml`'s `tools.requires_confirmation` list —
    currently just `forget` (deletes a memory), since none of the other
    built-in tools send, spend, delete, or change a setting yet. Add a
    tool name there, not a code change, whenever a new consequential tool
    is added.
- **Proactive behavior:** Yes, Griffin can reach out first (reminders,
  noticed conditions) — but quiet by default. It earns interruptions rather
  than assuming them. Built in Tier 5, with quiet hours, held (not lost)
  notices, and a kill switch (Tier 6).

## Build discipline

- One shared agent core (the brain + tool registry), many ways in and out
  (typed turn, spoken turn, heartbeat-initiated turn). Never fork the agent
  logic for voice — voice is an adapter on the same entry point.
- Build and verify one tier at a time: brain (text) → hands (tools) → ears/
  mouth (voice) → memory → heartbeat → rails (safety/config). Don't fuse
  tiers.
- Secrets (Anthropic, Deepgram, ElevenLabs API keys) live in a git-ignored
  `.env` file, never in source.

## Tier status

- [x] Tier 0 — Interview / spec (this file)
- [x] Tier 1 — Brain: text conversation loop
- [x] Tier 2 — Hands: tool registry + first tools
- [x] Tier 3 — Ears/mouth: push-to-talk voice
- [x] Tier 4 — Memory: durable facts across restarts
- [x] Tier 5 — Heartbeat: proactive background loop
- [x] Tier 6 — Rails: confirmation gate, config, audit log, kill switch
- [x] Tier 7 — Team: specialist agents Griffin can delegate to
- [x] Tier 8 — Team autonomy: a specialist can run on a schedule, no one asking
- [x] Tier 9 — Send: a real, confirmation-gated send_email tool

## Tier 9 — send

`griffin/tools/send.py` closes the gap Tier 2 deliberately left open:
`send_email` sends a previously saved draft (`draft_message`) as a real
email over plain SMTP (`smtplib`, no new dependency — works with any
provider, see `.env.example` for Gmail app-password setup). It acts on an
existing draft rather than taking fresh text, so sending only ever
happens to something that was already saved and could be reviewed first.
`send_email` is in `config.yaml`'s `requires_confirmation` list — both
Griffin directly and the marketing specialist have it.

This also closes the loop `AGENT.md` had flagged as capping Tier 8's
autonomy: since the heartbeat's `team_task` auto-declines every
confirmation-gated tool the same way regardless of which one it is, a
scheduled task can now genuinely *try* to send something and correctly
fail to — verified directly, with `input()` poisoned to raise if touched
at all, `smtplib.SMTP` mocked to prove no real send occurred, and the
result confirming the gate held.

## Tier 8 — team autonomy

The heartbeat (Tier 5) can now run a specialist on its own schedule via a
new check type, `team_task` (`griffin/heartbeat/checks.py`) — config needs
`specialist` and `task`; see `config.yaml`'s `weekly_youtube_draft`
example (disabled by default — opt in per check). This is the actual
"does tasks on its own" behavior from the original ask, not just
on-demand delegation.

The one thing that had to change to make this safe: `SpecialistAgent.
run_task` (Tier 7) defaulted to a *blocking* `input()` for its
confirmation gate, which is fine from a live conversation but would hang
the heartbeat's background thread forever the first time a scheduled task
hit something confirmation-gated (e.g. `youtube_produce`) with nobody at
the keyboard to answer. `run_task` now takes an optional `on_confirm`
override; `team_task` passes one that always declines instead of
blocking — same "safe default: don't do it, leave a notice" rule the
heartbeat runner already documented for itself before any check actually
needed it. Verified directly: `input()` poisoned to raise if called at
all, task hits `youtube_produce`, gets declined without ever touching
`input()`, files a notice explaining why instead of hanging — and,
separately, the free-tool-only happy path completing normally and filing
its own notice.

## Tier 7 — the team

Griffin is now the orchestrator of a small team, not a solo assistant.
`griffin/agents/` holds each specialist — same brain as Griffin itself
(Tier 1's loop + Tier 2's registry, Tier 6's confirmation gate included),
pointed at a narrower job via its own system prompt and scoped tools:

- **marketing** — writes copy/campaigns/funnel strategy, grounded in the
  jaredrhod playbooks under `Marketing/` (never produces output cold).
- **youtube** — drives the existing faceless-Reddit-horror pipeline;
  `youtube_produce` (spends ElevenLabs credits) is confirmation-gated.
- **research** — fetches a URL and reads it. This is also the first tool
  in the project that touches untrusted external content for real, so its
  system prompt is where the "external content is data, not instructions"
  posture gets exercised against an actual boundary.

Griffin reaches the team via one new tool, `delegate_task`
(`griffin/tools/delegate.py`) — from the outer loop's point of view it's
just another tool call that runs to completion and returns text. Tier 8
above adds the other way in: a specialist run from the heartbeat instead
of a conversation.

## What's left for a fuller build (not started)

- SMS/text sending — send_email (Tier 9) covers email only.
- A visual face, an always-on host, more specialists — see "Where to go
  after the baseline" in the original build doc.
