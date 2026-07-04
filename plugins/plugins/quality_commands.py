# plugins/quality_commands.py
import re
import logging
from datetime import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from info import ADMINS, LOG_CHANNEL, MULTIPLE_DB
from database.ia_filterdb import Media, Media2
from plugins.quality_upgrade import (
    BAD_QUALITY_KEYWORDS,
    GOOD_QUALITY_KEYWORDS,
    is_bad_quality,
    is_good_quality,
    get_movie_base_name,
    find_and_delete_bad_quality_files,
    send_upgrade_notification
)

logger = logging.getLogger(__name__)

# ============================================
# 🗑️ CLEAN BAD - सभी बैड क्वालिटी फाइल्स डिलीट करें
# ============================================
@Client.on_message(filters.command("clean_bad") & filters.user(ADMINS))
async def clean_bad_quality(bot, message):
    """
    सभी बैड क्वालिटी फाइल्स मैन्युअली डिलीट करें
    Usage: /clean_bad
    """
    msg = await message.reply("🔍 Searching for bad quality files...")
    
    total_deleted = 0
    processed = 0
    
    try:
        # सभी बैड क्वालिटी फाइल्स ढूंढें
        bad_pattern = "|".join(BAD_QUALITY_KEYWORDS)
        bad_regex = re.compile(bad_pattern, re.IGNORECASE)
        
        query = {"file_name": {"$regex": bad_regex}}
        
        # PRIMARY DB
        cursor = Media.find(query)
        async for doc in cursor:
            processed += 1
            try:
                result = await Media.collection.delete_one({"_id": doc.file_id})
                if result.deleted_count:
                    total_deleted += 1
                    logger.info(f"🗑️ Deleted: {doc.file_name}")
            except Exception as e:
                logger.error(f"Failed to delete {doc.file_name}: {e}")
            
            # प्रोग्रेस अपडेट करें
            if processed % 50 == 0:
                await msg.edit(
                    f"🔄 Processing...\n"
                    f"🗑️ Deleted: {total_deleted}\n"
                    f"📊 Processed: {processed}"
                )
        
        # SECONDARY DB (अगर MULTIPLE_DB ऑन है)
        if MULTIPLE_DB:
            cursor2 = Media2.find(query)
            async for doc in cursor2:
                processed += 1
                try:
                    result = await Media2.collection.delete_one({"_id": doc.file_id})
                    if result.deleted_count:
                        total_deleted += 1
                        logger.info(f"🗑️ Deleted from DB2: {doc.file_name}")
                except Exception as e:
                    logger.error(f"Failed to delete from DB2 {doc.file_name}: {e}")
                
                if processed % 50 == 0:
                    await msg.edit(
                        f"🔄 Processing...\n"
                        f"🗑️ Deleted: {total_deleted}\n"
                        f"📊 Processed: {processed}"
                    )
        
        await msg.edit(
            f"✅ **Cleanup Complete!**\n\n"
            f"🗑️ Deleted: {total_deleted}\n"
            f"📊 Total Processed: {processed}"
        )
        
        # लॉग भेजें
        await bot.send_message(
            LOG_CHANNEL,
            f"🧹 **Manual Cleanup Completed**\n\n"
            f"🗑️ Deleted: {total_deleted}\n"
            f"👤 By: {message.from_user.mention}"
        )
        
    except Exception as e:
        await msg.edit(f"❌ Error: {e}")
        logger.error(f"Error in clean_bad_quality: {e}")

