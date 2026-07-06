#!/usr/bin/env python3
"""
Telegram Mini App Demo — Bot side.
Sends a Web App button, receives data from the embedded GUI.
"""

import os, sys, json, logging
from http.server import HTTPServer, SimpleHTTPRequestHandler
from threading import Thread

from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("MINI_APP_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://your-domain.com/webapp.html")

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

# ── Handlers ────────────────────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Send a button that opens the Mini App."""
    user = update.effective_user
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "🚀 Open Mini App",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )
    ]])

    await update.message.reply_text(
        f"👋 Hey {user.first_name}!\n\n"
        f"Tap the button below to open the **Mini App** 🧪\n"
        f"It's a full GUI window inside Telegram.",
        reply_markup=keyboard,
    )


async def webapp_data(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Receive data sent from the Mini App via tg.sendData()."""
    payload = update.effective_message.web_app_data
    if not payload:
        return

    raw = payload.data
    user = update.effective_user

    log.info(f"WebApp data from {user.id}: {raw}")

    try:
        data = json.loads(raw)
        dtype = data.get("type", "unknown")

        if dtype == "action":
            action = data.get("action", "?")
            await update.effective_message.reply_text(
                f"⚡ Got action: **{action}**\n\n"
                f"From: {user.first_name}"
            )

        elif dtype == "feedback":
            name = data.get("name", "Anonymous")
            feedback = data.get("feedback", "")
            await update.effective_message.reply_text(
                f"📝 **Feedback from {name}**\n\n"
                f"_{feedback}_\n\n"
                f"✅ Submitted! Thanks {name}! 🙏"
            )

        elif dtype == "color":
            color = data.get("color", "#000")
            await update.effective_message.reply_text(
                f"🎨 Picked color: `{color}`\n\n"
                f"Nice choice! (This could update a theme, profile bg, etc.)"
            )

        elif dtype == "complete":
            ts = data.get("timestamp", "unknown")
            await update.effective_message.reply_text(
                f"✅ **Mini App session complete!**\n\n"
                f"👤 {user.first_name}\n"
                f"🕐 {ts}\n\n"
                f"Data received successfully. Window was closed on their end."
            )

        else:
            await update.effective_message.reply_text(
                f"📦 Received data: `{raw[:200]}`"
            )

    except json.JSONDecodeError:
        await update.effective_message.reply_text(f"📦 Raw data: `{raw[:300]}`")


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "**Commands:**\n"
        "/start — Open the Mini App 🧪\n"
        "/help — This message\n\n"
        "Tap the button → GUI opens in Telegram → interact → data comes back here."
    )


# ── Local dev server (for testing the webapp) ───────────────────────────────

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress HTTP log spam

def start_dev_server(directory, port=8080):
    """Serve the webapp.html locally (HTTP only — use ngrok for HTTPS)."""
    os.chdir(directory)
    server = HTTPServer(("0.0.0.0", port), QuietHandler)
    log.info(f"🌐 Dev server on http://localhost:{port}")
    log.info(f"   Expose with: ngrok http {port}")
    log.info(f"   Then set WEBAPP_URL=https://xxxx.ngrok.io/webapp.html")
    server.serve_forever()


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    if TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Set MINI_APP_BOT_TOKEN env var")
        sys.exit(1)

    print("🤖 Mini App Demo Bot starting...")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_data))

    print(f"✅ WebApp URL: {WEBAPP_URL}")
    print("   Bot running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
