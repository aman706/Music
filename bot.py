from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream.quality import HighQualityAudio
from pytgcalls.types.input_stream import InputAudioStream
import yt_dlp
import asyncio
import os

# =========================
# CONFIG
# =========================

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SESSION_STRING = os.getenv("SESSION_STRING")

# =========================
# PYROGRAM CLIENTS
# =========================

bot = Client(
    "MusicBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

assistant = Client(
    "Assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# =========================
# PYTGCALLS
# =========================

call_py = PyTgCalls(assistant)

# =========================
# DOWNLOAD FUNCTION
# =========================

def download_song(query):
    ydl_opts = {
        "format": "bestaudio",
        "outtmpl": "song.%(ext)s",
        "quiet": True,
        "noplaylist": True
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

        vc = message.chat.id

        await call_py.join_group_call(
            vc,
            AudioPiped(file_path)
        )

        await msg.edit_text(
            f"Playing:\n{title}"
        )

    except Exception as e:
        await msg.edit_text(
            f"Error:\n{e}"
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
