# Deploying Griffin: Discord bridge on an always-on host

This covers making Griffin reachable from your phone: a Discord bot that
DMs you, running on a small droplet so it's up even when your laptop
isn't. The text (`main.py`) and voice (`voice_main.py`) interfaces still
only make sense on a machine with a keyboard/mic — this deployment is just
for `discord_main.py` and `heartbeat_main.py`, the two pieces designed
from the start to run unattended.

## 1. Create the Discord bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and sign in with the Discord account you use normally.
2. **New Application** → give it a name (e.g. "Griffin") → Create.
3. In the left sidebar, open **Bot**. Click **Reset Token** (or **Copy** if a token's already shown) and save it somewhere safe — this is `DISCORD_BOT_TOKEN`. Treat it like a password; anyone with it can control the bot.
4. On the same Bot page, scroll to **Privileged Gateway Intents** and turn on **Message Content Intent**. Without this, the bot can see that a DM arrived but not read what it says.
5. In the left sidebar, open **OAuth2 → URL Generator**. Under **Scopes** check `bot`. Under **Bot Permissions** check `Send Messages` and `Read Message History` (that's all it needs). Copy the generated URL.
6. Open that URL in a browser and add the bot to **a server you control** — if you don't have one, create a new private Discord server first (takes 10 seconds, and can just be for you). This step is only needed so Discord considers you and the bot "known to each other" enough to allow DMs — Griffin never posts in that server's channels, only in your DMs.
7. Go find the bot in your server's member list and send it a DM to open the conversation from your side (Discord requires the human to start the DM in some cases). You should now be able to message it directly from your DM list going forward.

## 2. Get your Discord user ID

1. In Discord, open **Settings → Advanced** and turn on **Developer Mode**.
2. Right-click your own name/avatar anywhere and choose **Copy User ID**. This numeric ID is `DISCORD_OWNER_ID` — Griffin ignores every message that isn't a DM from this exact ID, so double-check it's yours, not the bot's or a server's.

## 3. Create the droplet

1. Sign up at [DigitalOcean](https://www.digitalocean.com/) if you don't have an account.
2. **Create → Droplets**. Pick:
   - **Image:** Ubuntu (latest LTS)
   - **Plan:** Basic, cheapest shared-CPU option (1GB RAM is plenty)
   - **Authentication:** SSH key (recommended) — if you don't have one, DigitalOcean's droplet-creation page links directly to instructions for generating one
   - Region: whichever is closest to you (mostly affects your own SSH latency, not Griffin's behavior)
3. Create the droplet and note its public IP address.

## 4. Set up the droplet

SSH in and install everything:

```bash
ssh root@YOUR_DROPLET_IP

apt update && apt install -y python3-venv python3-pip git
git clone https://github.com/juliancastro190/SynthPath-Marketing.git griffin
cd griffin
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
nano .env   # fill in ANTHROPIC_API_KEY, DISCORD_BOT_TOKEN, DISCORD_OWNER_ID
```

You don't need `DEEPGRAM_API_KEY` / `ELEVENLABS_API_KEY` on the droplet — those only matter for the local voice interface, not the Discord bridge.

## 5. Run it as a service

A systemd service keeps it running after you disconnect, restarts it if it
crashes, and starts it automatically on reboot. Create two unit files —
one for the bot, one for the heartbeat, since they're deliberately
separate processes:

```bash
cat > /etc/systemd/system/griffin-discord.service <<'EOF'
[Unit]
Description=Griffin Discord bridge
After=network-online.target

[Service]
WorkingDirectory=/root/griffin
ExecStart=/root/griffin/.venv/bin/python discord_main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/griffin-heartbeat.service <<'EOF'
[Unit]
Description=Griffin heartbeat
After=network-online.target

[Service]
WorkingDirectory=/root/griffin
ExecStart=/root/griffin/.venv/bin/python heartbeat_main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now griffin-discord griffin-heartbeat
```

Check they're actually running, and watch the logs:

```bash
systemctl status griffin-discord griffin-heartbeat
journalctl -u griffin-discord -f     # Ctrl+C to stop following
journalctl -u griffin-heartbeat -f
```

## 6. Verify

- DM the bot from your phone: "what's on my task list?" — confirm it replies, and that a message from any *other* Discord account is silently ignored.
- Ask it to do something that requires confirmation ("forget the thing about my dog") and confirm it asks first, waits for your reply, and only acts after you say yes.
- In `config.yaml`, temporarily set `stale_after_minutes: 0` and `alert_threshold: 0` under `heartbeat.checks`, add a task, `git pull && systemctl restart griffin-heartbeat`, and confirm you get an unprompted DM within one `interval_seconds` — that's the heartbeat actually reaching your phone instead of only a terminal you're not watching.

## Notes

- **No inbound ports needed.** Both the Discord bot (gateway websocket) and the heartbeat's Discord push (REST API) are outbound-only connections. The droplet's default firewall (SSH inbound, everything else closed) is already correct — you don't need to open anything.
- **Updating:** `cd /root/griffin && git pull && systemctl restart griffin-discord griffin-heartbeat`.
- **The kill switch still works here exactly as documented in Tier 6** — flip `kill_switch.proactive_paused` to `true` in `config.yaml` on the droplet and the heartbeat picks it up on its next tick, no restart needed. The Discord bot itself is unaffected, so you can still talk to Griffin while the heartbeat is paused.
