# plugins/quality_upgrade.py

import re
import logging
from database.ia_filterdb import Media, Media2
from info import MULTIPLE_DB, LOG_CHANNEL

logger = logging.getLogger(__name__)

# ❌ BAD QUALITY - Sirf ye delete hongi (CAM/Theatre/Dubbing)
BAD_QUALITY_KEYWORDS = [
    "cam", "camrip", "hdcam", "hdtc",
    "ts", "tc", "telesync", 
    "theatre", "theatrical", "theater",
    "print", "screener", "dvdscr", "predvd",
    "hqcam", "hdts", "hdtvrip",
    "dub", "dubbing", "dubbed", 
    "hindidubbed", "tamildubbed", "telugudubbed",
    "hindi dubbed", "tamil dubbed", "telugu dubbed",
]

# ✅ GOOD QUALITY - Real HD (ye kabhi delete nahi hongi)
GOOD_QUALITY_KEYWORDS = [
    "webdl", "web-dl", "web dl", 
    "webrip", "web rip",
    "bluray", "blu-ray", "blu ray",
    "brrip", "bdrip", "br rip", "bd rip",
    "1080p", "2160p", "4k", "1440p", "720p",
    "hdtv", "hdtvrip", "hdtv rip",
    "hevc", "x264", "x265", "h264", "h265",
    "netflix", "nf", "amzn", "prime", "amazon",
    "hotstar", "disney", "sonyliv", "zee5",
    "jio", "aha", "viki", "apple tv", "paramount",
    "dolby", "atmos", "truehd", "dts"
]

def get_movie_base_name(filename: str) -> str:
    """
    Movie ka base name extract karein (year ke saath)
    Example: "Jawan 2023 1080p WebDL" -> "Jawan 2023"
    """
    if not filename:
        return ""
    
    name = filename.lower()
    
    # Quality keywords hatao (dono types)
    all_keywords = BAD_QUALITY_KEYWORDS + GOOD_QUALITY_KEYWORDS
    for kw in all_keywords:
        name = name.replace(kw, "")
    
    # Year extract karein
    year_match = re.search(r'(19|20)\d{2}', name)
    year = year_match.group(0) if year_match else ""
    
    # Special characters hatao
    name = re.sub(r'[._\-\[\](){}@]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    if year:
        year_pos = name.find(year)
        if year_pos != -1:
            name = name[:year_pos + 4].strip()
    
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name.title()

def is_bad_quality(filename: str) -> bool:
    """
    Check karein ki file bad quality (Theatre/CAM/Dubbing) hai ya nahi
    """
    if not filename:
        return False
    
    filename_lower = filename.lower()
    
    # 🔥 PEHLE CHECK: Agar good quality hai toh bad quality nahi maanenge
    for kw in GOOD_QUALITY_KEYWORDS:
        if kw in filename_lower:
            return False  # Good quality hai, delete nahi karenge
    
    # Ab bad quality check karein
    for kw in BAD_QUALITY_KEYWORDS:
        if kw in filename_lower:
            return True
    
    return False

def is_good_quality(filename: str) -> bool:
    """
    Check karein ki file good quality (WebDL/BluRay/1080p etc.) hai ya nahi
    """
    if not filename:
        return False
    
    filename_lower = filename.lower()
    
    for kw in GOOD_QUALITY_KEYWORDS:
        if kw in filename_lower:
            return True
    
    return False

async def find_and_delete_bad_quality_files(bot, base_name, new_good_file=None):
    """
    Kisi movie ki saari bad quality (CAM/Theatre/Dubbing) files delete karein
    WebDL/BluRay/1080p files delete nahi hongi
    """
    if not base_name:
        return {"deleted": 0, "files": []}
    
    deleted_files = []
    deleted_count = 0
    
    try:
        base_name_escaped = re.escape(base_name)
        search_pattern = re.compile(base_name_escaped, re.IGNORECASE)
        query = {"file_name": {"$regex": search_pattern}}
        
        # PRIMARY DB
        cursor = Media.find(query)
        async for doc in cursor:
            file_name = doc.file_name
            if is_bad_quality(file_name):
                if new_good_file and file_name == new_good_file:
                    continue
                
                try:
                    result = await Media.collection.delete_one({"_id": doc.file_id})
                    if result.deleted_count:
                        deleted_count += 1
                        deleted_files.append(file_name)
                        logger.info(f"🗑️ Deleted CAM/Theatre: {file_name}")
                except Exception as e:
                    logger.error(f"Failed to delete {file_name}: {e}")
        
        # SECONDARY DB
        if MULTIPLE_DB:
            cursor2 = Media2.find(query)
            async for doc in cursor2:
                file_name = doc.file_name
                if is_bad_quality(file_name):
                    if new_good_file and file_name == new_good_file:
                        continue
                    
                    try:
                        result = await Media2.collection.delete_one({"_id": doc.file_id})
                        if result.deleted_count:
                            deleted_count += 1
                            deleted_files.append(file_name)
                            logger.info(f"🗑️ Deleted from DB2: {file_name}")
                    except Exception as e:
                        logger.error(f"Failed to delete from DB2 {file_name}: {e}")
        
        # LOG
        if deleted_count > 0 and LOG_CHANNEL:
            try:
                text = f"""
🎬 **QUALITY UPGRADE - CAM/Theatre Deleted**

📽️ **Movie:** `{base_name}`

✅ **New Good Quality Added:**
`{new_good_file}`

🗑️ **Deleted CAM/Theatre Files:** `{deleted_count}`

📋 **Deleted Files:**
"""
                for f in deleted_files[:5]:
                    text += f"• `{f[:60]}...`\n"
                if len(deleted_files) > 5:
                    text += f"• ... and {len(deleted_files) - 5} more\n"
                
                text += f"\n💡 **Auto-Delete by Quality Upgrade System**"
                await bot.send_message(LOG_CHANNEL, text, parse_mode="html")
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
            
    except Exception as e:
        logger.error(f"Error in find_and_delete_bad_quality_files: {e}")
    
    return {"deleted": deleted_count, "files": deleted_files}
