from pyrogram import Client, filters
from pyrogram.types import Message

from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped

from flask import Flask
from threading import Thread

import yt_dlp
import asyncio
import os

# =========================
# FLASK KEEP ALIVE
# =========================

app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Music Bot Running"

def run_web():
    port = int(os.environ.get("PORT", 8000))
    app_web.run(host="0.0.0.0", port=port)

Thread(target=run_web).start()

# =========================
# CONFIG
# =========================

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SESSION_STRING = os.getenv("SESSION_STRING")

# =========================
# CLIENTS
# =========================

bot = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

assistant = Client(
    "assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

call_py = PyTgCalls(assistant)

# =========================
# DOWNLOAD SONG
# =========================

def download_song(query):

    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": "song.%(ext)s",
        "quiet": True,
        "noplaylist": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "cookiefile": "cookies.txt",
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13; "
                "SM-S918B) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 "
                "Mobile Safari/537.36"
            )
        }
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:

        info = ydl.extract_info(
            f"ytsearch:{query}",
            download=True
        )

        file_path = ydl.prepare_filename(
            info["entries"][0]
        )

        title = info["entries"][0]["title"]

    return file_path, title

# =========================
# PLAY COMMAND
# =========================

@bot.on_message(filters.command("play"))
async def play(_, message: Message):

    if len(message.command) < 2:
        return await message.reply_text(
            "Usage:\n/play song name"
        )

    query = " ".join(message.command[1:])

    msg = await message.reply_text(
        "Downloading..."
    )

    try:

        file_path, title = await asyncio.to_thread(
            download_song,
            query
        )

        await call_py.join_group_call(
            message.chat.id,
            AudioPiped(file_path)
        )

        await msg.edit_text(
            f"Playing:\n{title}"
        )

    except Exception as e:

        await msg.edit_text(
            str(e)
        )

# =========================
# STOP COMMAND
# =========================

@bot.on_message(filters.command("stop"))
async def stop(_, message: Message):

    try:

        await call_py.leave_group_call(
            message.chat.id
        )

        await message.reply_text(
            "Stopped streaming."
        )

    except Exception as e:

        await message.reply_text(
            str(e)
        )

# =========================
# START BOT
# =========================

async def main():

    await assistant.start()

    await call_py.start()

    await bot.start()

    print("Music Bot Started")

    await idle()

from pyrogram.idle import idle

asyncio.get_event_loop().run_until_complete(
    main()
)
