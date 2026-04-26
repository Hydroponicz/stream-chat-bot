#!/usr/bin/env python3
import asyncio
import logging
import os
import signal
import sys

from dotenv import load_dotenv

load_dotenv()

import app as fastapi_app
import state as global_state
from state import add_message, leaderboard, trivia, bus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


async def on_chat_message(msg):
    logger.info(f"[{msg.platform}] {msg.username}: {msg.content}")
    add_message(platform=msg.platform, username=msg.username, text=msg.content)
    leaderboard[msg.username] = leaderboard.get(msg.username, 0) + 1
    await bus.publish({
        "type": "chat",
        "platform": msg.platform,
        "username": msg.username,
        "content": msg.content,
        "timestamp": msg.timestamp,
    })
    if trivia.active:
        result = await trivia.check_answer(msg.username, msg.content)
        if result is True:
            await bus.publish({"type": "trivia_win", "username": msg.username, "answer": trivia.answer})


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    kick_service = None

    if os.getenv("KICK_CHANNEL"):
        from services.kick import KickBot
        kick_service = KickBot(
            channel=os.getenv("KICK_CHANNEL"),
            chatroom_id=os.getenv("KICK_CHATROOM_ID"),
            bus=bus,
        )
        loop.create_task(kick_service.run())
        logger.info("[Main] Kick service started")

    def shutdown(signum, frame):
        logger.info("[Main] Shutdown received")
        if kick_service:
            loop.create_task(kick_service.close())
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    import uvicorn
    uvicorn.run(
        fastapi_app.app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8080)),
        log_level="info",
    )


if __name__ == "__main__":
    main()
