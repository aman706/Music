from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from pytgcalls import PyTgCalls, idle
from pytgcalls.types import MediaStream
from pytgcalls.types.stream import StreamEnded
from pytgcalls.exceptions import NoActiveGroupCall

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

Thread(target=run_web, daemon=True).start()

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
# QUEUE & STATE
# =========================

queues = {}
active_calls = set()

def get_queue(chat_id):
    return queues.get(chat_id, [])

def add_to_queue(chat_id, item):
    if chat_id not in queues:
        queues[chat_id] = []
    queues[chat_id].append(item)

def pop_queue(chat_id):
    if chat_id in queues and queues[chat_id]:
        return queues[chat_id].pop(0)
    return None

def clear_queue(chat_id):
    queues[chat_id] = []

def is_active(chat_id):
    return chat_id in active_calls

async def force_leave(chat_id):
    active_calls.discard(chat_id)
    try:
        await call_py.leave_group_call(chat_id)
    except Exception:
        pass

# =========================
# DOWNLOAD AUDIO
# =========================

def download_song(query):
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "/tmp/%(id)s.%(ext)s",
        "quiet": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "cookiefile": "cookies.txt",
        "extractor_args": {
            "youtube": {"player_client": ["tv"]}
        },
        "js_runtimes": {"node": {}},
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch1:{query}", download=True)
        if not info or "entries" not in info or not info["entries"]:
            raise Exception("No results found.")
        entry = info["entries"][0]
        if not entry:
            raise Exception("Search returned no results.")
        return {
            "file": ydl.prepare_filename(entry),
            "title": entry.get("title", query),
            "duration": entry.get("duration", 0),
            "url": entry.get("webpage_url", ""),
            "video": False,
        }

# =========================
# DOWNLOAD VIDEO (no re-encoding)
# =========================

def download_video(query):
    ydl_opts = {
        "format": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]",
        "outtmpl": "/tmp/%(id)s.%(ext)s",
        "quiet": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "cookiefile": "cookies.txt",
        "extractor_args": {
            "youtube": {"player_client": ["tv"]}
        },
        "js_runtimes": {"node": {}},
        "merge_output_format": "mp4",
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch1:{query}", download=True)
        if not info or "entries" not in info or not info["entries"]:
            raise Exception("No results found.")
        entry = info["entries"][0]
        if not entry:
            raise Exception("Search returned no results.")
        return {
            "file": ydl.prepare_filename(entry),
            "title": entry.get("title", query),
            "duration": entry.get("duration", 0),
            "url": entry.get("webpage_url", ""),
            "video": True,
        }

# =========================
# HELPERS
# =========================

def fmt_duration(seconds):
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02}:{s:02}"
    return f"{m}:{s:02}"

def now_playing_text(item):
    dur = fmt_duration(item["duration"])
    icon = "🎬" if item.get("video") else "🎵"
    mode = "Video" if item.get("video") else "Audio"
    return (
        f"{icon} **Now Playing** [{mode}]\n\n"
        f"**{item['title']}**\n"
        f"⏱ Duration: `{dur}`\n"
        f"👤 Requested by: {item['requester']}"
    )

def now_playing_buttons():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭ Skip", callback_data="skip"),
        InlineKeyboardButton("🛑 End", callback_data="end"),
    ]])

# =========================
# PLAY NEXT IN QUEUE
# =========================

async def play_next(chat_id, bot_client):
    item = pop_queue(chat_id)
    if not item:
        await force_leave(chat_id)
        return

    stream = MediaStream(item["file"])
    played = False

    # First attempt
    try:
        await call_py.play(chat_id, stream)
        active_calls.add(chat_id)
        played = True
    except NoActiveGroupCall:
        await bot_client.send_message(chat_id, "❌ No active Voice Chat. Please start one first.")
        clear_queue(chat_id)
        active_calls.discard(chat_id)
        return
    except Exception:
        pass

    # If first attempt failed, force leave and retry once
    if not played:
        await force_leave(chat_id)
        await asyncio.sleep(2)
        try:
            await call_py.play(chat_id, stream)
            active_calls.add(chat_id)
            played = True
        except NoActiveGroupCall:
            await bot_client.send_message(chat_id, "❌ No active Voice Chat. Please start one first.")
            clear_queue(chat_id)
            return
        except Exception as e:
            await bot_client.send_message(chat_id, f"❌ Failed to play: {e}")
            return

    await bot_client.send_message(
        chat_id,
        now_playing_text(item),
        reply_markup=now_playing_buttons()
    )

