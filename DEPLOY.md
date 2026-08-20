# Deploying Griffin

Two things can run 24/7, independent of your laptop:

- **The heartbeat** (Tier 5/8) — scheduled `team_task` checks like
  `weekly_youtube_draft`, running on their own with nobody watching.
- **The Discord bridge** (Tier 10) — chat with Griffin from Discord
  (phone or desktop) instead of only a local terminal.

The default deploy (`discord_main.py`, what `nixpacks.toml` builds) runs
**both in one process**: the Discord bridge starts the heartbeat in a
background thread itself, so there's one Railway service and one shared
`data/` volume instead of two deployments with diverging state.

**`main.py` is never deployed.** It's an interactive terminal program —
you type a message, it replies — which doesn't translate to a remote
server with nobody logged into it. Once the Discord bridge is running,
Discord is how you talk to Griffin remotely; `main.py` still works
locally too, but it has its own separate local `data/` and conversation
history, not shared with the deployed instance.

## What actually happens once it's deployed

The heartbeat runs its scheduled checks exactly like it does locally, and
you can DM the bot directly the same way you'd type into `main.py`.
Anything either path tries that needs your explicit yes (`forget`,
`send_email`, `youtube_produce`) always asks first — from Discord, that's
a real message ("Griffin wants to: ... Reply yes or no.") and your next
DM is read as the answer; from the heartbeat, since nobody's there, it
automatically declines and reports that in the notice it files instead.

**Security**: the bridge only responds to direct messages from the exact
Discord user id in `DISCORD_OWNER_ID` — everyone else, and every message
outside a DM with you, is silently ignored. That's the whole security
model; anyone who could reach it could spend your Anthropic credits or
trigger `send_email`, so don't share the bot invite link or the token.

## Setup (Railway)

Railway builds straight from your GitHub repo — no server to manage, no
SSH.

1. **Set up the Discord side first** — follow the numbered steps in
   `.env.example` under "Tier 10 — Discord bridge" (create the bot,
   enable Message Content Intent, invite it to a private server, get your
   own Discord user id). You'll end up with a bot token and your user id.
2. **Push this branch to GitHub** if you haven't already (`git push`).
3. Go to [railway.app](https://railway.app) and sign up (GitHub login is
   easiest).
4. **New Project → Deploy from GitHub repo** → pick `SynthPath-Marketing`
   → pick this branch (or `main` once this is merged).
5. **Set environment variables**: service → **Variables** tab → add:
   ```
   ANTHROPIC_API_KEY=your-real-key
   DISCORD_BOT_TOKEN=your-bot-token
   DISCORD_OWNER_ID=your-discord-user-id
   ```
   Optional but recommended (real Reddit sourcing instead of always
   falling back to AI-generated):
   ```
   REDDIT_CLIENT_ID=...
   REDDIT_CLIENT_SECRET=...
   ```
   You do **not** need `ELEVENLABS_API_KEY` or the `SMTP_*` variables for
   the heartbeat's own scheduled tasks — anything that would use them
   (`youtube_produce`, `send_email`) always requires your explicit yes,
   which you *can* now give from Discord if you want that to actually
   work when you approve it live; add them if so, skip them if you're
   fine with the heartbeat only ever declining those unattended (it
   always will regardless — this only affects whether a *live Discord*
   approval of one of those tools can actually complete).
6. **Add a persistent volume** (so scheduling state, drafts, and memory
   survive restarts/redeploys instead of resetting every time): service →
   **Settings** → **Volumes** → **New Volume** → mount path `/app/data`.
7. Railway should already be reading `nixpacks.toml` from this repo to
   build with `requirements-discord.txt` and run `python discord_main.py`.
   If the build logs show it installing from `requirements.txt` instead
   (you'd see `sounddevice`/`pynput`/`deepgram-sdk` in the install log),
   Railway isn't picking up `nixpacks.toml` — check **Settings → Build**
   that the builder is Nixpacks and the root directory is the repo root.
8. **Deploy.** Watch **Deployments → View Logs** — you should see
   `Starting heartbeat in the background...` then
   `Griffin Discord bridge ready — logged in as ...`.
9. DM the bot in Discord. It should reply the same way `main.py` would.

### If you already deployed the heartbeat-only version

You had `heartbeat_main.py` running before this. Nothing to undo — just
add the two `DISCORD_*` variables (step 5 above) and push; Railway
auto-redeploys, picks up the updated `nixpacks.toml`, and switches over to
`discord_main.py` (heartbeat included) on the next build. Same volume,
same data, no migration needed.

### Deploying the heartbeat alone instead (no Discord)

Change `nixpacks.toml`'s two lines to `requirements-heartbeat.txt` and
`heartbeat_main.py` — see the comment already in that file.

## Turning it off

- **Pause the heartbeat's proactive checks without undeploying**: set
  `kill_switch.proactive_paused: true` in `config.yaml`, commit, push —
  the loop keeps running but every check is a no-op until you flip it
  back. The Discord bridge itself keeps working either way.
- **Stop everything**: remove the service from the Railway project (or
  pause the whole project) from the dashboard.

## Cost

Railway bills by actual usage (CPU/RAM/time), not a flat subscription — a
small always-on worker like this is cheap, but check Railway's current
pricing page yourself before leaving it running long-term; I'm not going
to quote a number here that could be stale by the time you read this.
