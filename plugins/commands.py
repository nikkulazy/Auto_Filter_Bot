import os
import re, sys
import json
import base64
import logging
import random
import asyncio
import string
import pytz
from .pmfilter import auto_filter 
from Script import script
from datetime import datetime
from database.refer import referdb
from database.config_db import mdb
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardMarkup
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, ChatAdminRequired, UserNotParticipant
from database.ia_filterdb import Media, Media2, get_file_details, unpack_new_file_id, get_bad_files
from database.users_chats_db import db
from info import *
from utils import get_settings, save_group_settings, is_subscribed, is_req_subscribed, get_size, get_shortlink, is_check_admin, temp, get_readable_time, get_time, generate_settings_text, log_error, clean_filename



logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Kolkata"
BATCH_FILES = {}

# ✅ Free users ko sirf 360p & 480p quality allow
FREE_QUALITIES = ["360p", "480p"]

# Timer function for countdown warning
async def send_with_timer(client, message, file_id, caption, reply_markup, settings, delete_time):
    """Send file with countdown timer warning below - file auto delete after time expires"""
    # पहले फाइल भेजो
    msg = await client.send_cached_media(
        chat_id=message.from_user.id, 
        file_id=file_id, 
        caption=caption, 
        protect_content=settings.get('file_secure', PROTECT_CONTENT), 
        reply_markup=reply_markup
    )
    
    if delete_time <= 0:
        return msg
    
    # फाइल के नीचे टाइमर भेजो
    warn = await msg.reply_text(
        f"⚠️ Deleted Time {delete_time}s - <a href='https://t.me/Savefilevideo/1452'>Saved Quickly</a>", 
        quote=True
    )
    
    # Countdown loop
    for s in range(delete_time - 1, 0, -1):
        try:
            await warn.edit_text(f"⚠️ Deleted Time {s}s - <a href='https://t.me/Savefilevideo/1452'>Saved Quickly</a>")
        except:
            pass
        await asyncio.sleep(1)
    
    # Delete files after timer ends
    try:
        await msg.delete()
        await warn.delete()
        await message.reply_text(
            "<b>ʏᴏᴜʀ ᴠɪᴅᴇᴏ / ꜰɪʟᴇ ɪꜱ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ !!\n\n𝚂𝚎𝚊𝚛𝚌𝚑 𝙰𝚐𝚊𝚒𝚗 𝙸𝚗 𝙶𝚛𝚘𝚞𝚙... !</b>", 
            quote=True
        )
        await asyncio.sleep(600)
        await confirm.delete()
    except:
        pass
    return None