# ============================================
# 📊 CHECK QUALITY - किसी मूवी की क्वालिटी चेक करें
# ============================================
@Client.on_message(filters.command("check_quality") & filters.user(ADMINS))
async def check_quality(bot, message):
    """
    किसी मूवी की सभी क्वालिटीज चेक करें
    Usage: /check_quality Jawan 2023
    """
    if len(message.command) < 2:
        await message.reply(
            "Usage: `/check_quality Movie Name`\n\n"
            "Example: `/check_quality Jawan 2023`"
        )
        return
    
    movie_name = " ".join(message.command[1:])
    base_name = get_movie_base_name(movie_name)
    
    if not base_name:
        await message.reply("❌ Invalid movie name!")
        return
    
    msg = await message.reply(f"🔍 Searching for: {base_name}...")
    
    try:
        # Query बनाएं
        base_name_escaped = re.escape(base_name)
        search_pattern = re.compile(base_name_escaped, re.IGNORECASE)
        
        query = {"file_name": {"$regex": search_pattern}}
        
        bad_files = []
        good_files = []
        
        # PRIMARY DB
        cursor = Media.find(query)
        async for doc in cursor:
            if is_bad_quality(doc.file_name):
                bad_files.append(doc.file_name)
            elif is_good_quality(doc.file_name):
                good_files.append(doc.file_name)
        
        # SECONDARY DB
        if MULTIPLE_DB:
            cursor2 = Media2.find(query)
            async for doc in cursor2:
                if is_bad_quality(doc.file_name):
                    bad_files.append(doc.file_name)
                elif is_good_quality(doc.file_name):
                    good_files.append(doc.file_name)
        
        # रिप्लाई बनाएं
        response = f"📊 **Quality Check: {base_name}**\n\n"
        response += f"🔴 **Bad Quality (CAM/Dubbing):** {len(bad_files)} files\n"
        if bad_files:
            for f in bad_files[:10]:
                response += f"  • `{f[:60]}...`\n"
            if len(bad_files) > 10:
                response += f"  • ... and {len(bad_files) - 10} more\n"
        
        response += f"\n🟢 **Good Quality (WebDL/BluRay):** {len(good_files)} files\n"
        if good_files:
            for f in good_files[:10]:
                response += f"  • `{f[:60]}...`\n"
            if len(good_files) > 10:
                response += f"  • ... and {len(good_files) - 10} more\n"
        
        # बटन जोड़ें
        buttons = []
        if bad_files:
            buttons.append([
                InlineKeyboardButton(
                    "🗑️ Delete Bad Quality Files",
                    callback_data=f"delete_bad_{base_name[:50]}"
                )
            ])
        
        await msg.edit(
            response,
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        await msg.edit(f"❌ Error: {e}")
        logger.error(f"Error in check_quality: {e}")

# ============================================
# 🗑️ DELETE BAD QUALITY CALLBACK
# ============================================
@Client.on_callback_query(filters.regex(r"^delete_bad_"))
async def delete_bad_quality_callback(bot, query):
    """
    क्वालिटी चेक से सीधे बैड क्वालिटी फाइल्स डिलीट करें
    """
    user_id = query.from_user.id
    
    # चेक करें कि एडमिन है या नहीं
    if user_id not in ADMINS:
        await query.answer("❌ You're not authorized!", show_alert=True)
        return
    
    base_name = query.data.replace("delete_bad_", "")
    await query.answer(f"🔄 Deleting bad quality files for {base_name}...")
    
    await query.message.edit(f"🗑️ Deleting bad quality files for: {base_name}")
    
    try:
        # फाइल्स डिलीट करें
        result = await find_and_delete_bad_quality_files(bot, base_name, "")
        
        if result["deleted"] > 0:
            await query.message.edit(
                f"✅ **Deleted Successfully!**\n\n"
                f"📂 {base_name}\n"
                f"🗑️ Deleted: {result['deleted']} bad quality files"
            )
            
            # लॉग भेजें
            await send_upgrade_notification(
                bot,
                base_name,
                "Manual Delete",
                result["deleted"],
                result["files"]
            )
        else:
            await query.message.edit(
                f"ℹ️ No bad quality files found for: {base_name}"
            )
            
    except Exception as e:
        await query.message.edit(f"❌ Error: {e}")
        logger.error(f"Error in delete_bad_quality_callback: {e}")

# ============================================
# 📊 QUALITY STATS - पूरी स्टैट्स
# ============================================
@Client.on_message(filters.command("quality_stats") & filters.user(ADMINS))
async def quality_stats(bot, message):
    """
    पूरी क्वालिटी स्टैट्स दिखाएं
    Usage: /quality_stats
    """
    msg = await message.reply("📊 Generating quality stats...")
    
    try:
        total_files = 0
        bad_quality = 0
        good_quality = 0
        unknown = 0
        
        # PRIMARY DB
        async for doc in Media.find():
            total_files += 1
            if is_bad_quality(doc.file_name):
                bad_quality += 1
            elif is_good_quality(doc.file_name):
                good_quality += 1
            else:
                unknown += 1
        
        # SECONDARY DB
        if MULTIPLE_DB:
            async for doc in Media2.find():
                total_files += 1
                if is_bad_quality(doc.file_name):
                    bad_quality += 1
                elif is_good_quality(doc.file_name):
                    good_quality += 1
                else:
                    unknown += 1
        
        response = f"""
📊 **Quality Statistics**

📁 **Total Files:** {total_files}

🔴 **Bad Quality (CAM/Dubbing):** {bad_quality} 
🟢 **Good Quality (WebDL/BluRay):** {good_quality}
⚪ **Unknown:** {unknown}
"""
        
        await msg.edit(response)
        
    except Exception as e:
        await msg.edit(f"❌ Error: {e}")
        logger.error(f"Error in quality_stats: {e}")
