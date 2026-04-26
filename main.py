#!/usr/bin/env python3
import asyncio
import logging
import os
import signal
import sys

import dotenv
from dotenv import load_dotenv

load_dotenv()

import app as fastapi_app
from services.kick import KickService
from services.twitch import TwitchService
import state as global_state
from state import add_message, leaderboard, trivia, bus, broadcast

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


async def on_chat_message(msg):
    logger.info(f"[{msg.platform}] {msg.username}: {msg.content}")

    # Record in ring buffer
    add_message(platform=msg.platform, username=msg.username, text=msg.content)

    # Award participation points
    leaderboard[msg.username] = leaderboard.get(msg.username, 0) + 1

    # Broadcast to SSE clients
    await broadcast({
        "type": "chat",
        "platform": msg.platform,
        "username": msg.username,
        "content": msg.content,
        "timestamp": msg.timestamp,
    })

    # Trivia check
    if trivia.active:
        result = await trivia.check_answer(msg.username, msg.content)
        if result is True:
            await broadcast({
                "type": "trivia_win",
                "username": msg.username,
                "answer": trivia.answer,
            })


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    kick_service = None
    twitch_service = None

    if os.getenv("KICK_CHANNEL"):
        kick_service = KickService(
            channel_name=os.getenv("KICK_CHANNEL"),
            event_callback=on_chat_message,
        )
        kick_service.start(loop)
        logger.info("[Main] Kick service started")
    else:
        logger.warning("[Main] KICK_CHANNEL not set — skipping Kick")

    if os.getenv("TWITCH_TOKEN") and os.getenv("TWITCH_BOT_USERNAME") and os.getenv("TWITCH_CHANNEL"):
        twitch_service = TwitchService(
            token=os.getenv("TWITCH_TOKEN"),
            nickname=os.getenv("TWITCH_BOT_USERNAME"),
            channel=os.getenv("TWITCH_CHANNEL"),
            event_callback=on_chat_message,
        )
        twitch_service.start(loop)
        logger.info("[Main] Twitch service started")
    else:
        logger.warning("[Main] Twitch credentials not set — skipping Twitch")

    def shutdown(signum, frame):
        logger.info("[Main] Shutdown received")
        if kick_service:
            kick_service.stop()
        if twitch_service:
            twitch_service.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    import uvicorn
    uvicorn.run(
        fastapi_app.app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        loop=loop,
        log_level="info",
    )


if __name__ == "__main__":
    main()
