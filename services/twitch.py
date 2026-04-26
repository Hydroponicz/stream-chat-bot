"""
Twitch IRC bot via twitchio — connects with OAuth, joins IRC channel,
and publishes chat messages to the shared EventBus.
"""

import asyncio
import logging

import twitchio

log = logging.getLogger("twitch")

from state import bus, add_message, trivia


class TwitchBot(twitchio.Client):
    def __init__(self, token: str, username: str, channel: str, bus):
        self._bus = bus
        super().__init__(token=token, initial_channels=[f"#{channel}"])

    async def event_ready(self):
        log.info("Twitch bot connected as %s", self._nick)

    async def event_message(self, message: twitchio.Message):
        if message.echo:
            return
        username = message.author.name if message.author else "unknown"
        text = message.content

        entry = add_message("twitch", username, text)
        await self._bus.publish({**entry, "type": "chat_message"})

        # Check trivia answers
        if trivia.active:
            result = await trivia.check_answer(username, text)
            if result is True:
                await self._bus.publish({
                    "type": "trivia_correct",
                    "username": username,
                    "question": trivia.question,
                })


def create_twitch_bot(token: str, username: str, channel: str, bus) -> TwitchBot:
    return TwitchBot(token=token, username=username, channel=channel, bus=bus)
