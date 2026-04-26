# Stream Chat Bot

A multi-platform stream chat bot for **Kick** and **Twitch** with a secure web dashboard.

## Features

- Connect to Kick chat via WebSocket
- Connect to Twitch chat via IRC (twitchio)
- Real-time web dashboard with SSE push updates
- Password-protected admin panel
- Trivia game system with leaderboard
- Points system per user

## Setup

### 1. Clone & Install Dependencies

```bash
git clone <repo-url> stream-chat-bot
cd stream-chat-bot
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Twitch OAuth (get from https://twitchapps.com/tmi)
TWITCH_TOKEN=oauth:your_twitch_oauth_token
TWITCH_BOT_USERNAME=your_bot_username
TWITCH_CHANNEL=target_channel

# Kick
KICK_CHANNEL=channel_name

# Admin Dashboard
ADMIN_PASSWORD=your_secure_password

# Optional
HOST=0.0.0.0
PORT=8000
```

### 3. Run Locally

```bash
python main.py
# or with uvicorn directly:
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000` in your browser.

- **Dashboard**: `http://localhost:8000/`
- **Admin**: `http://localhost:8000/admin` (password: value of `ADMIN_PASSWORD`)

## Deployment (Docker)

```bash
docker build -t stream-chat-bot .
docker run -d --env-file .env -p 8000:8000 stream-chat-bot
```

Or with Docker Compose:

```bash
docker compose up -d
```

## Project Structure

```
stream-chat-bot/
├── main.py            # Entry point; starts bot + FastAPI
├── app.py             # FastAPI routes + SSE + HTML serving
├── services/
│   ├── kick.py        # Kick WebSocket connector
│   └── twitch.py      # Twitch IRC connector via twitchio
├── templates/
│   └── dashboard.html # Single-page dashboard (SPA)
├── static/
│   └── css/style.css
├── .env.example       # Template for .env
├── requirements.txt
├── Dockerfile
└── README.md
```

## Architecture

- **Kick** connects via the official `wss://ws-us2.pusher.com` WebSocket endpoint, authenticates with `App\\Events\\ChatMessageEvent` subscription, and streams chat in real-time.
- **Twitch** connects via IRC using `twitchio` (handles OAuth, join, PRIVMSG automatically).
- Both services emit messages to a shared in-memory event bus, consumed by SSE endpoints.
- The dashboard is a vanilla HTML/JS single-page app polling SSE for live updates.
