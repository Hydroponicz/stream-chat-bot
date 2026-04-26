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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


async def on_chat_message(msg):
    """Shared handler for messages from both platforms."""
    logger.info(f"[{msg.platform}] {msg.username}: {msg.content}")
    fastapi_app.record_message(msg)
    await fastapi_app.broadcast(
        {
            "type": "chat",
            "platform": msg.platform,
            "username": msg.username,
            "content": msg.content,
            "timestamp": msg.timestamp,
        }
    )

    # Trivia logic
    if fastapi_app.state["trivia"]["active"]:
        if (
            fastapi_app.state["trivia"]["answer"]
            and msg.content.lower().strip() == fastapi_app.state["trivia"]["answer"]
        ):
            current = fastapi_app.state["leaderboard"].get(msg.username, 0)
            fastapi_app.state["leaderboard"][msg.username] = current + 10
            fastapi_app.state["trivia"]["active"] = False
            await fastapi_app.broadcast(
                {
                    "type": "trivia_win",
                    "username": msg.username,
                    "answer": fastapi_app.state["trivia"]["answer"],
                }
            )


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Initialize services
    kick_service = None
    twitch_service = None

    if os.getenv("KICK_CHANNEL"):
        kick_service = KickService(
            channel_name=os.getenv("KICK_CHANNEL"),
            event_callback=on_chat_message,
        )
        fastapi_app.state["connected"]["kick"] = True
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
        fastapi_app.state["connected"]["twitch"] = True
        twitch_service.start(loop)
        logger.info("[Main] Twitch service started")
    else:
        logger.warning("[Main] Twitch credentials not set — skipping Twitch")

    # Graceful shutdown
    def shutdown(signum, frame):
        logger.info("[Main] Shutdown signal received")
        if kick_service:
            kick_service.stop()
        if twitch_service:
            twitch_service.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Import uvicorn here so it doesn't conflict with the signal handlers above
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
