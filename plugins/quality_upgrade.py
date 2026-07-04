# plugins/quality_upgrade.py
import re
import logging
from datetime import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from info import CHANNELS, LOG_CHANNEL, ADMINS, MULTIPLE_DB
from database.ia_filterdb import Media, Media2, save_file, unpack_new_file_id
from utils import temp

logger = logging.getLogger(__name__)

# ============================================
# 🚫 BAD/POOR QUALITY KEYWORDS (जो डिलीट होंगी)
# ============================================
BAD_QUALITY_KEYWORDS = [
    # Camera/Print Sources
    'camrip', 'cam-rip', 'cam', 'hdcam', 'hdtc', 'tc', 'ts', 
    'telesync', 'hdts', 'hd-tc', 'cam-ts',
    # Screen Recordings
    'dvdscr', 'predvd',
    # Dubbing Sources
    'hall dubbing', 'theatre dubbing', 'cinema dubbing',
    'theatre', 'cinema', 'hall', 'print',
    # Other Bad Quality
    'hdprint', 'screen', 'recorded', 'capture',
    'tsrip', 'hdcamrip', 'camhd', 'ts-hd'
]

# ============================================
# ✅ GOOD QUALITY KEYWORDS (जो रिप्लेस करेंगी)
# ============================================
GOOD_QUALITY_KEYWORDS = [
    # Web Sources
    'webdl', 'web-dl', 'webrip', 'web-rip', 'web',
    # BluRay Sources
    'bluray', 'brrip', 'bdrip', 'blu-ray',
    # Premium Sources
    'hdr', 'dolby', 'atmos', 'truehd', 'dts-hd',
    'remux', 'uhd', 'hq', 'fhd'
]

# ============================================
# 🎯 QUALITY DETECTION
# ============================================
def is_bad_quality(file_name: str) -> bool:
    """Check if file is bad quality (CAM/Dubbing/Print)"""
    if not file_name:
        return False
    file_lower = file_name.lower()
    return any(keyword in file_lower for keyword in BAD_QUALITY_KEYWORDS)

def is_good_quality(file_name: str) -> bool:
    """Check if file is good quality (WebDL/WEBRip/BluRay)"""
    if not file_name:
        return False
    file_lower = file_name.lower()
    # अगर बैड क्वालिटी है तो गुड नहीं हो सकती
    if is_bad_quality(file_name):
        return False
    return any(keyword in file_lower for keyword in GOOD_QUALITY_KEYWORDS)

def get_movie_base_name(file_name: str) -> str:
    """
    मूवी का बेस नाम निकाले (साल के साथ)
    Example: "Jawan 2023 CamRip Hindi" -> "Jawan 2023"
    Example: "Animal 2023 WebDL" -> "Animal 2023"
    """
    if not file_name:
        return ""
    
    file_lower = file_name.lower()
    clean_name = file_lower
    
    # 1. सभी बैड क्वालिटी keywords हटाएं
    for keyword in BAD_QUALITY_KEYWORDS:
        clean_name = clean_name.replace(keyword, '')
    
    # 2. सभी गुड क्वालिटी keywords हटाएं
    for keyword in GOOD_QUALITY_KEYWORDS:
        clean_name = clean_name.replace(keyword, '')
    
    # 3. Language keywords हटाएं
    languages = ['hindi', 'english', 'tamil', 'telugu', 'malayalam', 
                 'kannada', 'marathi', 'punjabi', 'bengali', 'gujarati',
                 'urdu', 'dubbed', 'dual audio', 'multi audio']
    for lang in languages:
        clean_name = clean_name.replace(lang, '')
    
    # 4. Video codes हटाएं
    codes = ['x264', 'x265', 'hevc', 'avc', '10bit', '8bit']
    for code in codes:
        clean_name = clean_name.replace(code, '')
    
    # 5. Audio codes हटाएं (सिर्फ कोड, क्वालिटी नहीं)
    audio_codes = ['aac', 'mp3', 'flac', 'wav']
    for code in audio_codes:
        clean_name = clean_name.replace(code, '')
    
    # 6. Special characters हटाएं
    clean_name = re.sub(r'[^a-zA-Z0-9\s\(\)]', ' ', clean_name)
    
    # 7. Extra spaces हटाएं
    clean_name = re.sub(r'\s+', ' ', clean_name).strip()
    
    # 8. Year extract करें
    year_match = re.search(r'\b(19|20)\d{2}\b', clean_name)
    if year_match:
        year = year_match.group(0)
        # Year को हटाकर बाकी नाम रखें
        clean_name = clean_name.replace(year, '').strip()
        if clean_name:
            return f"{clean_name} {year}"
        else:
            return f"Movie {year}"
    
    # 9. अगर नाम बहुत छोटा है
    if len(clean_name) < 3:
        # फाइल नाम से पहला शब्द लें
        first_word = file_name.split()[0] if file_name.split() else "Movie"
        return first_word
    
    return clean_name.title()

