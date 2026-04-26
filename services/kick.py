"""
Kick WebSocket bot — connects to wss://ws-us2.pusher.com, subscribes to
App\\Events\\ChatMessageEvent, parses messages, and publishes to the EventBus.
"""

import asyncio
import json
import logging
import random

import websockets
from websockets.client import connect

log = logging.getLogger("kick")


class KickBot:
    PUSHER_HOST = "ws-us2.pusher.com"
    PUSHER_PORT = 443

    def __init__(self, channel: str, chatroom_id: int | str | None, bus, *,
                 host: str = PUSHER_HOST, port: int = PUSHER_PORT):
        self.channel = channel
        self.chatroom_id = chatroom_id or channel
        self.bus = bus
        self.host = host
        self.port = port
        self._running = False
        self._ws = None

    async def run(self):
        self._running = True
        while self._running:
            try:
                await self._connect()
            except Exception as e:
                log.warning("Kick WebSocket disconnected: %s. Reconnecting in 5s…", e)
                await asyncio.sleep(5)

    async def _connect(self):
        import os
        from app import add_message

        uri = f"wss://{self.host}:{self.port}/app/{self.chatroom_id}"
        log.info("Connecting to Kick WebSocket: %s", uri)

        async with connect(uri, ping_interval=None) as ws:
            self._ws = ws
            # Subscribe to chat events
            subscribe_payload = {
                "event": "pusher:subscribe",
                "data": {
                    "auth": "",
                    "channel": f"private-app.{self.chatroom_id}",
                },
            }
            await ws.send(json.dumps(subscribe_payload))

            async for raw in ws:
                if not self._running:
                    break
                await self._handle_message(raw, add_message)

    async def _handle_message(self, raw: str, add_message):
        try:
            msg = json.loads(raw)
        except Exception:
            return

        event = msg.get("event", "")
        data = msg.get("data", {})

        if event == "App\\Events\\ChatMessageEvent":
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:
                    pass

            sender = data.get("sender", {})
            username = sender.get("username", "unknown")
            content = data.get("content", "")
            message_id = data.get("id", "")

            entry = add_message("kick", username, content, data)
            await self.bus.publish({**entry, "type": "chat_message"})

        elif event == "pusher:pong":
            pass  # keepalive response, ignore

    async def close(self):
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
