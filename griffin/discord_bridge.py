"""Tier 10 entry point (discord_main.py): chat with Griffin from Discord —
phone or desktop, not just a local terminal — on top of the exact same
brain as main.py/voice_cli.py. Only what feeds the loop and what happens
to its output changes.

discord.py's event handlers run on an asyncio event loop, but
ConversationLoop.send() is a plain blocking call — the same mismatch
voice_cli.py already solved for push-to-talk. The fix is the same shape:
every incoming DM is handed to a worker thread (a single one here, so two
messages from you in quick succession can never run through the shared
ConversationLoop concurrently and race on its history), and on_confirm
blocks that worker thread on a queue that on_message fills when your next
DM arrives while a confirmation is pending. asyncio.run_coroutine_threadsafe
is what lets that worker thread safely send Discord messages without
touching the event loop directly.

Security boundary: the bridge only ever responds to a direct message from
the exact Discord user id in DISCORD_OWNER_ID. Everything else — other
users, any message in a server channel — is silently ignored. This is the
only thing standing between "just you" and "anyone who finds the bot" for
tools that spend money or send real email, so it's deliberately not
configurable per-message or bypassable.
"""

import asyncio
import queue
import threading

import discord

from griffin.brain.loop import ConversationLoop
from griffin.brain.provider import ProviderError
from griffin.config import ASSISTANT_NAME, DISCORD_BOT_TOKEN, DISCORD_OWNER_ID
from griffin.heartbeat.notices import print_startup_notices
from griffin.heartbeat.runner import HeartbeatRunner
from griffin.project_config import load_config

_YES_WORDS = ("yes", "yeah", "yep", "yup", "sure", "confirm", "affirmative", "go ahead", "do it")
_NO_WORDS = ("no", "nope", "don't", "do not", "cancel", "negative", "stop")

# Discord's hard cap is 2000 characters; a little margin keeps this simple
# rather than trying to split exactly on the limit.
_MAX_MESSAGE_CHARS = 1900


class DiscordBridgeError(Exception):
    """Raised when the bridge can't start. Safe to show directly."""


def _parse_yes_no(text):
    lowered = text.lower()
    if any(word in lowered for word in _NO_WORDS):
        return False
    if any(word in lowered for word in _YES_WORDS):
        return True
    return False  # unclear answer -> safe default: decline, don't guess yes


def _chunks(text):
    text = (text or "").strip() or "(empty)"
    return [text[i : i + _MAX_MESSAGE_CHARS] for i in range(0, len(text), _MAX_MESSAGE_CHARS)]


def run_discord_bridge():
    if not DISCORD_BOT_TOKEN:
        raise DiscordBridgeError("No DISCORD_BOT_TOKEN set. Copy .env.example to .env and add your bot token.")
    if not DISCORD_OWNER_ID:
        raise DiscordBridgeError("No DISCORD_OWNER_ID set. Copy .env.example to .env and add your Discord user id.")
    try:
        owner_id = int(DISCORD_OWNER_ID)
    except ValueError:
        raise DiscordBridgeError("DISCORD_OWNER_ID must be a numeric Discord user id, not a username.")

    print_startup_notices()

    print("Starting heartbeat in the background...")
    threading.Thread(target=HeartbeatRunner().run_forever, daemon=True).start()

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    conversation = ConversationLoop()
    # Deliberately its own config key, not voice's confirmation_timeout_seconds
    # — see the comment on discord_confirmation_timeout_seconds in config.yaml.
    confirmation_timeout = load_config().get("tools", {}).get("discord_confirmation_timeout_seconds", 120)
    awaiting_confirmation = threading.Event()
    confirm_replies = queue.Queue()
    message_queue = queue.Queue()

    def _send(channel, text):
        # Called from the worker thread — schedule the actual send on the
        # bot's own event loop and wait for it, rather than touching
        # discord.py's connection from a thread it doesn't expect.
        for chunk in _chunks(text):
            asyncio.run_coroutine_threadsafe(channel.send(chunk), client.loop).result()

    def make_on_confirm(channel):
        def on_confirm(tool_name, tool_input, description):
            _send(channel, f"{ASSISTANT_NAME} wants to: {description}\nReply yes or no.")
            awaiting_confirmation.set()
            try:
                reply_text = confirm_replies.get(timeout=confirmation_timeout)
            except queue.Empty:
                reply_text = ""
                _send(channel, f"[no answer within {confirmation_timeout}s — treating as declined]")
            finally:
                awaiting_confirmation.clear()
            approved = _parse_yes_no(reply_text)
            _send(channel, "[confirmed]" if approved else "[declined]")
            return approved

        return on_confirm

    def process_message(message):
        channel = message.channel
        reply_chunks = []

        def on_text(chunk):
            reply_chunks.append(chunk)

        def on_tool_call(name, tool_input):
            _send(channel, f"[using tool: {name}({tool_input})]")

        def on_tool_result(name, result_text, is_error):
            tag = "error" if is_error else "result"
            _send(channel, f"[{name} {tag}: {result_text}]")

        try:
            conversation.send(
                message.content,
                on_text=on_text,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
                on_confirm=make_on_confirm(channel),
            )
            _send(channel, "".join(reply_chunks))
        except ProviderError as exc:
            _send(channel, f"[trouble reaching {ASSISTANT_NAME}'s brain: {exc}]")

    def worker():
        # One worker, not one thread per message: keeps every turn
        # strictly sequential against the single shared ConversationLoop,
        # so two DMs sent close together can't race on its history.
        while True:
            process_message(message_queue.get())

    threading.Thread(target=worker, daemon=True).start()

    @client.event
    async def on_ready():
        print(f"{ASSISTANT_NAME} Discord bridge ready — logged in as {client.user}.")

    @client.event
    async def on_message(message):
        if message.author == client.user:
            return
        if not isinstance(message.channel, discord.DMChannel):
            return
        if message.author.id != owner_id:
            return
        if awaiting_confirmation.is_set():
            confirm_replies.put(message.content)
            return
        message_queue.put(message)

    client.run(DISCORD_BOT_TOKEN)
