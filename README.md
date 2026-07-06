# 🧪 Telegram Mini App Demo

A working **Telegram Mini App** (Web App) demo — a full GUI inside Telegram.

## Architecture

```
Telegram App ←→ Bot (bot.py) ←→ Web App (webapp.html hosted on HTTPS)
                        ↕
                 tg.sendData() sends JSON back
```

## How it works

1. User types `/start` → bot sends a button
2. User taps **"Open Mini App"** → a full-screen web page opens inside Telegram
3. User interacts with the GUI (buttons, forms, color picker)
4. Each action calls `Telegram.WebApp.sendData(JSON)` → data arrives in the chat
5. Bot parses the JSON and replies

## What's in the Web App

| Feature | Description |
|---------|-------------|
| 👤 Telegram Profile | Auto-detects user ID, name, username, language |
| ⚡ Quick Actions | Like, Star, Share, Report — instant feedback |
| 📝 Feedback Form | Name + message, sent back to bot |
| 🎨 Color Picker | Pick a color, bot confirms it |
| 🚀 Main Action | Sends full data + closes the window |
| 🌙 Theme-aware | Automatically matches Telegram's dark/light theme |

## Running it

### 1. Host the Web App (HTTPS required)

**Option A — Quickest (GitHub Pages):**
```bash
# Create a repo, upload webapp.html, enable GitHub Pages
# → https://yourname.github.io/repo/webapp.html
```

**Option B — Local + ngrok (for testing):**
```bash
# Terminal 1: serve locally
cd tg-mini-app-demo
python -m http.server 8080

# Terminal 2: expose with ngrok
ngrok http 8080
# → https://xxxx.ngrok.io/webapp.html
```

### 2. Create the bot on Telegram

Message [@BotFather](https://t.me/BotFather):
```
/newbot → pick name → get token

/setdomain → pick your bot → set to your domain (e.g. yourname.github.io or xxxx.ngrok.io)
```

**Important:** BotFather's `/setdomain` must match the domain hosting `webapp.html`.

### 3. Run the bot

```bash
export MINI_APP_BOT_TOKEN="your:token"
export WEBAPP_URL="https://your-domain.com/webapp.html"
python bot.py
```

### 4. Use it

- Open Telegram → your bot → `/start`
- Tap "Open Mini App" → GUI opens inside Telegram
- Interact → data flows back to the chat

## Files

| File | What |
|------|------|
| `webapp.html` | The Mini App GUI (frontend) — runs inside Telegram |
| `bot.py` | The bot server (backend) — sends button, receives data |
| `README.md` | This file |