# Timer function for multiple files (allfiles)
async def send_with_timer_allfiles(client, message, files_list, delete_time):
    """Send multiple files with countdown timer warning below - all files auto delete after time expires"""
    sent_messages = []
    
    # पहले सारी फाइल्स भेजो
    for file_data in files_list:
        msg = await client.send_cached_media(
            chat_id=message.from_user.id,
            file_id=file_data['file_id'],
            caption=file_data['caption'],
            protect_content=file_data.get('protect_content', PROTECT_CONTENT),
            reply_markup=file_data.get('reply_markup', None)
        )
        sent_messages.append(msg)
    
    if delete_time <= 0:
        return sent_messages
    
    # आखिरी फाइल के नीचे टाइमर भेजो
    warn = await sent_messages[-1].reply_text(
        f"⚠️ Deleting Time {delete_time}s - Saved Quickly",
        quote=True
    )
    
    # Countdown loop
    for s in range(delete_time - 1, 0, -1):
        try:
            await warn.edit_text(f"⚠️ Deleted Time {s}s - Saved Quickly")
        except:
            pass
        await asyncio.sleep(1)
    
    # Delete all files after timer ends
    try:
        for msg in sent_messages:
            await msg.delete()
        await warn.delete()
        confirm = await message.reply_text(
            "<b>ʏᴏᴜʀ ᴠɪᴅᴇᴏ / ꜰɪʟᴇ ɪꜱ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ !!\n\n𝚂𝚎𝚊𝚛𝚌𝚑 𝙰𝚐𝚊𝚒𝚗 𝙸𝚗 𝙶𝚛𝚘𝚞𝚙... !</b>",
            quote=True
        )
        await asyncio.sleep(600)
        await confirm.delete()
    except:
        pass
    return None

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    if EMOJI_MODE:
        try:
            await message.react(emoji=random.choice(REACTIONS), big=True)
        except Exception:
            await message.react(emoji="⚡️", big=True)
    m = message
    if len(m.command) == 2 and m.command[1].startswith(('notcopy', 'sendall')):
        _, userid, verify_id, file_id = m.command[1].split("_", 3)
        user_id = int(userid)
        grp_id = temp.VERIFICATIONS.get(user_id, 0)
        settings = await get_settings(grp_id)         
        verify_id_info = await db.get_verify_id_info(user_id, verify_id)
        if not verify_id_info or verify_id_info["verified"]:
            return await message.reply("<b>Your link has expired or already verified...</b>")  
        
        ist_timezone = pytz.timezone('Asia/Kolkata')
        if await db.user_verified(user_id):
            key = "third_time_verified"
        else:
            key = "second_time_verified" if await db.is_user_verified(user_id) else "last_verified"
        current_time = datetime.now(tz=ist_timezone)
        result = await db.update_notcopy_user(user_id, {key:current_time})
        await db.update_verify_id_info(user_id, verify_id, {"verified":True})
        if key == "third_time_verified": 
            num = 3 
        else: 
            num =  2 if key == "second_time_verified" else 1 
        if key == "third_time_verified": 
            msg = script.THIRDT_VERIFY_COMPLETE_TEXT
        else:
            msg = script.SECOND_VERIFY_COMPLETE_TEXT if key == "second_time_verified" else script.VERIFY_COMPLETE_TEXT
        if message.command[1].startswith('sendall'):
            verifiedfiles = f"https://telegram.me/{temp.U_NAME}?start=allfiles_{grp_id}_{file_id}"
        else:
            verifiedfiles = f"https://telegram.me/{temp.U_NAME}?start=file_{grp_id}_{file_id}"
        await client.send_message(settings['log'], script.VERIFIED_LOG_TEXT.format(m.from_user.mention, user_id, datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d %B %Y'), num))
        btn = [[
            InlineKeyboardButton("✅ Click Here To Get File ✅", url=verifiedfiles),
        ]]
        reply_markup=InlineKeyboardMarkup(btn)
        dlt=await m.reply_photo(
            photo=(VERIFY_IMG),
            caption=msg.format(message.from_user.mention, get_readable_time(TWO_VERIFY_GAP)),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        await asyncio.sleep(300)
        await dlt.delete()
        return         
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        buttons = [[
                    InlineKeyboardButton('❤️ Add Me To Your Group ❤️', url=f'http://t.me/{temp.U_NAME}?startgroup=true')
                ],[
                    InlineKeyboardButton('🍿 Update Channel 🍿', url=UPDATE_CHNL_LNK)
                  ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply(script.GSTART_TXT.format(message.from_user.mention if message.from_user else message.chat.title, temp.U_NAME, temp.B_NAME), reply_markup=reply_markup, disable_web_page_preview=True)
        await asyncio.sleep(2) 
        if not await db.get_chat(message.chat.id):
            total=await client.get_chat_members_count(message.chat.id)
            await client.send_message(LOG_CHANNEL, script.LOG_TEXT_G.format(message.chat.title, message.chat.id, total, "Unknown"))       
            await db.add_chat(message.chat.id, message.chat.title)
        return 
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(message.from_user.id, message.from_user.mention))
    if len(message.command) != 2:
        buttons = [[
                    InlineKeyboardButton('🔰 Add Me To Your Group 🔰', url=f'http://telegram.me/{temp.U_NAME}?startgroup=true')
                ],[
                    InlineKeyboardButton(' Help 🎭', callback_data='help'),
                    InlineKeyboardButton(' About ♻️', callback_data='about')
                ],[
                    InlineKeyboardButton(' Mᴏᴠɪᴇ Gᴜɪᴅᴇ', url='http://t.me/wolverine273_bot/app2'),
                    InlineKeyboardButton(' Uᴘɢʀᴀᴅᴇ 🎟', callback_data="premium_info"),
                ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        m=await message.reply_text("⏳")
        await asyncio.sleep(0.4)
        await m.delete()        
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.START_TXT.format(message.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        return

    if len(message.command) == 2 and message.command[1] in ["subscribe", "error", "okay", "help"]:
        buttons = [[
                    InlineKeyboardButton('🔰 Add Me To Your Group 🔰', url=f'http://telegram.me/{temp.U_NAME}?startgroup=true')
                ],[
                    InlineKeyboardButton(' Help 🎭', callback_data='help'),
                    InlineKeyboardButton(' About ♻️', callback_data='about')
                ],[
                    InlineKeyboardButton(' Mᴏᴠɪᴇ Gᴜɪᴅᴇ', url='http://t.me/Misslazy_bot/app'),
                    InlineKeyboardButton('Uᴘɢʀᴀᴅᴇ 🎟', callback_data="premium_info"),
                ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        m=await message.reply_text("⏳")
        await asyncio.sleep(0.4)
        await m.delete()        
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.START_TXT.format(message.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        return
    if message.command[1].startswith("reff_"):
        try:
            user_id = int(message.command[1].split("_")[1])
        except ValueError:
            await message.reply_text("Invalid refer!")
            return
        if user_id == message.from_user.id:
            await message.reply_text("Hey Dᴜᴍᴇ, Yᴏᴜ Cᴀɴ'ᴛ Rᴇғᴇʀ Yᴏᴜʀsᴇʟғ 🤣!\n\nsʜᴀʀᴇ ʏᴏᴜʀ ʟɪɴᴋ ᴛᴏ ʏᴏᴜʀ ғʀɪᴇɴᴅs ᴀɴᴅ ɢᴇᴛ 10 ʀᴇғᴇʀʀᴀʟ ᴘᴏɪɴᴛs ɪғ ʏᴏᴜ ᴀʀᴇ ᴄᴏʀʀᴇᴄᴛʟʏ ᴄᴏᴍᴘʟᴇᴛɪɴɢ 100 ʀᴇғᴇʀʀᴀʟ ᴘᴏɪɴᴛs ᴛʜᴇɴ ʏᴏᴜ ᴄᴀɴ ɢᴇᴛ 1 ᴍᴏɴᴛʜ ғʀᴇᴇ ᴘʀᴇᴍɪᴜᴍ ᴍᴇᴍʙᴇʀsʜɪᴘ.")
            return
        if referdb.is_user_in_list(message.from_user.id):
            await message.reply_text("Yᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ᴀʟʀᴇᴀᴅʏ ɪɴᴠɪᴛᴇᴅ ❗")
            return
        if await db.is_user_exist(message.from_user.id): 
            await message.reply_text("‼️ Yᴏᴜ Hᴀᴠᴇ Bᴇᴇɴ Aʟʀᴇᴀᴅʏ Iɴᴠɪᴛᴇᴅ ᴏʀ Jᴏɪɴᴇᴅ")
            return 
        try:
            uss = await client.get_users(user_id)
        except Exception:
            return 	    
        referdb.add_user(message.from_user.id)
        fromuse = referdb.get_refer_points(user_id) + 10
        if fromuse == 100:
            referdb.add_refer_points(user_id, 0) 
            await message.reply_text(f"🎉 ᴄᴏɴɢʀᴀᴛᴜʟᴀᴛɪᴏɴ! ʏᴏᴜ ɢᴏᴛ 𝟷 ᴍᴏɴᴛʜ ғʀᴇᴇ ᴘʀᴇᴍɪᴜᴍ sᴜᴄᴄᴇssғᴜʟʟʏ ʏᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ ᴡɪʟʟ ʙᴇ ᴀᴅᴅᴇᴅ sᴏᴏɴ ᴀғᴛᴇʀ ᴛʜɪs ʀᴇǫᴜᴇsᴛ ᴘʀᴏᴄᴇss ʙʏ ᴏᴜʀ ᴏᴡɴᴇʀ ☞ {uss.mention}!")		    
            await message.reply_text(user_id, f"You have been successfully invited by {message.from_user.mention}!") 	
            seconds = 2592000
            if seconds > 0:
                expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
                user_data = {"id": user_id, "expiry_time": expiry_time}  # Using "id" instead of "user_id"  
                await db.update_user(user_data)  # Use the update_user method to update or insert user data		    
                await client.send_message(
                chat_id=user_id,
                text=f"<b>Hey {uss.mention}\n\nYᴏᴜ ɢᴏᴛ 1 ᴍᴏɴᴛʜ ᴘʀᴇᴍɪᴜᴍ sᴜᴄsᴄʀɪᴘᴛɪᴏɴ ʙʏ ɪɴᴠɪᴛɪɴɢ 10 ᴜsᴇʀs ❗", disable_web_page_preview=True              
                )
            for admin in ADMINS:
                await client.send_message(chat_id=admin, text=f"Sᴜᴄᴄᴇss ғᴜʟʟʏ ᴛᴀsᴋ ᴄᴏᴍᴘʟᴇᴛᴇᴅ ʙʏ ᴛʜɪs ᴜsᴇʀ:\n\nuser Nᴀᴍᴇ: {uss.mention}\n\nUsᴇʀ ɪᴅ: {uss.id}!")	
        else:
            referdb.add_refer_points(user_id, fromuse)
            await message.reply_text(f"You have been successfully invited by {uss.mention}!")
            await client.send_message(user_id, f"ᴄᴏɴɢʀᴀᴛᴜʟᴀᴛɪᴏɴ! ʏᴏᴜ ɢᴏᴛ 𝟷𝟶 ʀᴇғᴇʀʀᴀʟ ᴘᴏɪɴᴛs ᴏɴ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ʏᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ ᴡɪʟʟ ʙᴇ ᴀᴅᴅᴇᴅ sᴏᴏɴ ᴀғᴛᴇʀ ᴛʜɪs ʀᴇǫᴜᴇsᴛ ᴘʀᴏᴄᴇss ʙʏ ᴏᴜʀ ᴏᴡɴᴇʀ ☞{message.from_user.mention}!")
        return
        
    if len(message.command) == 2 and message.command[1] in ["premium"]:
        buttons = [[
                    InlineKeyboardButton('📲 ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴs ᴘʀɪᴄᴇ ᴄʜᴀʀᴛ', url=OWNER_LNK)
                  ],[
                    InlineKeyboardButton('❌ ᴄʟᴏsᴇ ❌', callback_data='close_data')
                  ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_photo(
            photo=(SUBSCRIPTION),
            caption=script.PREPLANS_TXT.format(message.from_user.mention, OWNER_UPI_ID, QR_CODE),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        return  
    
    if len(message.command) == 2 and message.command[1].startswith('getfile'):
        movies = message.command[1].split("-", 1)[1] 
        movie = movies.replace('-',' ')
        message.text = movie 
        await auto_filter(client, message) 
        return
    
    data = message.command[1]
    try:
        _, grp_id, file_id = data.split("_", 2)
        grp_id = int(grp_id)
    except:
        _, grp_id, file_id = "", 0, data

    if not await db.has_premium_access(message.from_user.id): 
        try:
            btn = []
            chat = int(data.split("_", 2)[1])
            settings      = await get_settings(chat)
            fsub_channels = list(dict.fromkeys((settings.get('fsub', []) if settings else [])+ AUTH_CHANNELS)) 

            if fsub_channels:
                btn += await is_subscribed(client, message.from_user.id, fsub_channels)
            if AUTH_REQ_CHANNELS:
                btn += await is_req_subscribed(client, message.from_user.id, AUTH_REQ_CHANNELS)
            if btn:
                if len(message.command) > 1 and "_" in message.command[1]:
                    kk, file_id = message.command[1].split("_", 1)
                    btn.append([
                        InlineKeyboardButton("♻️ ᴛʀʏ ᴀɢᴀɪɴ ♻️", callback_data=f"checksub#{kk}#{file_id}")
                    ])
                    reply_markup = InlineKeyboardMarkup(btn)
                photo = random.choice(FSUB_PICS) if FSUB_PICS else "https://graph.org/file/7478ff3eac37f4329c3d8.jpg"
                caption = (
                    f"👋 Hᴇʟʟᴏ {message.from_user.mention}\n\n"
                    "🛑 Yᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴛʜᴇ ʀᴇǫᴜɪʀᴇᴅ ᴄʜᴀɴɴᴇʟs ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ.\n"
                    "👉 Jᴏɪɴ ᴀʟʟ ᴛʜᴇ ʙᴇʟᴏᴡ ᴄʜᴀɴɴᴇʟs ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ."
                )
                await message.reply_photo(
                    photo=photo,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode=enums.ParseMode.HTML
                )
                return

        except Exception as e:
            await log_error(client, f"❌ Force Sub Error:\n\n{repr(e)}")
            logger.error(f"❌ Force Sub Error:\n\n{repr(e)}")


    user_id = m.from_user.id
    if not await db.has_premium_access(user_id):
        try:
            grp_id = int(grp_id)
            user_verified = await db.is_user_verified(user_id)
            settings = await get_settings(grp_id)
            is_second_shortener = await db.use_second_shortener(user_id, settings.get('verify_time', TWO_VERIFY_GAP)) 
            is_third_shortener = await db.use_third_shortener(user_id, settings.get('third_verify_time', THREE_VERIFY_GAP))
            if settings.get("is_verify", IS_VERIFY) and (not user_verified or is_second_shortener or is_third_shortener):
                verify_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=7))
                await db.create_verify_id(user_id, verify_id)
                temp.VERIFICATIONS[user_id] = grp_id
                if message.command[1].startswith('allfiles'):
                    verify = await get_shortlink(f"https://telegram.me/{temp.U_NAME}?start=sendall_{user_id}_{verify_id}_{file_id}", grp_id, is_second_shortener, is_third_shortener)
                else:
                    verify = await get_shortlink(f"https://telegram.me/{temp.U_NAME}?start=notcopy_{user_id}_{verify_id}_{file_id}", grp_id, is_second_shortener, is_third_shortener)
                if is_third_shortener:
                    howtodownload = settings.get('tutorial_3', TUTORIAL_3)
                else:
                    howtodownload = settings.get('tutorial_2', TUTORIAL_2) if is_second_shortener else settings.get('tutorial', TUTORIAL)
                buttons = [[
                    InlineKeyboardButton(text="♻️ Cʟɪᴄᴋ Hᴇʀᴇ Tᴏ Vᴇʀɪғʏ ♻️", url=verify)
                ],[
                    InlineKeyboardButton(text="⁉️ Hᴏᴡ Tᴏ Vᴇʀɪғʏ ⁉️", url=howtodownload)
                ]]
                reply_markup=InlineKeyboardMarkup(buttons)
                if await db.user_verified(user_id): 
                    msg = script.THIRDT_VERIFICATION_TEXT
                else:            
                    msg = script.SECOND_VERIFICATION_TEXT if is_second_shortener else script.VERIFICATION_TEXT
                n=await m.reply_text(
                    text=msg.format(message.from_user.mention),
                    protect_content = True,
                    reply_markup=reply_markup,
                    parse_mode=enums.ParseMode.HTML
                )
                await asyncio.sleep(300) 
                await n.delete()
                await m.delete()
                return
        except Exception as e:
            print(f"Error In Verification - {e}")
            pass

    if data.startswith("allfiles"):
        try:
            files = temp.GETALL.get(file_id)
            if not files:
                return await message.reply('<b><i>Nᴏ sᴜᴄʜ ғɪʟᴇ ᴇxɪsᴛs !</b></i>')
            
            # Prepare files list for countdown timer
            files_list = []
            for file in files:
                file_id_single = file.file_id
                files_ = await get_file_details(file_id_single)
                files1 = files_[0]
                
                # ✅ Quality check for allfiles
                user_id = message.from_user.id
                is_premium = await db.has_premium_access(user_id)
                
                if QUALITY_LIMIT and not is_premium:
                    if not any(q in (files1.file_name or "").lower() for q in FREE_QUALITIES):
                        buttons = [[
                            InlineKeyboardButton('🎟 Upgrade to Premium 🎟', callback_data="premium_info")
                        ],[
                            InlineKeyboardButton('🔞 Jᴏɪɴ Oᴜʀ Cʜᴀɴɴᴇʟ 📌', url=UPDATE_CHNL_LNK)
                        ]]
                        reply_markup = InlineKeyboardMarkup(buttons)
                        await message.reply_photo(
                            photo="http://ibb.co/608JNcwR",
                            caption=f"⚠️ Hey {message.from_user.mention},\n\n"
                                    f"Ye file sirf <b>Premium Users</b> ke liye available hai.\n\n"
                                    f"Free users ko sirf 360p & 480p quality milti hai ✅",
                            reply_markup=reply_markup,
                            parse_mode=enums.ParseMode.HTML
                        )
                        return
        
                title = clean_filename(files1.file_name)
                size = get_size(files1.file_size)
                f_caption = files1.caption
                settings = await get_settings(int(grp_id))
                DREAMX_CAPTION = settings.get('caption', CUSTOM_FILE_CAPTION)
                if DREAMX_CAPTION:
                    try:
                        f_caption = DREAMX_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
                    except Exception as e:
                        logger.exception(e)
                        f_caption = f_caption
                if f_caption is None:
                    f_caption = f"{clean_filename(files1.file_name)}"
                
                # Create buttons
                if STREAM_MODE and not PREMIUM_STREAM_MODE:
                    btn = [
                        [InlineKeyboardButton('🚀 Sᴛʀᴇᴀᴍ Dᴏᴡɴʟᴏᴀᴅ / Wᴀᴛᴄʜ Oɴʟɪɴᴇ 🖥️', callback_data=f'generate_stream_link:{file_id_single}')],
                        [InlineKeyboardButton('🔈𝚅𝚒𝚎𝚠 𝙰𝚞𝚍𝚒𝚘 & 𝚅𝚒𝚍𝚎𝚘 𝙸𝚗𝚏𝚘ℹ️', callback_data=f'extract_data:{file_id_single}')],
                        [InlineKeyboardButton('🔞 Jᴏɪɴ Oᴜʀ Cʜᴀɴɴᴇʟ 📌', url=UPDATE_CHNL_LNK)]
                    ]
                elif STREAM_MODE and PREMIUM_STREAM_MODE:
                    if not await db.has_premium_access(message.from_user.id):
                        btn = [
                            [InlineKeyboardButton('🚀 Sᴛʀᴇᴀᴍ Dᴏᴡɴʟᴏᴀᴅ / Wᴀᴛᴄʜ Oɴʟɪɴᴇ 🖥️', callback_data=f'prestream')],
                            [InlineKeyboardButton('🔈𝚅𝚒𝚎𝚠 𝙰𝚞𝚍𝚒𝚘 & 𝚅𝚒𝚍𝚎𝚘 𝙸𝚗𝚏𝚘ℹ️', callback_data=f'prestream')],
                            [InlineKeyboardButton('🔞 Jᴏɪɴ Oᴜʀ Cʜᴀɴɴᴇʟ 📌', url=UPDATE_CHNL_LNK)]
                        ]
                    else:
                        btn = [
                            [InlineKeyboardButton('🚀 Sᴛʀᴇᴀᴍ Dᴏᴡɴʟᴏᴀᴅ / Wᴀᴛᴄʜ Oɴʟɪɴᴇ 🖥️', callback_data=f'generate_stream_link:{file_id_single}')],
                            [InlineKeyboardButton('🔈𝚅𝚒𝚎𝚠 𝙰𝚞𝚍𝚒𝚘 & 𝚅𝚒𝚍𝚎𝚘 𝙸𝚗𝚏𝚘ℹ️', callback_data=f'extract_data:{file_id_single}')],
                            [InlineKeyboardButton('🔞 Jᴏɪɴ Oᴜʀ Cʜᴀɴɴᴇʟ 📌', url=UPDATE_CHNL_LNK)]
                        ]
                else:
                    btn = [[InlineKeyboardButton('🔞 Jᴏɪɴ Oᴜʀ Cʜᴀɴɴᴇʟ 📌', url=UPDATE_CHNL_LNK)]]
                
                files_list.append({
                    'file_id': file_id_single,
                    'caption': f_caption,
                    'protect_content': settings.get('file_secure', PROTECT_CONTENT),
                    'reply_markup': InlineKeyboardMarkup(btn)
                })
            
            # Send all files with countdown timer
            if IS_FILE_LIMIT:
                is_premium = await db.has_premium_access(message.from_user.id)
                if not is_premium:
                    count = await db.get_user_limit(message.from_user.id)
                    if count >= FILES_LIMIT:
                        return await message.reply_text("🚫 Daily download limit reached. Try again after 24 hours.")
                    await db.increment_user_limit(message.from_user.id)
                    remaining = FILES_LIMIT - count - 1
                    await message.reply_text(f"📦 Remaining limit: {remaining}/{FILES_LIMIT}")
            
            # Send all files with countdown warning
            await send_with_timer_allfiles(
                client=client,
                message=message,
                files_list=files_list,
                delete_time=DELETE_TIME
            )
            return
            
        except Exception as e:
            logger.exception(e)
            return

    user = message.from_user.id
    files_ = await get_file_details(file_id)
    settings = await get_settings(int(grp_id))
    if not files_:
        pre, file_id = ((base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("ascii")).split("_", 1)
        try:
            if STREAM_MODE and not PREMIUM_STREAM_MODE:
                btn = [
                    [InlineKeyboardButton('🚀 Sᴛʀᴇᴀᴍ Dᴏᴡɴʟᴏᴀᴅ / Wᴀᴛᴄʜ Oɴʟɪɴᴇ 🖥️', callback_data=f'generate_stream_link:{file_id}')],
                    [InlineKeyboardButton('🔈𝚅𝚒𝚎𝚠 𝙰𝚞𝚍𝚒𝚘 & 𝚅𝚒𝚍𝚎𝚘 𝙸𝚗𝚏𝚘ℹ️', callback_data=f'extract_data:{file_id}')],
                    [InlineKeyboardButton('🔞 Jᴏɪɴ Oᴜʀ Cʜᴀɴɴᴇʟ 📌', url=UPDATE_CHNL_LNK)]
                ]
            elif STREAM_MODE and PREMIUM_STREAM_MODE:
                if not await db.has_premium_access(message.from_user.id):
                   btn = [
                        [InlineKeyboardButton('🚀 Sᴛʀᴇᴀᴍ Dᴏᴡɴʟᴏᴀᴅ / Wᴀᴛᴄʜ Oɴʟɪɴᴇ 🖥️', callback_data=f'prestream')],
                        [InlineKeyboardButton('🔈𝚅𝚒𝚎𝚠 𝙰𝚞𝚍𝚒𝚘 & 𝚅𝚒𝚍𝚎𝚘 𝙸𝚗𝚏𝚘ℹ️', callback_data=f'prestream')],
                        [InlineKeyboardButton('🔞 Jᴏɪɴ Oᴜʀ Cʜᴀɴɴᴇʟ 📌', url=UPDATE_CHNL_LNK)]
                    ]
                else:
                    btn = [
                        [InlineKeyboardButton('🚀 Sᴛʀᴇᴀᴍ Dᴏᴡɴʟᴏᴀᴅ / Wᴀᴛᴄʜ Oɴʟɪɴᴇ 🖥️', callback_data=f'generate_stream_link:{file_id}')],
                        [InlineKeyboardButton('🔈𝚅𝚒𝚎𝚠 𝙰𝚞𝚍𝚒𝚘 & 𝚅𝚒𝚍𝚎𝚘 𝙸𝚗𝚏𝚘ℹ️', callback_data=f'extract_data:{file_id}')],
                        [InlineKeyboardButton('🔞 Jᴏɪɴ Oᴜʀ Cʜᴀɴɴᴇʟ 📌', url=UPDATE_CHNL_LNK)]
                    ]
            else:
                btn = [[InlineKeyboardButton('🔞 Jᴏɪɴ Oᴜʀ Cʜᴀɴɴᴇʟ 📌', url=UPDATE_CHNL_LNK)]] 
            if IS_FILE_LIMIT:
                    is_premium = await db.has_premium_access(message.from_user.id)
                    if not is_premium:
                        count = await db.get_user_limit(message.from_user.id)
                        if count >= FILES_LIMIT:
                            return await message.reply_text("🚫 Daily download limit reached. Try again after 24 hours.")
                        await db.increment_user_limit(message.from_user.id)
                        remaining = FILES_LIMIT - count - 1
                        await message.reply_text(f"📦 Remaining limit: {remaining}/{FILES_LIMIT}")
        except Exception as e:
            print(f"Error in setting buttons: {e}")
            btn = [[InlineKeyboardButton('🔞 Jᴏɪɴ Oᴜʀ Cʜᴀɴɴᴇʟ 📌', url=UPDATE_CHNL_LNK)]]
    
    files = files_[0]
    # ✅ Quality restriction for single file
    is_premium = await db.has_premium_access(user)
    file_quality = getattr(files, "quality", "")
    if QUALITY_LIMIT and not is_premium:
        if not any(q in (files.file_name or "").lower() for q in FREE_QUALITIES):
            buttons = [[
                InlineKeyboardButton('🎟 Upgrade to Premium 🎟', callback_data="premium_info")
            ],[
                InlineKeyboardButton('🔞 Jᴏɪɴ Oᴜʀ Cʜᴀɴɴᴇʟ 📌', url=UPDATE_CHNL_LNK)
            ]]
            reply_markup = InlineKeyboardMarkup(buttons)
            await message.reply_photo(
                photo="http://ibb.co/608JNcwR",
                caption=f"⚠️ Hey {message.from_user.mention},\n\n"
                        f"Ye file sirf <b>Premium Users</b> ke liye available hai.\n\n"
                        f"Free users ko sirf 360p & 480p quality milti hai ✅",
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            )
            return

    title = clean_filename(files.file_name)
    size = get_size(files.file_size)
    f_caption = files.caption
    settings = await get_settings(int(grp_id))            
    DREAMX_CAPTION = settings.get('caption', CUSTOM_FILE_CAPTION)
    if DREAMX_CAPTION:
        try:
            f_caption = DREAMX_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
        except Exception as e:
            logger.exception(e)
            f_caption = f_caption

    if f_caption is None:
        f_caption = clean_filename(files.file_name)
    
    if STREAM_MODE and not PREMIUM_STREAM_MODE:
        btn = [
            [InlineKeyboardButton('🚀 Sᴛʀᴇᴀᴍ Dᴏᴡɴʟᴏᴀᴅ / Wᴀᴛᴄʜ Oɴʟɪɴᴇ 🖥️', callback_data=f'generate_stream_link:{file_id}')],
            [InlineKeyboardButton('🔈𝚅𝚒𝚎𝚠 𝙰𝚞𝚍𝚒𝚘 & 𝚅𝚒𝚍𝚎𝚘 𝙸𝚗𝚏𝚘ℹ️', callback_data=f'extract_data:{file_id}')],
            [InlineKeyboardButton('🔞 Jᴏɪɴ Oᴜʀ Cʜᴀɴɴᴇʟ 📌', url=UPDATE_CHNL_LNK)]
        ]
    elif STREAM_MODE and PREMIUM_STREAM_MODE:
        if not await db.has_premium_access(message.from_user.id):
            btn = [
                [InlineKeyboardButton('🚀 Sᴛʀᴇᴀᴍ Dᴏᴡɴʟᴏᴀᴅ / Wᴀᴛᴄʜ Oɴʟɪɴᴇ 🖥️', callback_data=f'prestream')],
                [InlineKeyboardButton('🔈𝚅𝚒𝚎𝚠 𝙰𝚞𝚍𝚒𝚘 & 𝚅𝚒𝚍𝚎𝚘 𝙸𝚗𝚏𝚘ℹ️', callback_data=f'prestream')],
                [InlineKeyboardButton('🔞 Jᴏɪɴ Oᴜʀ Cʜᴀɴɴᴇʟ 📌', url=UPDATE_CHNL_LNK)]
            ]
        else:
            btn = [
                [InlineKeyboardButton('🚀 Sᴛʀᴇᴀᴍ Dᴏᴡɴʟᴏᴀᴅ / Wᴀᴛᴄʜ Oɴʟɪɴᴇ 🖥️', callback_data=f'generate_stream_link:{file_id}')],
                [InlineKeyboardButton('🔈𝚅𝚒𝚎𝚠 𝙰𝚞𝚍𝚒𝚘 & 𝚅𝚒𝚍𝚎𝚘 𝙸𝚗𝚏𝚘ℹ️', callback_data=f'extract_data:{file_id}')],
                [InlineKeyboardButton('🔞 Jᴏɪɴ Oᴜʀ Cʜᴀɴɴᴇʟ 📌', url=UPDATE_CHNL_LNK)]
            ]
    else:
        btn = [[InlineKeyboardButton('🔞 Jᴏɪɴ Oᴜʀ Cʜᴀɴɴᴇʟ 📌', url=UPDATE_CHNL_LNK)]]
    
    if IS_FILE_LIMIT:
        is_premium = await db.has_premium_access(message.from_user.id)
        if not is_premium:
            count = await db.get_user_limit(message.from_user.id)
            if count >= FILES_LIMIT:
                return await message.reply_text("🚫 Daily download limit reached. Try again after 24 hours.")
            await db.increment_user_limit(message.from_user.id)
            remaining = FILES_LIMIT - count - 1
            await message.reply_text(f"📦 Remaining limit: {remaining}/{FILES_LIMIT}")
    
    # ✅ FIXED: Send single file with countdown timer
    await send_with_timer(
        client=client,
        message=message,
        file_id=file_id,
        caption=f_caption,
        reply_markup=InlineKeyboardMarkup(btn),
        settings=settings,
        delete_time=DELETE_TIME
    )

@Client.on_message(filters.command('logs') & filters.user(ADMINS))
async def log_file(bot, message):
    """Send log file"""
    try:
        await message.reply_document('DreamXlogs.txt', caption="📑 **Lᴏɢs**")
    except Exception as e:
        await message.reply(str(e))

@Client.on_message(filters.command('delete') & filters.user(ADMINS))
async def delete(bot, message):
    """Delete file from database"""
    reply = message.reply_to_message
    if reply and reply.media:
        msg = await message.reply("Pʀᴏᴄᴇssɪɴɢ...⏳", quote=True)
    else:
        await message.reply('Rᴇᴘʟʏ ᴛᴏ ᴀ ғɪʟᴇ ᴡɪᴛʜ /delete ᴡʜɪᴄʜ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴅᴇʟᴇᴛᴇ', quote=True)
        return

    for file_type in ("document", "video", "audio"):
        media = getattr(reply, file_type, None)
        if media is not None:
            break
    else:
        await msg.edit('Tʜɪs ɪs ɴᴏᴛ sᴜᴘᴘᴏʀᴛᴇᴅ ғɪʟᴇ ғᴏʀᴍᴀᴛ')
        return
    
    file_id, file_ref = unpack_new_file_id(media.file_id)
    if await Media.count_documents({'file_id': file_id}):
        result = await Media.collection.delete_one({
            '_id': file_id,
        })
    else:
        result = await Media2.collection.delete_one({
            '_id': file_id,
        })
    if result.deleted_count:
        await msg.edit('Fɪʟᴇ ɪs sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ғʀᴏᴍ ᴅᴀᴛᴀʙᴀsᴇ ✅')
    else:
        file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
        result = await Media.collection.delete_many({
            'file_name': file_name,
            'file_size': media.file_size,
            'mime_type': media.mime_type
            })
        if result.deleted_count:
            await msg.edit('Fɪʟᴇ ɪs sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ғʀᴏᴍ ᴅᴀᴛᴀʙᴀsᴇ ✅')
        else:
            result = await Media2.collection.delete_many({
                'file_name': file_name,
                'file_size': media.file_size,
                'mime_type': media.mime_type
            })
            if result.deleted_count:
                await msg.edit('Fɪʟᴇ ɪs sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ғʀᴏᴍ ᴅᴀᴛᴀʙᴀsᴇ ✅')
            else:
                result = await Media.collection.delete_many({
                    'file_name': media.file_name,
                    'file_size': media.file_size,
                    'mime_type': media.mime_type
                })
                if result.deleted_count:
                    await msg.edit('Fɪʟᴇ ɪs sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ғʀᴏᴍ ᴅᴀᴛᴀʙᴀsᴇ ✅')
                else:
                    result = await Media2.collection.delete_many({
                        'file_name': media.file_name,
                        'file_size': media.file_size,
                        'mime_type': media.mime_type
                    })
                    if result.deleted_count:
                        await msg.edit('Fɪʟᴇ ɪs sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ғʀᴏᴍ ᴅᴀᴛᴀʙᴀsᴇ ✅')
                    else:
                        await msg.edit('Fɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ ɪɴ ᴅᴀᴛᴀʙᴀsᴇ ❌')


@Client.on_message(filters.command('deleteall') & filters.user(ADMINS))
async def delete_all_index(bot, message):
    await message.reply_text(
        'Tʜɪs ᴡɪʟʟ ᴅᴇʟᴇᴛᴇ ᴀʟʟ ʏᴏᴜʀ ɪɴᴅᴇxᴇᴅ ғɪʟᴇs !\nDᴏ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ ?',
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="⚠️ Yᴇs ⚠️", callback_data="autofilter_delete"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Nᴏ ❌", callback_data="close_data"
                    )
                ],
            ]
        ),
        quote=True,
    )
from info import IS_FILE_LIMIT, FILES_LIMIT
from database.users_chats_db import db

@Client.on_message(filters.command("checklimit") & filters.user(ADMINS))
async def check_limit(client, message):
    if len(message.command) == 2:
        user_id = int(message.command[1])
        count = await db.get_user_limit(user_id)
        await message.reply_text(f"User {user_id} has used {count}/{FILES_LIMIT} files today.")
    else:
        await message.reply_text("Usage: /checklimit <user_id>")

@Client.on_message(filters.command("resetuser") & filters.user(ADMINS))
async def reset_single_user(client, message):
    if len(message.command) == 2:
        user_id = int(message.command[1])
        await db.reset_user_limit(user_id)
        await message.reply_text(f"✅ Reset limit for user {user_id}")
    else:
        await message.reply_text("Usage: /resetuser <user_id>")

@Client.on_message(filters.command("resetlimit") & filters.user(ADMINS))
async def reset_all_limits(client, message):
    modified = await db.reset_user_limit()
    await message.reply_text(f"✅ Reset limits for {modified} users.")

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio

# 🟢 Apna channel ID yaha daalo
REQUEST_CHANNEL = -1001521000125  

@Client.on_message(filters.command("request"))
async def request_movie(bot, message):
    # Agar sirf /request likha gaya ho
    if len(message.command) == 1:
        warn = await message.reply_text(
            "❌ Please use: /request movie_name",
            quote=True
        )
        await asyncio.sleep(10)
        await warn.delete()
        try:
            await message.delete()
        except:
            pass
        return

    # Movie ka naam
    movie_name = " ".join(message.command[1:])

    # Channel me request bhejna
    text = f"""
🎬 **New Movie Request**

👤 User: {message.from_user.mention}
🆔 User ID: `{message.from_user.id}`
📌 Movie: `{movie_name}`
    """
    await bot.send_message(REQUEST_CHANNEL, text)

    # User ko confirmation
    await message.reply_text("✅ Your request has been submitted!", quote=True)
    
@Client.on_message(filters.command('settings'))
async def settings(client, message):
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return await message.reply(f"Yᴏᴜ'ʀᴇ ᴀɴᴏɴʏᴍᴏᴜs ᴀᴅᴍɪɴ.")
    chat_type = message.chat.type
    if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        if not await is_check_admin(client, grp_id, message.from_user.id):
            return await message.reply_text(script.NT_ADMIN_ALRT_TXT)
        await db.connect_group(grp_id, user_id)
        btn = [[
                InlineKeyboardButton("👤 Oᴘᴇɴ Iɴ Pʀɪᴠᴀᴛᴇ Cʜᴀᴛ 👤", callback_data=f"opnsetpm#{grp_id}")
              ],[
                InlineKeyboardButton("🥷 Oᴘᴇɴ Hᴇʀᴇ 🥷", callback_data=f"opnsetgrp#{grp_id}")
              ]]
        await message.reply_text(
                text="<b>Wʜᴇʀᴇ Dᴏ Yᴏᴜ Wᴀɴᴛ Tᴏ Oᴘᴇɴ Sᴇᴛᴛɪɴɢs ? ♨️</b>",
                reply_markup=InlineKeyboardMarkup(btn),
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML,
                reply_to_message_id=message.id
        )
    elif chat_type == enums.ChatType.PRIVATE:
        connected_groups = await db.get_connected_grps(user_id)
        if not connected_groups:
            return await message.reply_text("Nᴏ Cᴏɴɴᴇᴄᴛᴇᴅ Gʀᴏᴜᴘs Fᴏᴜɴᴅ .")
        group_list = []
        for group in connected_groups:
            try:
                Chat = await client.get_chat(group)
                group_list.append([ InlineKeyboardButton(text=Chat.title, callback_data=f"grp_pm#{Chat.id}") ])
            except Exception as e:
                print(f"Error In PM Settings Button - {e}")
                pass
        await message.reply_text(
                    "⚠️ Sᴇʟᴇᴄᴛ ᴛʜᴇ ɢʀᴏᴜᴘ ᴡʜᴏsᴇ sᴇᴛᴛɪɴɢs ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴄʜᴀɴɢᴇ.\n\n"
                    "Iғ ʏᴏᴜʀ ɢʀᴏᴜᴘ ɪs ɴᴏᴛ sʜᴏᴡɪɴɢ ʜᴇʀᴇ,\n"
                    "ᴜsᴇ /reload ɪɴ ᴛʜᴀᴛ ɢʀᴏᴜᴘ ᴀɴᴅ ɪᴛ ᴡɪʟʟ ᴀᴘᴘᴇᴀʀ ʜᴇʀᴇ.",
                    reply_markup=InlineKeyboardMarkup(group_list)
                )
        
@Client.on_message(filters.command('reload'))
async def connect_group(client, message):
    user_id = message.from_user.id
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        await db.connect_group(message.chat.id, user_id)
        await message.reply_text("Gʀᴏᴜᴘ Rᴇʟᴏᴀᴅᴇᴅ ✅ Nᴏᴡ Yᴏᴜ Cᴀɴ Mᴀɴᴀɢᴇ Tʜɪs Gʀᴏᴜᴘ Fʀᴏᴍ PM.")
    elif message.chat.type == enums.ChatType.PRIVATE:
        if len(message.command) < 2:
            await message.reply_text("Example: /reload 123456789")
            return
        try:
            group_id = int(message.command[1])
            if not await is_check_admin(client, group_id, user_id):
                await message.reply_text(script.NT_ADMIN_ALRT_TXT)
                return
            chat = await client.get_chat(group_id)
            await db.connect_group(group_id, user_id)
            await message.reply_text(f"Lɪɴᴋᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ ✅ {chat.title} ᴛᴏ PM.")
        except:
            await message.reply_text("Invalid group ID or error occurred.")
            
@Client.on_message(filters.command('set_template'))
async def save_template(client, message):
    sts = await message.reply("Cʜᴇᴄᴋɪɴɢ Tᴇᴍᴘʟᴀᴛᴇ...")
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return await message.reply("Yᴏᴜ'ʀᴇ ᴀɴᴏɴʏᴍᴏᴜs ᴀᴅᴍɪɴ.")
    
    if message.chat.type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return await sts.edit("⚠️ Usᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ɪɴ ᴀ ɢʀᴏᴜᴘ ᴄʜᴀᴛ.")
    
    group_id = message.chat.id
    title = message.chat.title
    if not await is_check_admin(client, group_id, user_id):
        await message.reply_text(script.NT_ADMIN_ALRT_TXT)
        return
    if len(message.command) < 2:
        return await sts.edit("⚠️ Nᴏ Tᴇᴍᴘʟᴀᴛᴇ Pʀᴏᴠɪᴅᴇᴅ!")
    
    template = message.text.split(" ", 1)[1]
    await save_group_settings(group_id, 'template', template)
    await sts.edit(
        f"✅ Sᴜᴄᴄᴇssғᴜʟʟʏ ᴜᴘᴅᴀᴛᴇᴅ ᴛᴇᴍᴘʟᴀᴛᴇ ғᴏʀ <code>{title}</code> ᴛᴏ:\n\n{template}"
    )


# Must add REQST_CHANNEL and SUPPORT_CHAT_ID to use this feature 
@Client.on_message((filters.command(["request", "Request"]) | filters.regex("#request") | filters.regex("#Request")) & filters.group)
async def requests(bot, message):
    if REQST_CHANNEL is None or SUPPORT_CHAT_ID is None: return 
    if message.reply_to_message and SUPPORT_CHAT_ID == message.chat.id:
        chat_id = message.chat.id
        reporter = str(message.from_user.id)
        mention = message.from_user.mention
        success = True
        content = message.reply_to_message.text
        try:
            if REQST_CHANNEL is not None:
                btn = [[
                        InlineKeyboardButton('Pɪᴇᴅ Rᴇǫᴜᴇsᴛ', url=f"{message.reply_to_message.link}"),
                        InlineKeyboardButton('Sʜᴏᴡ Oᴘᴛɪᴏɴs', callback_data=f'show_option#{reporter}')
                      ]]
                reported_post = await bot.send_message(chat_id=REQST_CHANNEL, text=f"<b>📝 Rᴇǫᴜᴇsᴛ : <u>{content}</u>\n\n📚 Rᴇᴘᴏʀᴛᴇᴅ Bʏ : {mention}\n📖 Rᴇᴘᴏʀᴛᴇʀ Iᴅ : {reporter}\n\n</b>", reply_markup=InlineKeyboardMarkup(btn))
                success = True
            elif len(content) >= 3:
                for admin in ADMINS:
                    btn = [[
                        InlineKeyboardButton('Pɪᴇᴅ Rᴇǫᴜᴇsᴛ', url=f"{message.reply_to_message.link}"),
                        InlineKeyboardButton('Sʜᴏᴡ Oᴘᴛɪᴏɴs', callback_data=f'show_option#{reporter}')
                      ]]
                    reported_post = await bot.send_message(chat_id=admin, text=f"<b>📝 Rᴇǫᴜᴇsᴛ : <u>{content}</u>\n\n📚 Rᴇᴘᴏʀᴛᴇᴅ Bʏ : {mention}\n📖 Rᴇᴘᴏʀᴛᴇʀ Iᴅ : {reporter}\n\n</b>", reply_markup=InlineKeyboardMarkup(btn))
                    success = True
            else:
                if len(content) < 3:
                    await message.reply_text("<b>Yᴏᴜ ᴍᴜsᴛ ᴛʏᴘᴇ ᴀʙᴏᴜᴛ ʏᴏᴜʀ Rᴇǫᴜᴇsᴛ [ᴍɪɴɪᴍᴜᴍ 3 Cʜᴀʀᴀᴄᴛᴇʀs]. Rᴇǫᴜᴇsᴛs ᴄᴀɴ'ᴛ ʙᴇ ᴇᴍᴘᴛʏ.</b>")
            if len(content) < 3:
                success = False
        except Exception as e:
            await message.reply_text(f"Error: {e}")
            pass
    elif SUPPORT_CHAT_ID == message.chat.id:
        chat_id = message.chat.id
        reporter = str(message.from_user.id)
        mention = message.from_user.mention
        success = True
        content = message.text
        keywords = ["#request", "/request", "#Request", "/Request"]
        for keyword in keywords:
            if keyword in content:
                content = content.replace(keyword, "")
        try:
            if REQST_CHANNEL is not None and len(content) >= 3:
                btn = [[
                        InlineKeyboardButton('Pɪᴇᴅ Rᴇǫᴜᴇsᴛ', url=f"{message.link}"),
                        InlineKeyboardButton('Sʜᴏᴡ Oᴘᴛɪᴏɴs', callback_data=f'show_option#{reporter}')
                      ]]
                reported_post = await bot.send_message(chat_id=REQST_CHANNEL, text=f"<b>📝 Rᴇǫᴜᴇsᴛ : <u>{content}</u>\n\n📚 Rᴇᴘᴏʀᴛᴇᴅ Bʏ : {mention}\n📖 Rᴇᴘᴏʀᴛᴇʀ Iᴅ : {reporter}\n\n</b>", reply_markup=InlineKeyboardMarkup(btn))
                success = True
            elif len(content) >= 3:
                for admin in ADMINS:
                    btn = [[
                        InlineKeyboardButton('Pɪᴇᴅ Rᴇǫᴜᴇsᴛ', url=f"{message.link}"),
                        InlineKeyboardButton('Sʜᴏᴡ Oᴘᴛɪᴏɴs', callback_data=f'show_option#{reporter}')
                      ]]
                    reported_post = await bot.send_message(chat_id=admin, text=f"<b>📝 Rᴇǫᴜᴇsᴛ : <u>{content}</u>\n\n📚 Rᴇᴘᴏʀᴛᴇᴅ Bʏ : {mention}\n📖 Rᴇᴘᴏʀᴛᴇʀ Iᴅ : {reporter}\n\n</b>", reply_markup=InlineKeyboardMarkup(btn))
                    success = True
            else:
                if len(content) < 3:
                    await message.reply_text("<b>Yᴏᴜ ᴍᴜsᴛ ᴛʏᴘᴇ ᴀʙᴏᴜᴛ ʏᴏᴜʀ Rᴇǫᴜᴇsᴛ [ᴍɪɴɪᴍᴜᴍ 3 Cʜᴀʀᴀᴄᴛᴇʀs]. Rᴇǫᴜᴇsᴛs ᴄᴀɴ'ᴛ ʙᴇ ᴇᴍᴘᴛʏ.</b>")
            if len(content) < 3:
                success = False
        except Exception as e:
            await message.reply_text(f"Error: {e}")
            pass
    elif SUPPORT_CHAT_ID == message.chat.id:
        chat_id = message.chat.id
        reporter = str(message.from_user.id)
        mention = message.from_user.mention
        success = True
        content = message.text
        keywords = ["#request", "/request", "#Request", "/Request"]
        for keyword in keywords:
            if keyword in content:
                content = content.replace(keyword, "")
        try:
            if REQST_CHANNEL is not None and len(content) >= 3:
                btn = [[
                        InlineKeyboardButton('Pɪᴇᴅ Rᴇǫᴜᴇsᴛ', url=f"{message.link}"),
                        InlineKeyboardButton('Sʜᴏᴡ Oᴘᴛɪᴏɴs', callback_data=f'show_option#{reporter}')
                      ]]
                reported_post = await bot.send_message(chat_id=REQST_CHANNEL, text=f"<b>📝 Rᴇǫᴜᴇsᴛ : <u>{content}</u>\n\n📚 Rᴇᴘᴏʀᴛᴇᴅ Bʏ : {mention}\n📖 Rᴇᴘᴏʀᴛᴇʀ Iᴅ : {reporter}\n\n</b>", reply_markup=InlineKeyboardMarkup(btn))
                success = True
            elif len(content) >= 3:
                for admin in ADMINS:
                    btn = [[
                        InlineKeyboardButton('Pɪᴇᴅ Rᴇǫᴜᴇsᴛ', url=f"{message.link}"),
                        InlineKeyboardButton('Sʜᴏᴡ Oᴘᴛɪᴏɴs', callback_data=f'show_option#{reporter}')
                      ]]
                    reported_post = await bot.send_message(chat_id=admin, text=f"<b>📝 Rᴇǫᴜᴇsᴛ : <u>{content}</u>\n\n📚 Rᴇᴘᴏʀᴛᴇᴅ Bʏ : {mention}\n📖 Rᴇᴘᴏʀᴛᴇʀ Iᴅ : {reporter}\n\n</b>", reply_markup=InlineKeyboardMarkup(btn))
                    success = True
            else:
                if len(content) < 3:
                    await message.reply_text("<b>Yᴏᴜ ᴍᴜsᴛ ᴛʏᴘᴇ ᴀʙᴏᴜᴛ ʏᴏᴜʀ Rᴇǫᴜᴇsᴛ [ᴍɪɴɪᴍᴜᴍ 3 Cʜᴀʀᴀᴄᴛᴇʀs]. Rᴇǫᴜᴇsᴛs ᴄᴀɴ'ᴛ ʙᴇ ᴇᴍᴘᴛʏ.</b>")
            if len(content) < 3:
                success = False
        except Exception as e:
            await message.reply_text(f"Error: {e}")
            pass
    else:
        success = False
    if success:
        '''if isinstance(REQST_CHANNEL, (int, str)):
            channels = [REQST_CHANNEL]
        elif isinstance(REQST_CHANNEL, list):
            channels = REQST_CHANNEL
        for channel in channels:
            chat = await bot.get_chat(channel)
        #chat = int(chat)'''
        link = await bot.create_chat_invite_link(int(REQST_CHANNEL))
        btn = [[
                InlineKeyboardButton('Jᴏɪɴ Cʜᴀɴɴᴇʟ', url=link.invite_link),
                InlineKeyboardButton('Pɪᴇᴅ Rᴇǫᴜᴇsᴛ', url=f"{reported_post.link}")
              ]]
        await message.reply_text("<b>Yᴏᴜʀ Rᴇǫᴜᴇsᴛ Hᴀs Bᴇᴇɴ Aᴅᴅᴇᴅ! Pʟᴇᴀsᴇ Wᴀɪᴛ Fᴏʀ Sᴏᴍᴇ Tɪᴍᴇ.\n\nJᴏɪɴ Cʜᴀɴɴᴇʟ Fɪʀsᴛ & Pɪᴇᴅ Rᴇǫᴜᴇsᴛ.</b>", reply_markup=InlineKeyboardMarkup(btn))
    
@Client.on_message(filters.command("send") & filters.user(ADMINS))
async def send_msg(bot, message):
    if message.reply_to_message:
        target_id = message.text.split(" ", 1)[1]
        out = "Users Saved In DB Are:\n\n"
        success = False
        try:
            user = await bot.get_users(target_id)
            users = await db.get_all_users()
            async for usr in users:
                out += f"{usr['id']}"
                out += '\n'
            if str(user.id) in str(out):
                await message.reply_to_message.copy(int(user.id))
                success = True
            else:
                success = False
            if success:
                await message.reply_text(f"<b>Yᴏᴜʀ Mᴇssᴀɢᴇ Hᴀs Bᴇᴇɴ Sᴜᴄᴄᴇssғᴜʟʟʏ Sᴇɴᴛ Tᴏ {user.mention}.</b>")
            else:
                await message.reply_text("<b>Tʜɪs Usᴇʀ Dɪᴅɴ'ᴛ Sᴛᴀʀᴛᴇᴅ Tʜɪs Bᴏᴛ Yᴇᴛ !</b>")
        except Exception as e:
            await message.reply_text(f"<b>Error: {e}</b>")
    else:
        await message.reply_text("<b>Usᴇ Tʜɪs Cᴏᴍᴍᴀɴᴅ As A Rᴇᴘʟʏ Tᴏ Aɴʏ Mᴇssᴀɢᴇ Usɪɴɢ Tʜᴇ Tᴀʀɢᴇᴛ Cʜᴀᴛ. Fᴏʀ Ex: /send Usᴇʀɪᴅ</b>")

@Client.on_message(filters.command("deletefiles") & filters.user(ADMINS))
async def deletemultiplefiles(bot, message):
    chat_type = message.chat.type
    if chat_type != enums.ChatType.PRIVATE:
        return await message.reply_text(f"<b>Hey {message.from_user.mention}, This command won't work in groups. It only works on my PM !</b>")
    else:
        pass
    try:
        keyword = message.text.split(" ", 1)[1]
    except:
        return await message.reply_text(f"<b>Hey {message.from_user.mention}, Give me a keyword along with the command to delete files.</b>")
    k = await bot.send_message(chat_id=message.chat.id, text=f"<b>Fetching Files for your query {keyword} on DB... Please wait...</b>")
    files, total = await get_bad_files(keyword)
    total = len(files)
    if total == 0:
        await k.edit_text(f"<b>No files found for your query {keyword} !</b>")
        await asyncio.sleep(DELETE_TIME)
        await k.delete()
        return
    await k.delete()
    if total == 0:
        return await message.reply_text(f"<b>Hey {message.from_user.mention}, No files found for your query {keyword}.</b>")
        
    btn = [[
       InlineKeyboardButton("⚠️ Yes, Continue ! ⚠️", callback_data=f"killfilesdq#{keyword}")
       ],[
       InlineKeyboardButton("❌ No, Abort operation ! ❌", callback_data="close_data")
    ]]
    await message.reply_text(
        text=f"<b>Found {total} files for your query {keyword} !\n\nDo you want to delete?</b>",
        reply_markup=InlineKeyboardMarkup(btn),
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_callback_query(filters.regex("topsearch"))
async def topsearch_callback(client, callback_query):
    def is_alphanumeric(string):
        return bool(re.match('^[a-zA-Z0-9 ]*$', string))
    
    limit = 20  
    top_messages = await mdb.get_top_messages(limit)
    seen_messages = set()
    truncated_messages = []
    for msg in top_messages:
        msg_lower = msg.lower()
        if msg_lower not in seen_messages and is_alphanumeric(msg):
            seen_messages.add(msg_lower)
            if len(msg) > 35:
                truncated_messages.append(msg[:32] + "...")
            else:
                truncated_messages.append(msg)
    keyboard = [truncated_messages[i:i+2] for i in range(0, len(truncated_messages), 2)]
    reply_markup = ReplyKeyboardMarkup(
        keyboard, 
        one_time_keyboard=True, 
        resize_keyboard=True, 
        placeholder="Most searches of the day"
    )
    await callback_query.message.reply_text(
        "<b>Tᴏᴘ Sᴇᴀʀᴄʜᴇs Oғ Tʜᴇ Dᴀʏ 👇</b>",
        reply_markup=reply_markup
    )
    await callback_query.answer()

@Client.on_message(filters.command('top_search'))
async def top(_, message):
    def is_alphanumeric(string):
        return bool(re.match('^[a-zA-Z0-9 ]*$', string))
    try:
        limit = int(message.command[1])
    except (IndexError, ValueError):
        limit = 20
    top_messages = await mdb.get_top_messages(limit)
    seen_messages = set()
    truncated_messages = []
    for msg in top_messages:
        msg_lower = msg.lower()
        if msg_lower not in seen_messages and is_alphanumeric(msg):
            seen_messages.add(msg_lower)
            if len(msg) > 35:
                truncated_messages.append(msg[:32] + "...")
            else:
                truncated_messages.append(msg)
    keyboard = [truncated_messages[i:i+2] for i in range(0, len(truncated_messages), 2)]
    reply_markup = ReplyKeyboardMarkup(
        keyboard, 
        one_time_keyboard=True, 
        resize_keyboard=True, 
        placeholder="Most searches of the day"
    )
    await message.reply_text(
        "<b>Tᴏᴘ Sᴇᴀʀᴄʜᴇs Oғ Tʜᴇ Dᴀʏ 👇</b>",
        reply_markup=reply_markup
    )

@Client.on_message(filters.command('trendlist'))
async def trendlist(client, message):
    def is_alphanumeric(string):
        return bool(re.match('^[a-zA-Z0-9 ]*$', string))
    limit = 31
    if len(message.command) > 1:
        try:
            limit = int(message.command[1])
        except ValueError:
            await message.reply_text(
                "Invalid number format.\nPlease provide a valid number after the /trendlist command."
            )
            return 
    try:
        top_messages = await mdb.get_top_messages(limit)
    except Exception as e:
        await message.reply_text(f"Error retrieving messages: {str(e)}")
        return  

    if not top_messages:
        await message.reply_text("No top messages found.")
        return 
    seen_messages = set()
    truncated_messages = []

    for msg in top_messages:
        msg_lower = msg.lower()
        if msg_lower not in seen_messages and is_alphanumeric(msg):
            seen_messages.add(msg_lower)
            truncated_messages.append(msg[:32] + '...' if len(msg) > 35 else msg)

    if not truncated_messages:
        await message.reply_text("No valid top messages found.")
        return  
    formatted_list = "\n".join([f"{i+1}. <b>{msg}</b>" for i, msg in enumerate(truncated_messages)])
    additional_message = (
        "⚡️ 𝐍𝐨𝐭𝐞 𝐓𝐡𝐚𝐭 𝐓𝐡𝐞𝐬𝐞 𝐓𝐨𝐩 𝐒𝐞𝐚𝐫𝐜𝐡𝐞𝐬 𝐚𝐫𝐞 𝐅𝐫𝐨𝐦 𝐓𝐡𝐞 𝐋𝐚𝐬𝐭 𝟏𝟓 𝐃𝐚𝐲𝐬, "
        "𝐖𝐡𝐢𝐜𝐡 𝐚𝐫𝐞 𝐔𝐩𝐝𝐚𝐭𝐞𝐝 𝐃𝐚𝐢𝐥𝐲 𝐅𝐫𝐨𝐦 𝐍𝐨𝐰 𝐨𝐧𝐰𝐚𝐫𝐝𝐬. "
        "𝐒𝐨 𝐏𝐥𝐞𝐚𝐬𝐞 𝐕𝐢𝐬𝐢𝐭 𝐓𝐡𝐢𝐬 𝐒𝐞𝐜𝐭𝐢𝐨𝐧 𝐃𝐚𝐢𝐥𝐲 𝐅𝐨𝐫 𝐋𝐚𝐭𝐞𝐬𝐭 𝐔𝐩𝐝𝐚𝐭𝐞𝐝 𝐓𝐫𝐞𝐧𝐝𝐬 𝐨𝐟 𝐓𝐡𝐞 𝐃𝐚𝐲."
    )
    formatted_list += f"\n\n{additional_message}"
    reply_text = f"<b>Top {len(truncated_messages)} Tʀᴀɴᴅɪɴɢ ᴏғ ᴛʜᴇ Dᴀʏ 👇:</b>\n\n{formatted_list}"
    await message.reply_text(reply_text)

@Client.on_message(filters.private & filters.command("pm_search") & filters.user(ADMINS))
async def set_pm_search(client, message):
    bot_id = client.me.id
    try:
        option = message.text.split(" ", 1)[1].strip().lower()
        enable_status = option in ['on', 'true']
    except (IndexError, ValueError):
        await message.reply_text("<b>🔻 Invalid option. Please send 'on' or 'off' after the command..</b>")
        return
    try:
        await db.update_pm_search_status(bot_id, enable_status)
        response_text = (
            "<b> ᴘᴍ sᴇᴀʀᴄʜ ᴇɴᴀʙʟᴇᴅ ✅</b>" if enable_status 
            else "<b> ᴘᴍ sᴇᴀʀᴄʜ ᴅɪsᴀʙʟᴇᴅ ❌</b>"
        )
        await message.reply_text(response_text)
    except Exception as e:
        logger.error(f"Error in set_pm_search: {e}")
        await message.reply_text(f"<b>❌ An error occurred: {e}</b>")

@Client.on_message(filters.private & filters.command("movie_update") & filters.user(ADMINS))
async def set_movie_update_notification(client, message):
    bot_id = client.me.id
    try:
        option = message.text.split(" ", 1)[1].strip().lower()
        enable_status = option in ['on', 'true']
    except (IndexError, ValueError):
        await message.reply_text("<b>🔻 Invalid option. Please send 'on' or 'off' after the command.</b>")
        return
    try:
        await db.update_movie_update_status(bot_id, enable_status)
        response_text = (
            "<b>ᴍᴏᴠɪᴇ ᴜᴘᴅᴀᴛᴇ ɴᴏᴛɪғɪᴄᴀᴛɪᴏɴ ᴇɴᴀʙʟᴇᴅ ✅</b>" if enable_status 
            else "<b>ᴍᴏᴠɪᴇ ᴜᴘᴅᴀᴛᴇ ɴᴏᴛɪғɪᴄᴀᴛɪᴏɴ ᴅɪsᴀʙʟᴇᴅ ❌</b>"
        )
        await message.reply_text(response_text)
    except Exception as e:
        logger.error(f"Error in set_movie_update_notification: {e}")
        await message.reply_text(f"<b>❌ An error occurred: {e}</b>")

@Client.on_message(filters.command("restart") & filters.user(ADMINS))
async def stop_button(bot, message):
    msg = await bot.send_message(text="<b><i>Bᴏᴛ ɪs Rᴇsᴛᴀʀᴛɪɴɢ</i></b>", chat_id=message.chat.id)       
    await asyncio.sleep(3)
    await msg.edit("<b><i><u>Bᴏᴛ ɪs Rᴇsᴛᴀʀᴛᴇᴅ</u> ✅</i></b>")
    os.execl(sys.executable, sys.executable, *sys.argv)

@Client.on_message(filters.command("del_msg") & filters.user(ADMINS))
async def del_msg(client, message):
    confirm_markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("Yes", callback_data="confirm_del_yes"),
        InlineKeyboardButton("No", callback_data="confirm_del_no")
    ]])
    sent_message = await message.reply_text(
        "⚠️ Aʀᴇ Yᴏᴜ Sᴜʀᴇ Yᴏᴜ Wᴀɴᴛ Tᴏ Cʟᴇᴀʀ Tʜᴇ Uᴘᴅᴀᴛᴇs Cʜᴀɴɴᴇʟ Fɪsᴛ ?\n\n Dᴏ Yᴏᴜ Sᴛɪʟʟ Wᴀɴᴛ Tᴏ Cᴏɴᴛɪɴᴜᴇ ?",
        reply_markup=confirm_markup
    )
    await asyncio.sleep(60)
    try:
        await sent_message.delete()
    except Exception as e:
        print(f"Error deleting the message: {e}")

@Client.on_callback_query(filters.regex('^confirm_del_'))
async def confirmation_handler(client, callback_query):
    action = callback_query.data.split("_")[-1] 
    if action == "yes":
        await db.delete_all_msg()  
        await callback_query.message.edit_text('🧹 Uᴘᴅᴀᴛᴇs Cʜᴀɴɴᴇʟ Fɪsᴛ Hᴀs Bᴇᴇɴ Cʟᴇᴀʀᴇᴅ Sᴜᴄᴄᴇssғᴜʟʟʏ ✅')
    elif action == "no":
        await callback_query.message.delete()  
    await callback_query.answer()

@Client.on_message(filters.command('set_caption'))
async def save_caption(client, message):
    grp_id = message.chat.id
    title = message.chat.title
    invite_link = await client.export_chat_invite_link(grp_id)
    if not await is_check_admin(client, grp_id, message.from_user.id):
        return await message.reply_text(script.NT_ADMIN_ALRT_TXT)
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return await message.reply_text("<b>Usᴇ Tʜɪs Cᴏᴍᴍᴀɴᴅ Iɴ Gʀᴏᴜᴘ...</b>")
    try:
        caption = message.text.split(" ", 1)[1]
    except:
        return await message.reply_text("<code>Gɪᴠᴇ Mᴇ A Cᴀᴘᴛɪᴏɴ Aʟᴏɴɢ Wɪᴛʜ Iᴛ.\n\nExᴀᴍᴘʟᴇ -\n\nFᴏʀ Fɪʟᴇ Nᴀᴍᴇ Usᴇ <code>{file_name}</code>\nFᴏʀ Fɪʟᴇ Sɪᴢᴇ Usᴇ <code>{file_size}</code>\n\n<code>/set_caption {file_name}</code></code>")
    await save_group_settings(grp_id, 'caption', caption)
    await message.reply_text(f"Sᴜᴄᴄᴇssғᴜʟʟʏ Cʜᴀɴɢᴇᴅ Cᴀᴘᴛɪᴏɴ Fᴏʀ {title}\n\nCᴀᴘᴛɪᴏɴ - {caption}", disable_web_page_preview=True)
    await client.send_message(LOG_API_CHANNEL, f"#Set_Caption\n\nGʀᴏᴜᴘ Nᴀᴍᴇ : {title}\n\nGʀᴏᴜᴘ Iᴅ: {grp_id}\nIɴᴠɪᴛᴇ Lɪɴᴋ : {invite_link}\n\nUᴘᴅᴀᴛᴇᴅ Bʏ : {message.from_user.username}")


@Client.on_message(filters.command(["set_tutorial", "set_tutorial_2", "set_tutorial_3"]))
async def set_tutorial(client, message: Message):
    grp_id = message.chat.id
    title = message.chat.title
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return await message.reply_text(
            f"<b>Usᴇ Tʜɪs Cᴏᴍᴍᴀɴᴅ Iɴ Gʀᴏᴜᴘ...\n\nGroup Name: {title}\nGroup ID: {grp_id}</b>"
        )
    if not await is_check_admin(client, grp_id, message.from_user.id):
        return await message.reply_text(script.NT_ADMIN_ALRT_TXT)

    try:
        tutorial_link = message.text.split(" ", 1)[1]
    except IndexError:
        return await message.reply_text(
            f"<b>Cᴏᴍᴍᴀɴᴅ Iɴᴄᴏᴍᴘʟᴇᴛᴇ !!\n\nUsᴇ Lɪᴋᴇ Tʜɪs -</b>\n\n"
            f"<code>/{message.command[0]} https://t.me/WOLVERIN_P</code>"
        )
    if message.command[0] == "set_tutorial":
        tutorial_key = "tutorial"
    else:
        tutorial_key = f"tutorial_{message.command[0].split('_', 2)[2]}"

    await save_group_settings(grp_id, tutorial_key, tutorial_link)
    invite_link = await client.export_chat_invite_link(grp_id)
    await message.reply_text(
        f"<b>Sᴜᴄᴄᴇssғᴜʟʟʏ Cʜᴀɴɢᴇᴅ {tutorial_key.replace('_', ' ').title()} Fᴏʀ {title}</b>\n\n"
        f"Lɪɴᴋ - {tutorial_link}",
        disable_web_page_preview=True
    )
    await client.send_message(
        LOG_API_CHANNEL,
        f"#Set_{tutorial_key.title()}_Video\n\n"
        f"Gʀᴏᴜᴘ Nᴀᴍᴇ : {title}\n"
        f"Gʀᴏᴜᴘ Iᴅ : {grp_id}\n"
        f"Iɴᴠɪᴛᴇ Lɪɴᴋ : {invite_link}\n"
        f"Uᴘᴅᴀᴛᴇᴅ Bʏ : {message.from_user.mention()}"
    )


async def handle_shortner_command(c, m, shortner_key, api_key, log_prefix, fallback_url, fallback_api):
    grp_id = m.chat.id
    if not await is_check_admin(c, grp_id, m.from_user.id):
        return await m.reply_text(script.NT_ADMIN_ALRT_TXT)
    if len(m.command) != 3:
        return await m.reply(
            f"<b>Usᴇ Tʜɪs Cᴏᴍᴍᴀɴᴅ Lɪᴋᴇ -\n\n`/{m.command[0]} omegalinks.in your_api_key_here`</b>"
        )
    sts = await m.reply("<b>♻️ Cʜᴇᴄᴋɪɴɢ...</b>")
    await asyncio.sleep(1.2)
    await sts.delete()
    if m.chat.type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return await m.reply_text("<b>Usᴇ Tʜɪs Cᴏᴍᴍᴀɴᴅ Iɴ Gʀᴏᴜᴘ...</b>")
    try:
        URL = m.command[1]
        API = m.command[2]
        await save_group_settings(grp_id, shortner_key, URL)
        await save_group_settings(grp_id, api_key, API)
        await m.reply_text(f"<b><u>✅ Sʜᴏʀᴛɴᴇʀ Aᴅᴅᴇᴅ</u>\n\nSɪᴛᴇ - `{URL}`\nAᴘɪ - `{API}`</b>")
        user_id = m.from_user.id
        user_info = f"@{m.from_user.username}" if m.from_user.username else f"{m.from_user.mention}"
        link = (await c.get_chat(m.chat.id)).invite_link
        grp_link = f"[{m.chat.title}]({link})"
        log_message = (
            f"#{log_prefix}\n\nNᴀᴍᴇ - {user_info}\n\nIᴅ - `{user_id}`"
            f"\n\nSɪᴛᴇ - {URL}\n\nAᴘɪ - `{API}`"
            f"\n\nGʀᴏᴜᴘ - {grp_link}\nGʀᴏᴜᴘ Iᴅ - `{grp_id}`"
        )
        await c.send_message(LOG_API_CHANNEL, log_message, disable_web_page_preview=True)
    except Exception as e:
        await save_group_settings(grp_id, shortner_key, fallback_url)
        await save_group_settings(grp_id, api_key, fallback_api)
        await m.reply_text(
            f"<b><u>💢 Eʀʀᴏʀ Oᴄᴄᴜʀᴇᴅ!</u>\n\n"
            f"Dᴇғᴀᴜʟᴛ Sʜᴏʀᴛɴᴇʀ Aᴘᴘʟɪᴇᴅ\n"
            f"Iғ Yᴏᴜ Wᴀɴᴛ Tᴏ Cʜᴀɴɢᴇ Tʀʏ A Vᴀʟɪᴅ Sɪᴛᴇ Aɴᴅ Aᴘɪ Kᴇʏ.\n\n"
            f"Lɪᴋᴇ:\n\n`/{m.command[0]} mdiskshortner.link your_api_key_here`\n\n"
            f"🔴 Eʀʀᴏʀ - <code>{e}</code></b>"
        )

@Client.on_message(filters.command('set_shortner'))
async def set_shortner(c, m):
    await handle_shortner_command(c, m, 'shortner', 'api', 'New_Shortner_Set_For_1st_Verify', SHORTENER_WEBSITE, SHORTENER_API)

@Client.on_message(filters.command('set_shortner_2'))
async def set_shortner_2(c, m):
    await handle_shortner_command(c, m, 'shortner_two', 'api_two', 'New_Shortner_Set_For_2nd_Verify', SHORTENER_WEBSITE2, SHORTENER_API2)

@Client.on_message(filters.command('set_shortner_3'))
async def set_shortner_3(c, m):
    await handle_shortner_command(c, m, 'shortner_three', 'api_three', 'New_Shortner_Set_For_3rd_Verify', SHORTENER_WEBSITE3, SHORTENER_API3)

@Client.on_message(filters.command('set_log_channel'))
async def set_log(client, message):
    grp_id = message.chat.id
    title = message.chat.title
    if not await is_check_admin(client, grp_id, message.from_user.id):
        return await message.reply_text(script.NT_ADMIN_ALRT_TXT)
    if len(message.text.split()) == 1:
        await message.reply("<b>Usᴇ Tʜɪs Cᴏᴍᴍᴀɴᴅ Lɪᴋᴇ Tʜɪs - \n\n`/set_log_channel -100******`</b>")
        return
    sts = await message.reply("<b>♻️ Cʜᴇᴄᴋɪɴɢ...</b>")
    await asyncio.sleep(1.2)
    await sts.delete()
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return await message.reply_text("<b>Usᴇ Tʜɪs Cᴏᴍᴍᴀɴᴅ Iɴ Gʀᴏᴜᴘ...</b>")
    try:
        log = int(message.text.split(" ", 1)[1])
    except IndexError:
        return await message.reply_text("<b><u>Iɴᴠᴀʟɪᴅ Fᴏʀᴍᴀᴛ!!</u>\n\nUsᴇ Lɪᴋᴇ Tʜɪs - `/set_log_channel -100xxxxxxxx`</b>")
    except ValueError:
        return await message.reply_text('<b>Mᴀᴋᴇ Sᴜʀᴇ Iᴅ Is Iɴᴛᴇɢᴇʀ...</b>')
    try:
        t = await client.send_message(chat_id=log, text="<b>Hᴇʏ Wʜᴀᴛ's Uᴘ!!</b>")
        await asyncio.sleep(3)
        await t.delete()
    except Exception as e:
        return await message.reply_text(f'<b><u>😐 Mᴀᴋᴇ Sᴜʀᴇ Tʜɪs Bᴏᴛ Is Aᴅᴍɪɴ Iɴ Tʜᴀᴛ Cʜᴀɴɴᴇʟ...</u>\n\n🔴 Eʀʀᴏʀ - <code>{e}</code></b>')
    await save_group_settings(grp_id, 'log', log)
    await message.reply_text(f"<b>✅ Sᴜᴄᴄᴇssғᴜʟʟʏ Sᴇᴛ Yᴏᴜʀ Lᴏɢ Cʜᴀɴɴᴇʟ Fᴏʀ {title}\n\nIᴅ - `{log}`</b>", disable_web_page_preview=True)
    user_id = message.from_user.id
    user_info = f"@{message.from_user.username}" if message.from_user.username else f"{message.from_user.mention}"
    link = (await client.get_chat(message.chat.id)).invite_link
    grp_link = f"[{message.chat.title}]({link})"
    log_message = f"#New_Log_Channel_Set\n\nNᴀᴍᴇ - {user_info}\n\nIᴅ - `{user_id}`\n\nLᴏɢ Cʜᴀɴɴᴇʟ Iᴅ - `{log}`\nGʀᴏᴜᴘ Lɪɴᴋ - `{grp_link}`\n\nGʀᴏᴜᴘ Iᴅ : `{grp_id}`"
    await client.send_message(LOG_API_CHANNEL, log_message, disable_web_page_preview=True) 


@Client.on_message(filters.command('set_time'))
async def set_time(client, message):
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return await message.reply_text("<b>Usᴇ Tʜɪs Cᴏᴍᴍᴀɴᴅ Iɴ Gʀᴏᴜᴘ...</b>")       
    grp_id = message.chat.id
    title = message.chat.title
    invite_link = await client.export_chat_invite_link(grp_id)
    if not await is_check_admin(client, grp_id, message.from_user.id):
        return await message.reply_text(script.NT_ADMIN_ALRT_TXT)
    try:
        time = int(message.text.split(" ", 1)[1])
    except:
        return await message.reply_text("<b>Cᴏᴍᴍᴀɴᴅ Iɴᴄᴏᴍᴘʟᴇᴛᴇ\n\nUsᴇ Tʜɪs Cᴏᴍᴍᴀɴᴅ Lɪᴋᴇ Tʜɪs - <code>/set_time 600</code> [ Tɪᴍᴇ Mᴜsᴛ Bᴇ Iɴ Sᴇᴄᴏɴᴅs ]</b>")   
    await save_group_settings(grp_id, 'verify_time', time)
    await message.reply_text(f"<b>✅ Sᴜᴄᴄᴇssғᴜʟʟʏ Sᴇᴛ 2ɴᴅ Vᴇʀɪғʏ Tɪᴍᴇ Fᴏʀ {title}\n\nTɪᴍᴇ - <code>{time}</code></b>")
    await client.send_message(LOG_API_CHANNEL, f"#Set_2nd_Verify_Time\n\nGʀᴏᴜᴘ Nᴀᴍᴇ : {title}\n\nGʀᴏᴜᴘ Iᴅ : {grp_id}\n\nIɴᴠɪᴛᴇ Lɪɴᴋ : {invite_link}\n\nUᴘᴅᴀᴛᴇᴅ Bʏ : {message.from_user.username}")

@Client.on_message(filters.command('set_time_2'))
async def set_time_2(client, message):
    chat_type = message.chat.type
    if chat_type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return await message.reply_text("<b>Usᴇ Tʜɪs Cᴏᴍᴍᴀɴᴅ Iɴ Gʀᴏᴜᴘ...</b>")       
    grp_id = message.chat.id
    title = message.chat.title
    invite_link = await client.export_chat_invite_link(grp_id)
    if not await is_check_admin(client, grp_id, message.from_user.id):
        return await message.reply_text(script.NT_ADMIN_ALRT_TXT)
    try:
        time = int(message.text.split(" ", 1)[1])
    except:
        return await message.reply_text("<b>Cᴏᴍᴍᴀɴᴅ Iɴᴄᴏᴍᴘʟᴇᴛᴇ\n\nUsᴇ Tʜɪs Cᴏᴍᴍᴀɴᴅ Lɪᴋᴇ Tʜɪs - <code>/set_time 3600</code> [ Tɪᴍᴇ Mᴜsᴛ Bᴇ Iɴ Sᴇᴄᴏɴᴅs ]</b>")   
    await save_group_settings(grp_id, 'third_verify_time', time)
    await message.reply_text(f"<b>✅ Sᴜᴄᴄᴇssғᴜʟʟʏ Sᴇᴛ 3ʀᴅ Vᴇʀɪғʏ Tɪᴍᴇ Fᴏʀ {title}\n\nTɪᴍᴇ - <code>{time}</code></b>")
    await client.send_message(LOG_API_CHANNEL, f"#Set_3rd_Verify_Time\n\nGʀᴏᴜᴘ Nᴀᴍᴇ : {title}\n\nGʀᴏᴜᴘ Iᴅ : {grp_id}\n\nIɴᴠɪᴛᴇ Lɪɴᴋ : {invite_link}\n\nUᴘᴅᴀᴛᴇᴅ Bʏ : {message.from_user.username}")


@Client.on_message(filters.command('details'))
async def all_settings(client, message):
    if message.chat.type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return await message.reply_text("<b>Usᴇ Tʜɪs Cᴏᴍᴍᴀɴᴅ Iɴ Gʀᴏᴜᴘ...</b>")
    grp_id = message.chat.id
    title = message.chat.title
    if not await is_check_admin(client, grp_id, message.from_user.id):
        return await message.reply_text(script.NT_ADMIN_ALRT_TXT)
    try:
        settings = await get_settings(grp_id)
    except Exception as e:
        return await message.reply_text(f"<b>⚠️ Eʀʀᴏʀ Fᴇᴛᴄʜɪɴɢ Sᴇᴛᴛɪɴɢs:</b>\n<code>{e}</code>")
    text = generate_settings_text(settings, title)
    btn = [
        [InlineKeyboardButton("♻️ Rᴇsᴇᴛ Sᴇᴛᴛɪɴɢs", callback_data=f"reset_group_{grp_id}")],
        [InlineKeyboardButton("🚫 Cʟᴏsᴇ", callback_data="close_data")]
    ]
    dlt = await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
    await asyncio.sleep(300)
    await dlt.delete()

@Client.on_callback_query(filters.regex(r"^reset_group_(\-\d+)$"))
async def reset_group_callback(client, callback_query):
    grp_id = int(callback_query.matches[0].group(1))
    user_id = callback_query.from_user.id
    if not await is_check_admin(client, grp_id, user_id):
        return await callback_query.answer(script.NT_ADMIN_ALRT_TXT, show_alert=True)
    await callback_query.answer("♻️ Rᴇsᴇᴛᴛɪɴɢ Sᴇᴛᴛɪɴɢs...")
    defaults = {
        'shortner': SHORTENER_WEBSITE,
        'api': SHORTENER_API,
        'shortner_two': SHORTENER_WEBSITE2,
        'api_two': SHORTENER_API2,
        'shortner_three': SHORTENER_WEBSITE3,
        'api_three': SHORTENER_API3,
        'verify_time': TWO_VERIFY_GAP,
        'third_verify_time': THREE_VERIFY_GAP,
        'template': IMDB_TEMPLATE,
        'tutorial': TUTORIAL,
        'tutorial_2': TUTORIAL_2,
        'tutorial_3': TUTORIAL_3,
        'caption': CUSTOM_FILE_CAPTION,
        'log': LOG_CHANNEL,
        'is_verify': IS_VERIFY,
        'fsub': AUTH_CHANNELS
    }
    current = await get_settings(grp_id)
    if current == defaults:
        return await callback_query.answer("✅ Sᴇᴛᴛɪɴɢs Aʟʀᴇᴀᴅʏ Dᴇғᴀᴜʟᴛ.", show_alert=True)
    for key, value in defaults.items():
        await save_group_settings(grp_id, key, value)
    updated = await get_settings(grp_id)
    title = callback_query.message.chat.title
    text = generate_settings_text(updated, title, reset_done=True)
    buttons = [
        [InlineKeyboardButton("♻️ Rᴇsᴇᴛ Sᴇᴛᴛɪɴɢs", callback_data=f"reset_group_{grp_id}")],
        [InlineKeyboardButton("🚫 Cʟᴏsᴇ", callback_data="close_data")]
    ]
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)

@Client.on_message(filters.command("verify") & filters.user(ADMINS))
async def verify(bot, message):
    try:
        chat_type = message.chat.type
        if chat_type == enums.ChatType.PRIVATE:
            return await message.reply_text("Tʜɪs Cᴏᴍᴍᴀɴᴅ Wᴏʀᴋs Oɴʟʏ Iɴ Gʀᴏᴜᴘs!")
        if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            grpid = message.chat.id
            title = message.chat.title
            command_text = message.text.split(' ')[1] if len(message.text.split(' ')) > 1 else None
            if command_text == "off":
                await save_group_settings(grpid, 'is_verify', False)
                return await message.reply_text("✅ Vᴇʀɪғʏ Sᴜᴄᴄᴇssғᴜʟʟʏ Dɪsᴀʙʟᴇᴅ.")
            elif command_text == "on":
                await save_group_settings(grpid, 'is_verify', True)
                return await message.reply_text("✅ Vᴇʀɪғʏ Sᴜᴄᴄᴇssғᴜʟʟʏ Eɴᴀʙʟᴇᴅ.")
            else:
                return await message.reply_text("Hɪ, Tᴏ Eɴᴀʙʟᴇ Vᴇʀɪғʏ, Usᴇ <code>/verify on</code> Aɴᴅ Tᴏ Dɪsᴀʙʟᴇ Vᴇʀɪғʏ, Usᴇ <code>/verify off</code>.")
    except Exception as e:
        print(f"Error: {e}")
        await message.reply_text(f"Error: {e}")

@Client.on_message(filters.command('set_fsub'))
async def set_fsub(client, message):
    try:
        userid = message.from_user.id if message.from_user else None
        if not userid:
            return await message.reply("<b>You are Anonymous admin you can't use this command !</b>")
        if message.chat.type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            return await message.reply_text("Tʜɪs Cᴏᴍᴍᴀɴᴅ Cᴀɴ Oɴʟʏ Bᴇ Usᴇᴅ Iɴ Gʀᴏᴜᴘs")
        grp_id = message.chat.id
        title = message.chat.title
        if not await is_check_admin(client, grp_id, userid):
            return await message.reply_text(script.NT_ADMIN_ALRT_TXT)
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply_text(
                "Cᴏᴍᴍᴀɴᴅ Iɴᴄᴏᴍᴘʟᴇᴛᴇ!\n\n"
                "Cᴀɴ Aᴅᴅ Mᴜʟᴛɪᴘʟᴇ Cʜᴀɴɴᴇʟs Sᴇᴘᴀʀᴀᴛᴇᴅ Bʏ Sᴘᴀᴄᴇs. Exᴀᴍᴘʟᴇ: /sᴇᴛ_ғsᴜʙ ɪᴅ1 ɪᴅ2 ɪᴅ3\n"
            )
        option = args[1].strip()
        try:
            fsub_ids = [int(x) for x in option.split()]
        except ValueError:
            return await message.reply_text('Mᴀᴋᴇ Sᴜʀᴇ Aʟʟ Iᴅs Aʀᴇ Iɴᴛᴇɢᴇʀs.')
        if len(fsub_ids) > 5:
            return await message.reply_text("Mᴀxɪᴍᴜᴍ 5 Cʜᴀɴɴᴇʟs Aʟʟᴏᴡᴇᴅ.")
        channels = "Cʜᴀɴɴᴇʟs:\n"
        channel_titles = []
        for id in fsub_ids:
            try:
                chat = await client.get_chat(id)
            except Exception as e:
                return await message.reply_text(
                    f"{id} Is Iɴᴠᴀʟɪᴅ!\nMᴀᴋᴇ Sᴜʀᴇ Tʜɪs Bᴏᴛ Is Aᴅᴍɪɴ Iɴ Tʜᴀᴛ Cʜᴀɴɴᴇʟ.\n\nError - {e}"
                )
            if chat.type != enums.ChatType.CHANNEL:
                return await message.reply_text(f"{id} Is Nᴏᴛ A Cʜᴀɴɴᴇʟ.")
            channel_titles.append(f"{chat.title} (`{id}`)")
            channels += f'{chat.title}\n'
        await save_group_settings(grp_id, 'fsub', fsub_ids)
        await message.reply_text(f"Sᴜᴄᴄᴇssғᴜʟʟʏ Sᴇᴛ Fsᴜʙ Cʜᴀɴɴᴇʟ(s) Fᴏʀ {title} Tᴏ\n\n{channels}")
        mention = message.from_user.mention if message.from_user else "Unknown"
        await client.send_message(
            LOG_API_CHANNEL,
            f"#Fsub_Channel_set\n\n"
            f"Usᴇʀ - {mention} Sᴇᴛ Tʜᴇ Fᴏʀᴄᴇ Cʜᴀɴɴᴇʟ(s) Fᴏʀ {title}:\n\n"
            f"Fsᴜʙ Cʜᴀɴɴᴇʟ(s):\n" + '\n'.join(channel_titles)
        )
    except Exception as e:
        err_text = f"⚠️ Error in set_fSub :\n{e}"
        logger.error(err_text)
        await client.send_message(LOG_API_CHANNEL, err_text)

@Client.on_message(filters.private & filters.command("resetallgroup") & filters.user(ADMINS))
async def reset_all_settings(client, message):
    try:
        reset_count = await db.dreamx_reset_settings()
        await message.reply_text(
            f"<b>Sᴜᴄᴄᴇssғᴜʟʟʏ Dᴇʟᴇᴛᴇᴅ Sᴇᴛᴛɪɴɢs Fᴏʀ  <code>{reset_count}</code> Gʀᴏᴜᴘs. Dᴇғᴀᴜʟᴛ Vᴀʟᴜᴇs Wɪʟʟ Bᴇ Usᴇᴅ ✅</b>",
            quote=True
        )
    except Exception as e:
        print(f"[ERROR] reset_all_settings: {e}")
        await message.reply_text(
            "<b>🚫 An error occurred while resetting group settings.\nPlease try again later.</b>",
            quote=True
        )

@Client.on_message(filters.command("trial_reset"))
async def reset_trial(client, message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        await message.reply("Yᴏᴜ Dᴏɴ'ᴛ Hᴀᴠᴇ Aɴʏ Pᴇʀᴍɪssɪᴏɴ Tᴏ Usᴇ Tʜɪs Cᴏᴍᴍᴀɴᴅ.")
        return
    try:
        if len(message.command) > 1:
            target_user_id = int(message.command[1])
            updated_count = await db.reset_free_trial(target_user_id)
            message_text = f"Sᴜᴄᴄᴇssғᴜʟʟʏ Rᴇsᴇᴛ Fʀᴇᴇ Tʀɪᴀʟ Fᴏʀ Usᴇʀ {target_user_id}." if updated_count else f"Usᴇʀ {target_user_id} Nᴏᴛ Fᴏᴜɴᴅ Oʀ Dᴏɴ'ᴛ Hᴀᴠᴇ Aᴄᴛɪᴠᴇ Fʀᴇᴇ Tʀɪᴀʟ Yᴇᴛ."
        else:
            updated_count = await db.reset_free_trial()
            message_text = f"Sᴜᴄᴄᴇssғᴜʟʟʏ Rᴇsᴇᴛ Fʀᴇᴇ Tʀɪᴀʟ Fᴏʀ {updated_count} Usᴇʀs."
        await message.reply_text(message_text)
    except Exception as e:
        await message.reply_text(f"An error occurred: {e}")

#music download handle========================
# ✅ Sahi Code
@Client.on_message(filters.command("song") & filters.incoming)
async def song_download(client, message):
    """YouTube se MP3 song download karein"""
    if len(message.command) < 2:
        await message.reply_text(
            "🎵 **Kripya song ka naam likhein!**\n\n"
            "Usage: `/song song_name`\n"
            "Example: `/song Tum Hi Ho`"
        )
        return
    
    song_name = " ".join(message.command[1:])
    status_msg = await message.reply_text(f"🔍 `{song_name}` dhoond raha hoon...")
    
    try:
        import yt_dlp
        import os
        import glob
        
        os.makedirs("downloads", exist_ok=True)
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            'extractaudio': True,
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'default_search': 'ytsearch5',
            'cookiefile': 'cookies.txt',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{song_name}", download=True)
            
            if not info or 'entries' not in info:
                await status_msg.edit_text("❌ Koi song nahi mila!")
                return
            
            video = info['entries'][0]
            title = video.get('title', song_name)
            duration = video.get('duration', 0)
            uploader = video.get('uploader', 'Unknown')
            
            files = glob.glob("downloads/*.mp3")
            if not files:
                await status_msg.edit_text("❌ Download fail ho gaya!")
                return
            
            audio_file = files[0]
            duration_min = duration // 60
            duration_sec = duration % 60
            
            caption = f"""🎵 **{title}**

⏱️ Duration: `{duration_min}m {duration_sec}s`
👤 Uploader: `{uploader}`

🎶 **Enjoy the music!** 🎶
"""
            
            await status_msg.delete()
            
            await client.send_audio(
                chat_id=message.chat.id,
                audio=audio_file,
                caption=caption,
                title=title,
                performer=uploader,
                duration=duration,
                reply_to_message_id=message.id
            )
            
            try:
                os.remove(audio_file)
            except:
                pass
                
    except ImportError:
        await status_msg.edit_text(
            "❌ **yt-dlp install nahi hai!**\n\n"
            "Install karein: `pip install yt-dlp`"
        )
        return
        
    except Exception as e:
        error_msg = str(e)
        if "Sign in to confirm" in error_msg:
            await status_msg.edit_text(
                "❌ **YouTube Login Required!**\n\n"
                "Cookies file chahiye.\n"
                "1. Chrome extension 'Get cookies.txt LOCALLY' install karein\n"
                "2. YouTube pe login karein\n"
                "3. Export karein aur 'cookies.txt' file bot folder mein rakhein"
            )
        else:
            await status_msg.edit_text(f"❌ Error: `{error_msg[:200]}`")
        logging.error(f"Song download error: {e}")
        return
