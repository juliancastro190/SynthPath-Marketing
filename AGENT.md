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
- [x] Tier 10 — Discord bridge + always-on hosting
- [x] Tier 11 — Publisher: a confirmation-gated YouTube upload tool

## Tier 11 — publisher

The youtube specialist (Tier 7) produces a finished video and stops —
nothing puts it online. `publisher` (`griffin/agents/publisher.py`,
`griffin/youtube/upload.py`) closes that gap: `publish_youtube_video`
uploads an already-produced video to YouTube via the YouTube Data API v3.
Its own specialist rather than a third tool on `youtube` — producing
content and putting it live are different levels of consequence, and
separating them means a task that only asks for a script or draft video
can never accidentally reach the publish path.

`publish_youtube_video` is in `config.yaml`'s `requires_confirmation`
list, same as `send_email` and `youtube_produce` — the same "never
without asking" case AGENT.md's original interview called out, now
applied to a public channel instead of a private inbox. On top of that
gate it also defaults to `privacyStatus: private` unless a task
explicitly asks for `unlisted` or `public`, a second layer of safety on
top of the confirmation itself.

A plain API key can't authorize a video upload — this needs OAuth2 user
consent, done once via `youtube_auth.py` (repo root, run locally — it
opens a browser) to mint a refresh token; every upload after that
refreshes it silently, which is what lets this run from Railway or the
heartbeat and not just an interactive terminal. See `.env.example`'s
Tier 11 section for the Google Cloud project setup and the one real rough
edge: a Google Cloud OAuth app left in "Testing" status (the simplest
setup) has refresh tokens that expire after 7 days.

Verified with a mocked upload call: missing/unknown `story_id`, no
`video.mp4` yet, invalid `privacy_status`, the default-private/derived-
title path and every override, an upload failure surfacing as a normal
tool error, the confirmation gate actually being set, and — same check
every confirmation-gated tool gets — a heartbeat-triggered publish
declining without ever calling the upload function. I haven't exercised
this against a live YouTube channel or the real OAuth flow in this
sandbox.

## Tier 10 — Discord bridge + hosting

Griffin can now be reached from outside a local terminal.
`griffin/discord_bridge.py` (`discord_main.py`) chats over Discord DMs —
same brain as `main.py`, same confirmation gate, just a different way in
and out, exactly like Tier 3's voice mode. It also starts the heartbeat
in a background thread itself, so `discord_main.py` deployed once (see
`DEPLOY.md`, Railway) gives both remote chat and Tier 8's autonomy from
one process sharing one `data/` volume — the alternative (heartbeat and
chat as two separate deployments) would mean two divergent `data/`
directories, which was flagged as a real cost when Tier 8 was first
deployed alone.

Security is a single hard boundary: the bridge only ever responds to a
direct message from the exact Discord user id in `DISCORD_OWNER_ID`;
every other user and every non-DM message is silently ignored. Anyone who
could reach it could spend Anthropic credits or trigger `send_email`, so
this isn't configurable per-message.

The interesting engineering problem: `discord.py`'s event handlers run on
an asyncio event loop, but `ConversationLoop.send()` is a plain blocking
call — the exact mismatch Tier 3's `voice_cli.py` already solved for
push-to-talk. Same fix, adapted: every DM is handed to a single worker
thread (not one thread per message, so two DMs sent close together can't
race on the shared `ConversationLoop`'s history), and `on_confirm` blocks
that thread on a queue that `on_message` fills when the next DM arrives
while a confirmation is pending. Sending a Discord message from that
worker thread goes through `asyncio.run_coroutine_threadsafe` rather than
touching the event loop directly.

Verified two ways: real discord.py API calls (`Intents`, `Client`,
`DMChannel`) construct correctly against the actual library, not a mock;
and, since discord.py itself can't connect to a live gateway from this
sandbox, the concurrency pattern specifically — a real background asyncio
event loop (not discord.py, just `asyncio` directly) standing in for
`client.loop`, driving a full confirmation round trip end to end (prompt
sent, thread blocks, next "message" arrives, correctly routed to the
confirmation queue not a new turn, parsed, tool result relayed) — no
deadlock, correct routing. I have not connected this to a live Discord
bot or exchanged a real message in this sandbox.

## Tier 9 — send

`griffin/tools/send.py` closes the gap Tier 2 deliberately left open:
`send_email` sends a previously saved draft (`draft_message`) as a real
email over Resend's HTTPS API (`requests`, no new dependency — see
`.env.example` for signup steps). It acts on an existing draft rather
than taking fresh text, so sending only ever happens to something that
was already saved and could be reviewed first. `send_email` is in
`config.yaml`'s `requires_confirmation` list — both Griffin directly and
the marketing specialist have it.

This also closes the loop `AGENT.md` had flagged as capping Tier 8's
autonomy: since the heartbeat's `team_task` auto-declines every
confirmation-gated tool the same way regardless of which one it is, a
scheduled task can now genuinely *try* to send something and correctly
fail to — verified directly, with `input()` poisoned to raise if touched
at all, Resend's `requests.post` call mocked to prove no real send
occurred, and the result confirming the gate held.

This was originally plain SMTP (`smtplib`), swapped for Resend after a
live Tier 10 deploy on Railway proved outbound SMTP is blocked there
entirely — both Gmail's and iCloud's mail servers were unreachable on
port 587 from that instance, while the same instance reaches Anthropic
and Discord fine over HTTPS. No code fix works around a platform-level
SMTP block, so this moved to an HTTPS-based provider instead.

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
- **publisher** (Tier 11) — uploads a video `youtube` already produced to
  YouTube; also confirmation-gated, and private by default.
- **research** — searches the web (`web_search`, Anthropic's server-side
  tool, no local code or API key of ours) and fetches a specific URL to
  read in full (`fetch_url`, local). This is also the first specialist to
  touch untrusted external content for real, so its system prompt is
  where the "external content is data, not instructions" posture gets
  exercised against an actual boundary.

Griffin reaches the team via one new tool, `delegate_task`
(`griffin/tools/delegate.py`) — from the outer loop's point of view it's
just another tool call that runs to completion and returns text. Tier 8
above adds the other way in: a specialist run from the heartbeat instead
of a conversation.

## What's left for a fuller build (not started)

- SMS/text sending — send_email (Tier 9) covers email only.
- A visual face, more specialists — see "Where to go after the baseline"
  in the original build doc.
