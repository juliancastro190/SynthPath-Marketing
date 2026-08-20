# Deploying the heartbeat

This deploys **only the heartbeat** (`heartbeat_main.py` — Tier 5/8's
background loop that runs scheduled `team_task` checks like
`weekly_youtube_draft`) to run 24/7, independent of your laptop.

**It does not deploy `main.py`.** `main.py` is an interactive terminal
program — you type a message, it replies — and that doesn't translate to
a remote server with nobody logged into it. You'll keep talking to
Griffin locally, the same way as now; the heartbeat just keeps doing its
scheduled work in the background even when your laptop is off or asleep.

(`.env.example` mentions a Discord bridge for exactly this — chatting
with Griffin from anywhere, not just a local terminal — but that bridge
was never actually built; only the placeholder env vars exist. This
deploy doesn't need it. If you want that later, it's a separate project.)

## What actually happens when it's deployed

Every check in `config.yaml`'s `heartbeat.checks` list that's
`enabled: true` runs on its own schedule, exactly like it does locally.
Anything a scheduled task tries that needs your explicit yes (`forget`,
`send_email`, `youtube_produce`) automatically gets declined — there's
nobody there to ask — and that gets reported in the notice it files
instead. You'll see those notices next time you open `main.py` locally
("While you were away"), same as always.

## Setup (Railway)

Railway builds straight from your GitHub repo with no server to manage by
hand — you don't SSH into anything.

1. **Push this branch to GitHub** if you haven't already (`git push`).
2. Go to [railway.app](https://railway.app) and sign up (GitHub login is
   easiest — it can read your repos directly).
3. **New Project → Deploy from GitHub repo** → pick `SynthPath-Marketing`
   → pick this branch (`claude/ai-assistant-team-system-el41fa`, or
   `main` once this is merged).
4. Railway will try to build immediately — let it fail once if it does;
   the next two steps fix it.
5. **Set environment variables**: open the service → **Variables** tab →
   add, at minimum:
   ```
   ANTHROPIC_API_KEY=your-real-key
   ```
   Optional but recommended (real Reddit sourcing instead of always
   falling back to AI-generated — see the earlier Reddit OAuth setup):
   ```
   REDDIT_CLIENT_ID=...
   REDDIT_CLIENT_SECRET=...
   ```
   You do **not** need `ELEVENLABS_API_KEY` or the `SMTP_*` variables here
   — anything that would use them (`youtube_produce`, `send_email`)
   always gets auto-declined unattended anyway, so they'd never fire.
6. **Add a persistent volume** (so scheduling state and notices survive
   restarts/redeploys instead of resetting every time): service →
   **Settings** → **Volumes** → **New Volume** → mount path `/app/data`.
   Without this, `data/heartbeat_state.json` resets on every redeploy and
   every check looks newly-due again.
7. Railway should already be reading `nixpacks.toml` from this repo (it's
   committed at the root) to build with `requirements-heartbeat.txt`
   (deliberately excludes the voice packages — they need real audio
   hardware this container doesn't have, and aren't needed for the
   heartbeat at all) and run `python heartbeat_main.py`. If the build logs
   show it installing from `requirements.txt` instead (you'd see
   `sounddevice`/`pynput`/`deepgram-sdk` in the install log), Railway
   isn't picking up `nixpacks.toml` — check **Settings → Build** that the
   builder is set to Nixpacks and the root directory is the repo root,
   not a subfolder.
8. **Deploy.** Watch the **Deployments → View Logs** tab — you should see
   `Heartbeat running. Ctrl+C to stop.` and then, on schedule, the same
   live `[specialist using tool: ...]` output you've already seen
   locally.

## Turning it off

- **Pause without undeploying**: set `kill_switch.proactive_paused: true`
  in `config.yaml`, commit, push — Railway auto-redeploys, and the loop
  keeps running but every check is a no-op until you flip it back.
- **Stop it entirely**: remove the service from the Railway project (or
  pause the whole project) from the dashboard.

## Cost

Railway bills by actual usage (CPU/RAM/time), not a flat subscription — a
small always-on worker like this is cheap, but check Railway's current
pricing page yourself before leaving it running long-term; I'm not going
to quote a number here that could be stale by the time you read this.