# ============================================
# 🔍 FIND & DELETE BAD QUALITY FILES
# ============================================
async def find_and_delete_bad_quality_files(bot, base_name: str, new_file_id: str) -> dict:
    """
    बेस नाम से मैचिंग सभी बैड क्वालिटी फाइल्स ढूंढें और डिलीट करें
    Returns: डिलीट की गई फाइल्स की जानकारी
    """
    result = {
        "deleted": 0,
        "files": []
    }
    
    try:
        # MongoDB query बनाएं - बेस नाम से मैच करें
        base_name_escaped = re.escape(base_name)
        search_pattern = re.compile(base_name_escaped, re.IGNORECASE)
        
        # Bad quality keywords के लिए regex बनाएं
        bad_pattern = "|".join(BAD_QUALITY_KEYWORDS)
        bad_regex = re.compile(bad_pattern, re.IGNORECASE)
        
        filter_query = {
            "file_name": {"$regex": search_pattern},
            "file_name": {"$regex": bad_regex}
        }
        
        # PRIMARY DB से खोजें
        deleted_files = []
        
        cursor = Media.find(filter_query)
        async for doc in cursor:
            # नई फाइल को डिलीट न करें
            if doc.file_id == new_file_id:
                continue
            
            try:
                # फाइल डिलीट करें
                delete_result = await Media.collection.delete_one({"_id": doc.file_id})
                if delete_result.deleted_count:
                    result["deleted"] += 1
                    deleted_files.append(doc.file_name)
                    logger.info(f"🗑️ Deleted bad quality: {doc.file_name}")
            except Exception as e:
                logger.error(f"Error deleting {doc.file_name}: {e}")
        
        # SECONDARY DB से खोजें (अगर MULTIPLE_DB ऑन है)
        if MULTIPLE_DB:
            cursor2 = Media2.find(filter_query)
            async for doc in cursor2:
                if doc.file_id == new_file_id:
                    continue
                
                try:
                    delete_result = await Media2.collection.delete_one({"_id": doc.file_id})
                    if delete_result.deleted_count:
                        result["deleted"] += 1
                        deleted_files.append(doc.file_name)
                        logger.info(f"🗑️ Deleted bad quality from DB2: {doc.file_name}")
                except Exception as e:
                    logger.error(f"Error deleting from DB2 {doc.file_name}: {e}")
        
        result["files"] = deleted_files
        
    except Exception as e:
        logger.error(f"Error in find_and_delete_bad_quality_files: {e}")
    
    return result

# ============================================
# 📨 SEND UPGRADE NOTIFICATION
# ============================================
async def send_upgrade_notification(bot, base_name: str, new_file_name: str, deleted_count: int, deleted_files: list):
    """
    एडमिन और लॉग चैनल को अपग्रेड नोटिफिकेशन भेजें
    """
    try:
        # लॉग मैसेज बनाएं
        log_msg = f"""
<b>✅ QUALITY UPGRADE COMPLETED</b>

📂 <b>Movie:</b> <code>{base_name}</code>
🗑️ <b>Deleted:</b> <code>{deleted_count}</code> bad quality files

🆕 <b>New File:</b> <code>{new_file_name}</code>

📅 <b>Date:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>
"""
        
        if deleted_files:
            log_msg += f"\n<b>📋 Deleted Files:</b>\n"
            for f in deleted_files[:5]:  # सिर्फ 5 दिखाएं
                log_msg += f"  • <code>{f}</code>\n"
            if len(deleted_files) > 5:
                log_msg += f"  • ... and {len(deleted_files) - 5} more\n"
        
        # LOG_CHANNEL पर भेजें
        await bot.send_message(LOG_CHANNEL, log_msg, parse_mode=enums.ParseMode.HTML)
        
        # एडमिन्स को भी भेजें
        for admin_id in ADMINS:
            try:
                await bot.send_message(
                    admin_id,
                    f"✅ Quality Upgrade Alert!\n\n"
                    f"📂 {base_name}\n"
                    f"🗑️ {deleted_count} bad quality files deleted\n"
                    f"🆕 New: {new_file_name}",
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as e:
                logger.warning(f"Couldn't send notification to admin {admin_id}: {e}")
                
    except Exception as e:
        logger.error(f"Error sending notification: {e}")

# ============================================
# 🎯 MAIN HANDLER - जब नई फाइल आए
# ============================================
@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video | filters.audio))
async def quality_upgrade_handler(bot, message: Message):
    """
    जब CHANNELS में कोई नई फाइल आए तो यह हैंडलर रन होगा
    """
    try:
        # MEDIA OBJECT प्राप्त करें
        media = None
        for media_type in ["document", "video", "audio"]:
            if hasattr(message, media_type):
                media = getattr(message, media_type)
                if media:
                    break
        
        if not media:
            return
        
        # फाइल का नाम
        file_name = media.file_name or ""
        if not file_name:
            return
        
        # चेक करें कि नई फाइल गुड क्वालिटी है या नहीं
        if not is_good_quality(file_name):
            logger.info(f"⏭️ Skipping (not good quality): {file_name}")
            return
        
        # बेस नाम निकालें
        base_name = get_movie_base_name(file_name)
        if not base_name:
            logger.info(f"⏭️ Skipping (no base name): {file_name}")
            return
        
        logger.info(f"📥 New good quality file: {file_name}")
        logger.info(f"📂 Base name: {base_name}")
        
        # नई फाइल ID प्राप्त करें
        new_file_id, _ = unpack_new_file_id(media.file_id)
        
        # बैड क्वालिटी फाइल्स ढूंढें और डिलीट करें
        result = await find_and_delete_bad_quality_files(
            bot, 
            base_name, 
            new_file_id
        )
        
        # अगर कुछ डिलीट हुआ तो नोटिफिकेशन भेजें
        if result["deleted"] > 0:
            logger.info(f"✅ Upgraded {base_name}: Deleted {result['deleted']} files")
            await send_upgrade_notification(
                bot,
                base_name,
                file_name,
                result["deleted"],
                result["files"]
            )
        else:
            logger.info(f"ℹ️ No bad quality files found for: {base_name}")
        
    except Exception as e:
        logger.error(f"❌ Error in quality_upgrade_handler: {e}")
        # एडमिन को एरर भेजें
        for admin_id in ADMINS:
            try:
                await bot.send_message(
                    admin_id,
                    f"❌ Quality Upgrade Error!\n\n{str(e)}"
                )
            except:
                pass
