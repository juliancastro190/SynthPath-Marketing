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
- [ ] Tier 5 — Heartbeat: proactive background loop
- [ ] Tier 6 — Rails: confirmation gate, config, audit log, kill switch
