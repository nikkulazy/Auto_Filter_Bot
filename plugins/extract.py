import asyncio
import os
import logging
import aiofiles
import tempfile
import uuid
import requests
import json
import subprocess

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery



from database.ia_filterdb import get_file_details
from info import BIN_CHANNEL
from dreamxbotz.util.file_properties import get_name

logger = logging.getLogger(__name__)

# Telegraph init


def lang_name(code):
    mapping = {
        "eng": "English",
        "tam": "Tamil",
        "hin": "Hindi",
        "mal": "Malayalam",
        "tel": "Telugu",
        "kan": "Kannada",
        "jpn": "Japanese",
        "kor": "Korean",
        "ara": "Arabic",
        "spa": "Spanish",
        "fre": "French",
        "ger": "German",
        "und": "Unknown"
    }

    return mapping.get(code.lower(), code.upper())

def format_track(lang: str | None, title: str | None) -> str:
    lang = (lang or "").strip()
    title = (title or "").strip()

    if lang and lang.lower() != "und":
        return lang

    if title:
        return title

    return "und"


@Client.on_callback_query(filters.regex(r"^extract_data"), group=2)
async def extract_data_handler(client: Client, query: CallbackQuery):
    try:
        await query.answer("Fetching Details...", show_alert=False)
    except Exception:
        pass

    _, file_id = query.data.split(":")

    current_markup = query.message.reply_markup
    wait_keyboard = []

    if current_markup and getattr(current_markup, "inline_keyboard", None):
        for row in current_markup.inline_keyboard:
            new_row = []
            for btn in row:
                if btn.callback_data == query.data:
                    new_row.append(
                        InlineKeyboardButton("ᴘʟᴇᴀꜱᴇ ᴡᴀɪᴛ... ⏳", callback_data="wait_data")
                    )
                else:
                    new_row.append(btn)
            wait_keyboard.append(new_row)

    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(wait_keyboard))
    except Exception:
        pass

    temp_path = os.path.join(
        tempfile.gettempdir(),
        f"acc_{query.from_user.id}_{query.message.id}_{uuid.uuid4().hex}.tmp"
    )

    try:
        files_ = await get_file_details(file_id)
        if not files_:
            await query.message.reply_text("❌ File not found in DB.", quote=True)
            return

        if query.message and query.message.media:
            log_msg = query.message
        else:
            log_msg = await client.send_cached_media(
                chat_id=BIN_CHANNEL,
                file_id=file_id
            )



        
        chunk_limit = 3

        async with aiofiles.open(temp_path, "wb") as f:
            async for chunk in client.stream_media(log_msg, limit=chunk_limit):
                await f.write(chunk)

        audio_tracks = []
        subtitle_tracks = []
        video_info = []

        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                temp_path
            ],
            capture_output=True,
            text=True
        )
        if result.returncode != 0 or not result.stdout.strip():
            await query.message.reply_text(
                "❌ Unable to read media information.",
                quote=True
            )
            return
        data = json.loads(result.stdout)

        seen_audio = set()
        seen_subs = set()

        for stream in data.get("streams", []):

            codec_type = stream.get("codec_type")

            if codec_type == "video":
                codec = stream.get("codec_name", "Unknown")
                width = stream.get("width", "?")
                height = stream.get("height", "?")

                video_info.append(
                    f"Video: {codec.upper()} {width}x{height}"
                )

            elif codec_type == "audio":
                tags = stream.get("tags", {})

                lang = lang_name(tags.get("language", "und"))

                if lang not in seen_audio:
                    seen_audio.add(lang)

                    audio_tracks.append({
                        "language": lang,
                        "title": tags.get("title", "")
                    })

            elif codec_type == "subtitle":
                tags = stream.get("tags", {})

                lang = lang_name(tags.get("language", "und"))
                title = tags.get("title", "").strip()

                if lang not in seen_subs:
                    seen_subs.add(lang)

                    subtitle_tracks.append({
                        "language": lang,
                        "title": title
                    })


        text = "<b>🎬 Available Tracks</b>\n\n"

        if video_info:
            text += "<b>📹 Video</b>\n"
            for v in video_info:
                text += f"• {v}\n"

        if audio_tracks:
            text += f"\n<b>🔊 Audio Tracks ({len(audio_tracks)})</b>\n"
            for a in audio_tracks:
                text += f"• {a['language']}\n"

        if subtitle_tracks:
            text += f"\n<b>💬 Subtitle Tracks ({len(subtitle_tracks)})</b>\n"
            for s in subtitle_tracks:
                line = s["language"]

                if s["title"]:
                    line += f" - {s['title']}"

                text += f"• {line}\n"

        await query.message.reply_text(
            text,
            quote=True
        )

        try:
            await query.edit_message_reply_markup(
                reply_markup=current_markup
            )
        except:
            pass

    except Exception as e:
        logger.exception(e)
        await query.message.reply_text(f"Error: {e}", quote=True)

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
