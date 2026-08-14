"""A Discord DM bridge on top of the exact same brain and tools as the
text/voice CLIs. Nothing about ConversationLoop changes here — only how a
turn arrives (a DM instead of typed/spoken input) and where its reply goes
(back as a DM). This is what makes Griffin reachable from a phone.

Restricted to a single owner (DISCORD_OWNER_ID) and DMs only — matches
AGENT.md's "just the owner" scope. Every other message (other users,
server/guild channels, the bot's own messages) is silently ignored.

ConversationLoop.send() is synchronous; discord.py's event loop is async.
Each incoming message runs its turn in a worker thread (asyncio.to_thread)
so the bot keeps servicing the gateway connection while a turn is in
progress. The confirmation gate reuses the same shape as voice mode:
on_confirm blocks its worker thread on a plain queue.Queue waiting for the
owner's next DM, routed there instead of starting a new turn, with the
same configurable timeout — "never block forever waiting on a human."
"""

import asyncio
import queue
import threading

import discord

from griffin.brain.loop import ConversationLoop
from griffin.brain.provider import ProviderError
from griffin.confirm import parse_yes_no
from griffin.config import ASSISTANT_NAME, DISCORD_BOT_TOKEN, DISCORD_OWNER_ID
from griffin.heartbeat import notices
from griffin.project_config import load_config

# Discord's hard per-message content limit is 2000 chars; leave headroom
# for the "_using tool..._" / "**...**" formatting wrapped around replies.
_CHUNK_LIMIT = 1900


def _chunk_text(text):
    """Split text into Discord-sized pieces, preferring to break on a
    blank line, then a newline, then a space, rather than mid-word."""
    if len(text) <= _CHUNK_LIMIT:
        return [text]
    chunks = []
    remaining = text
    while len(remaining) > _CHUNK_LIMIT:
        split_at = remaining.rfind("\n\n", 0, _CHUNK_LIMIT)
        if split_at == -1:
            split_at = remaining.rfind("\n", 0, _CHUNK_LIMIT)
        if split_at == -1:
            split_at = remaining.rfind(" ", 0, _CHUNK_LIMIT)
        if split_at <= 0:
            split_at = _CHUNK_LIMIT
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


class GriffinDiscordClient(discord.Client):
    def __init__(self, owner_id):
        intents = discord.Intents.default()
        intents.message_content = True  # privileged — must be enabled in the Developer Portal too
        super().__init__(intents=intents)
        self.owner_id = owner_id
        self.conversation = ConversationLoop()
        self.confirmation_timeout = load_config().get("tools", {}).get("confirmation_timeout_seconds", 30)
        self._awaiting_confirmation = threading.Event()
        self._confirm_replies = queue.Queue()

    async def on_ready(self):
        print(f"{ASSISTANT_NAME} is online as {self.user}. DM it from the owner account to talk.")
        await self._deliver_pending_notices()

    async def _deliver_pending_notices(self):
        pending = notices.undismissed()
        if not pending:
            return
        try:
            owner = await self.fetch_user(self.owner_id)
        except discord.DiscordException:
            return
        lines = "\n".join(f"- [{n['id']}] {n['message']}" for n in pending)
        for chunk in _chunk_text(f"**While you were away:**\n{lines}"):
            await owner.send(chunk)
        notices.mark_delivered([n["id"] for n in pending])

    async def on_message(self, message):
        if message.author.id == self.user.id:
            return
        if not isinstance(message.channel, discord.DMChannel):
            return
        if message.author.id != self.owner_id:
            return

        text = message.content.strip()
        if not text:
            return

        if self._awaiting_confirmation.is_set():
            self._confirm_replies.put(text)
            return

        async with message.channel.typing():
            await asyncio.to_thread(self._handle_turn, message.channel, text)

    def _run_coro(self, coro):
        """Schedule a coroutine on the bot's event loop from a worker
        thread and block until it completes."""
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    def _on_confirm(self, tool_name, tool_input, description, channel):
        self._run_coro(channel.send(f"**{ASSISTANT_NAME} wants to:** {description}\nReply yes or no."))
        self._awaiting_confirmation.set()
        try:
            reply_text = self._confirm_replies.get(timeout=self.confirmation_timeout)
        except queue.Empty:
            reply_text = ""
            self._run_coro(
                channel.send(f"_No answer within {self.confirmation_timeout}s — treating as declined._")
            )
        finally:
            self._awaiting_confirmation.clear()
        approved = parse_yes_no(reply_text)
        self._run_coro(channel.send("_Confirmed._" if approved else "_Declined._"))
        return approved

    def _handle_turn(self, channel, text):
        def on_tool_call(name, tool_input):
            self._run_coro(channel.send(f"_using {name}..._"))

        def on_tool_result(name, result_text, is_error):
            tag = "error" if is_error else "result"
            for chunk in _chunk_text(f"_{name} {tag}:_ {result_text}"):
                self._run_coro(channel.send(chunk))

        reply_chunks = []
        try:
            self.conversation.send(
                text,
                on_text=reply_chunks.append,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
                on_confirm=lambda name, tool_input, description: self._on_confirm(
                    name, tool_input, description, channel
                ),
            )
        except ProviderError as exc:
            self._run_coro(channel.send(f"_trouble reaching {ASSISTANT_NAME}'s brain: {exc}_"))
            return

        reply = "".join(reply_chunks).strip()
        if not reply:
            return
        for chunk in _chunk_text(reply):
            self._run_coro(channel.send(chunk))


def run_bot():
    if not DISCORD_BOT_TOKEN:
        print("[can't start: no DISCORD_BOT_TOKEN set. Add it to .env.]")
        return
    if not DISCORD_OWNER_ID:
        print("[can't start: no DISCORD_OWNER_ID set. Add it to .env.]")
        return
    try:
        owner_id = int(DISCORD_OWNER_ID)
    except ValueError:
        print("[can't start: DISCORD_OWNER_ID must be a numeric Discord user ID.]")
        return

    client = GriffinDiscordClient(owner_id)
    client.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    run_bot()
