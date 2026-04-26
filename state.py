"""
Shared in-memory state — event bus, message ring buffer, leaderboard, trivia.
Imported by app.py, main.py, services/kick.py, services/twitch.py
to avoid circular imports.
"""

import asyncio
import json
from collections import defaultdict
from datetime import datetime
from typing import Any


# ── Event Bus ────────────────────────────────────────────────────────────────

class EventBus:
    def __init__(self):
        self._subs: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._subs.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subs:
            self._subs.remove(q)

    async def publish(self, msg: dict):
        for sub in self._subs[:]:
            try:
                sub.put_nowait(msg)
            except Exception:
                self._subs.remove(sub)

    @property
    def subscriber_count(self) -> int:
        return len(self._subs)


bus = EventBus()


# ── Message Buffer ───────────────────────────────────────────────────────────

_messages: list[dict] = []
_MESSAGE_LIMIT = 200


def add_message(platform: str, username: str, text: str, raw: dict | None = None) -> dict:
    entry = {
        "id": len(_messages),
        "platform": platform,
        "username": username,
        "text": text,
        "timestamp": datetime.utcnow().isoformat(),
    }
    _messages.append(entry)
    if len(_messages) > _MESSAGE_LIMIT:
        _messages.pop(0)
    return entry


def get_recent_messages(n: int = 50) -> list[dict]:
    return _messages[-n:]


# ── Leaderboard ──────────────────────────────────────────────────────────────

leaderboard: dict[str, int] = defaultdict(int)


def get_leaderboard() -> list[tuple[str, int]]:
    return sorted(leaderboard.items(), key=lambda x: -x[1])


def award_points(username: str, pts: int):
    leaderboard[username] += pts


def reset_leaderboard():
    leaderboard.clear()


# ── Trivia ────────────────────────────────────────────────────────────────────

class TriviaManager:
    def __init__(self):
        self.active: bool = False
        self.question: str = ""
        self.answer: str = ""
        self.hint: str = ""
        self.participants: set[str] = set()
        self._lock = asyncio.Lock()

    async def start_trivia(self, question: str, answer: str, hint: str = ""):
        async with self._lock:
            self.active = True
            self.question = question
            self.answer = answer.lower().strip()
            self.hint = hint
            self.participants.clear()
        await bus.publish({"type": "trivia_start", "question": question, "hint": hint})

    async def stop_trivia(self):
        async with self._lock:
            self.active = False
        await bus.publish({"type": "trivia_stop"})

    async def check_answer(self, username: str, text: str) -> bool | None:
        async with self._lock:
            if not self.active:
                return None
            if username in self.participants:
                return False
            if text.lower().strip() == self.answer:
                self.participants.add(username)
                leaderboard[username] += 100
                return True
            self.participants.add(username)
            return False

    def get_state(self) -> dict:
        return {
            "active": self.active,
            "question": self.question if self.active else "",
            "hint": self.hint if self.active else "",
            "answered_count": len(self.participants),
        }


trivia = TriviaManager()