# =========================
# STREAM END HANDLER
# =========================

@call_py.on_update()
async def on_stream_ended(_, update):
    if isinstance(update, StreamEnded):
        chat_id = update.chat_id
        active_calls.discard(chat_id)
        queue = get_queue(chat_id)
        if queue:
            await play_next(chat_id, bot)
        else:
            await force_leave(chat_id)

# =========================
# /start
# =========================

@bot.on_message(filters.command("start"))
async def start(_, message: Message):
    await message.reply_text(
        "🎶 **Music Bot**\n\n"
        "**Commands:**\n"
        "/play `<song>` — Play or queue audio\n"
        "/vplay `<song>` — Play or queue video\n"
        "/skip — Skip current song\n"
        "/queue — Show queue\n"
        "/end — Stop and clear queue\n"
    )

# =========================
# SHARED PLAY LOGIC
# =========================

async def handle_play(message: Message, query: str, is_video: bool):
    requester = message.from_user.first_name if message.from_user else "Someone"
    mode = "video" if is_video else "audio"
    msg = await message.reply_text(f"🔍 Searching **{query}** [{mode}]...")

    try:
        downloader = download_video if is_video else download_song
        song = await asyncio.to_thread(downloader, query)
    except Exception as e:
        return await msg.edit_text(f"❌ {e}")

    song["requester"] = requester
    chat_id = message.chat.id
    queue = get_queue(chat_id)

    if is_active(chat_id) or queue:
        add_to_queue(chat_id, song)
        pos = len(get_queue(chat_id))
        dur = fmt_duration(song["duration"])
        icon = "🎬" if is_video else "🎵"
        return await msg.edit_text(
            f"✅ **Added to Queue** #{pos}\n\n"
            f"{icon} **{song['title']}**\n"
            f"⏱ Duration: `{dur}`\n"
            f"👤 By: {requester}"
        )

    add_to_queue(chat_id, song)
    await msg.delete()
    await play_next(chat_id, bot)

# =========================
# /play
# =========================

@bot.on_message(filters.command("play"))
async def play(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/play <song name>`")
    await handle_play(message, " ".join(message.command[1:]), is_video=False)

# =========================
# /vplay
# =========================

@bot.on_message(filters.command("vplay"))
async def vplay(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/vplay <song name>`")
    await handle_play(message, " ".join(message.command[1:]), is_video=True)

# =========================
# /skip
# =========================

@bot.on_message(filters.command("skip"))
async def skip(_, message: Message):
    chat_id = message.chat.id
    queue = get_queue(chat_id)
    if not queue:
        await message.reply_text("⏹ No more songs. Leaving VC.")
        await force_leave(chat_id)
        return
    await message.reply_text("⏭ Skipping...")
    await play_next(chat_id, bot)

# =========================
# /end
# =========================

@bot.on_message(filters.command("end"))
async def end(_, message: Message):
    chat_id = message.chat.id
    clear_queue(chat_id)
    await force_leave(chat_id)
    await message.reply_text("🛑 Stopped and cleared the queue.")

# =========================
# /queue
# =========================

@bot.on_message(filters.command("queue"))
async def show_queue(_, message: Message):
    queue = get_queue(message.chat.id)
    if not queue:
        return await message.reply_text("📭 Queue is empty.")
    lines = [f"**🎶 Queue — {len(queue)} song(s)**\n"]
    for i, item in enumerate(queue, 1):
        icon = "🎬" if item.get("video") else "🎵"
        dur = fmt_duration(item["duration"])
        lines.append(
            f"`{i}.` {icon} **{item['title']}** `[{dur}]` — {item['requester']}"
        )
    await message.reply_text("\n".join(lines))

# =========================
# CALLBACK BUTTONS
# =========================

@bot.on_callback_query()
async def callbacks(_, query):
    chat_id = query.message.chat.id

    if query.data == "skip":
        await query.answer("Skipping...")
        queue = get_queue(chat_id)
        if not queue:
            await force_leave(chat_id)
            await query.message.edit_text("⏹ Queue ended. Left VC.")
        else:
            await query.message.edit_reply_markup(None)
            await play_next(chat_id, bot)

    elif query.data == "end":
        await query.answer("Stopping...")
        clear_queue(chat_id)
        await force_leave(chat_id)
        await query.message.edit_text("🛑 Music stopped and queue cleared.")

# =========================
# START BOT
# =========================

async def main():
    await assistant.start()
    await call_py.start()
    await bot.start()
    print("Music Bot Started")
    await idle()

asyncio.get_event_loop().run_until_complete(main())
