"""
Stream Chat Bot — FastAPI web dashboard, SSE push, and admin API.
Serves the single-page dashboard and exposes REST + SSE endpoints.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sse_starlette.sse import EventSourceResponse as EventStreamResponse

load_dotenv()
app = FastAPI()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

TEMPLATES = Path(__file__).parent / "templates"
STATIC = Path(__file__).parent / "static"

from state import (
    bus, trivia, add_message, get_recent_messages,
    get_leaderboard, award_points, reset_leaderboard, leaderboard,
)

security = HTTPBasic()


def verify_admin(credentials: HTTPBasicCredentials):
    if credentials.username != "admin" or credentials.password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=401,
            detail="Incorrect credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


# ── SSE Endpoint ────────────────────────────────────────────────────────────

@app.get("/events")
async def events():
    async def gen():
        q = bus.subscribe()
        try:
            while True:
                msg = await q.get()
                yield {"event": msg.get("type", "message"), "data": json.dumps(msg)}
        except Exception:
            bus.unsubscribe(q)

    return EventStreamResponse(gen(), media_type="text/event-stream")


# ── Page Routes ─────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse(str(TEMPLATES / "dashboard.html"))


@app.get("/admin")
async def admin_page():
    return FileResponse(str(TEMPLATES / "dashboard.html"))


# ── REST API ────────────────────────────────────────────────────────────────

@app.get("/api/messages")
async def get_messages(n: int = 50):
    return JSONResponse(get_recent_messages(n))


@app.get("/api/leaderboard")
async def get_leaderboard_api():
    return JSONResponse(get_leaderboard())


@app.get("/api/trivia")
async def get_trivia():
    return JSONResponse(trivia.get_state())


@app.post("/api/trivia/start")
async def start_trivia_api(
    request: Request,
    credentials: HTTPBasicCredentials = security,
):
    verify_admin(credentials)
    body = await request.json()
    await trivia.start_trivia(
        question=body.get("question", "?"),
        answer=body.get("answer", "?"),
        hint=body.get("hint", ""),
    )
    return JSONResponse({"ok": True})


@app.post("/api/trivia/stop")
async def stop_trivia_api(credentials: HTTPBasicCredentials = security):
    verify_admin(credentials)
    await trivia.stop_trivia()
    return JSONResponse({"ok": True})


@app.post("/api/points")
async def points_api(
    request: Request,
    credentials: HTTPBasicCredentials = security,
):
    verify_admin(credentials)
    body = await request.json()
    user = body.get("username", "")
    pts = int(body.get("points", 0))
    if not user:
        return JSONResponse({"error": "username required"}, status_code=400)
    award_points(user, pts)
    return JSONResponse({"ok": True, "username": user, "points": leaderboard[user]})


@app.post("/api/leaderboard/reset")
async def reset_leaderboard_api(credentials: HTTPBasicCredentials = security):
    verify_admin(credentials)
    reset_leaderboard()
    return JSONResponse({"ok": True})


@app.get("/api/status")
async def status_api():
    return JSONResponse({
        "connected": True,
        "kick_channel": os.getenv("KICK_CHANNEL", ""),
        "twitch_channel": os.getenv("TWITCH_CHANNEL", ""),
    })


@app.get("/static/{path:path}")
async def static_files(path: str):
    file_path = STATIC / path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(file_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host=HOST, port=PORT, reload=False)
