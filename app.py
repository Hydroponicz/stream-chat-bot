import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette import EventSourceResponse
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

import state as global_state
from state import bus, add_message, leaderboard, trivia, get_leaderboard

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "change-me-in-prod"))

# --- Mounts ---
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- SSE broadcast ---
sse_connections: list[asyncio.Queue] = []


async def sse_event_generator():
    queue: asyncio.Queue = asyncio.Queue()
    sse_connections.append(queue)
    try:
        while True:
            data = await queue.get()
            yield {"event": "update", "data": json.dumps(data)}
    finally:
        sse_connections.remove(queue)


async def broadcast(data: dict):
    for q in sse_connections[:]:
        try:
            q.put_nowait(data)
        except Exception:
            sse_connections.remove(q)


# --- Routes ---
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/admin")
async def admin_page(request: Request):
    if request.session.get("admin_authenticated") != os.getenv("ADMIN_PASSWORD"):
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("dashboard.html", {"request": request, "admin": True})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login_submit(request: Request):
    form = await request.form()
    entered = form.get("password", "")
    if entered == os.getenv("ADMIN_PASSWORD"):
        request.session["admin_authenticated"] = entered
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid password"})


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)


# --- SSE stream ---
@app.get("/events")
async def events(request: Request):
    return EventSourceResponse(sse_event_generator())


# --- REST control (admin only) ---
def require_admin(request: Request):
    if request.session.get("admin_authenticated") != os.getenv("ADMIN_PASSWORD"):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/admin/trivia/start")
async def trivia_start(request: Request, question: str = "", answer: str = ""):
    require_admin(request)
    hint = f"The answer starts with '{answer[0].upper()}'" if answer else ""
    await trivia.start_trivia(question=question, answer=answer, hint=hint)
    return {"status": "ok", "question": question}


@app.post("/admin/trivia/stop")
async def trivia_stop(request: Request):
    require_admin(request)
    await trivia.stop_trivia()
    return {"status": "ok"}


@app.post("/admin/reset")
async def reset_game(request: Request):
    require_admin(request)
    global_state._messages.clear()
    leaderboard.clear()
    trivia.active = False
    trivia.question = ""
    trivia.answer = ""
    trivia.participants.clear()
    await broadcast({"type": "reset"})
    return {"status": "ok"}


@app.post("/admin/points")
async def give_points(request: Request, username: str = "", points: int = 0):
    require_admin(request)
    if not username:
        raise HTTPException(status_code=400, detail="username required")
    leaderboard[username] = leaderboard.get(username, 0) + points
    await broadcast({"type": "points_update", "username": username, "points": leaderboard[username]})
    return {"status": "ok", "username": username, "points": leaderboard[username]}


@app.get("/admin/state")
async def get_state(request: Request):
    require_admin(request)
    return {
        "messages": global_state._messages[-50:],
        "leaderboard": dict(get_leaderboard()),
        "trivia": trivia.get_state(),
        "connected": {"kick": False, "twitch": False},
    }
