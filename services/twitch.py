"""
Twitch IRC bot via twitchio — connects with OAuth, joins IRC channel,
and publishes chat messages to the shared EventBus.
"""

import asyncio
import logging

import twitchio
from twitchio import Client, eventsub
from twitchio.ext import commands

log = logging.getLogger("twitch")


class TwitchBot(twitchio.Client):
    def __init__(self, token: str, username: str, channel: str, bus):
        self._bus = bus
        self._username = username
        self._channel = channel
        super().__init__(token=token, initial_channels=[f"#{channel}"])

    async def event_ready(self):
        log.info("Twitch bot connected as %s", self._username)

    async def event_message(self, message: twitchio.Message):
        if message.echo:
            return
        username = message.author.name if message.author else "unknown"
        text = message.content

        from app import add_message
        entry = add_message("twitch", username, text)
        await self._bus.publish({**entry, "type": "chat_message"})

        from app import trivia
        if trivia.active:
            result = await trivia.check_answer(username, text)
            if result is True:
                await self._bus.publish({
                    "type": "trivia_correct",
                    "username": username,
                    "question": trivia.question,
                })

    async def event_raw_data(self, data: str):
        """Log raw IRC lines for debugging."""
        log.debug("IRC <<< %s", data.strip())

    async def run(self):
        self.loop = asyncio.get_event_loop()
        try:
            await self.start()
        except Exception as e:
            log.warning("Twitch bot error: %s", e)


def create_twitch_bot(token: str, username: str, channel: str, bus) -> TwitchBot:
    return TwitchBot(token=token, username=username, channel=channel, bus=bus)
