# ia_filterdb_advanced.py

import logging
from struct import pack
import re
import base64
from pyrogram.file_id import FileId
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict, Counter
from pymongo.errors import DuplicateKeyError
from umongo import Instance, Document, fields
from motor.motor_asyncio import AsyncIOMotorClient
from marshmallow import ValidationError
from info import *
from utils import get_settings, save_group_settings
from datetime import datetime, timedelta
import asyncio
from fuzzywuzzy import fuzz, process
import Levenshtein
from cachetools import TTLCache

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------
# Advanced Caching System
_db_stats_cache = {"timestamp": None, "primary_size": 0.0}
_search_cache = TTLCache(maxsize=1000, ttl=300)  # Cache search results for 5 minutes
_suggestion_cache = TTLCache(maxsize=500, ttl=600)  # Cache suggestions for 10 minutes

# Primary DB
client = AsyncIOMotorClient(DATABASE_URI)
db = client[DATABASE_NAME]
instance = Instance.from_db(db)

# Secondary DB
client2 = AsyncIOMotorClient(DATABASE_URI2)
db2 = client2[DATABASE_NAME]
instance2 = Instance.from_db(db2)


@instance.register
class Media(Document):
    file_id = fields.StrField(attribute="_id")
    file_ref = fields.StrField(allow_none=True)
    file_name = fields.StrField(required=True)
    file_size = fields.IntField(required=True)
    file_type = fields.StrField(allow_none=True)
    mime_type = fields.StrField(allow_none=True)
    caption = fields.StrField(allow_none=True)
    # New fields for better search
    search_terms = fields.ListField(fields.StrField(), default=[])
    normalized_name = fields.StrField(allow_none=True)
    keywords = fields.ListField(fields.StrField(), default=[])
    year = fields.IntField(allow_none=True)
    language = fields.StrField(allow_none=True)
    quality = fields.StrField(allow_none=True)
    added_date = fields.DateTimeField(default=datetime.utcnow)

    class Meta:
        indexes = (
            "$file_name",
            "$search_terms",
            "$keywords",
            "$normalized_name",
            ("file_type", "year"),
        )
        collection_name = COLLECTION_NAME


@instance2.register
class Media2(Document):
    file_id = fields.StrField(attribute="_id")
    file_ref = fields.StrField(allow_none=True)
    file_name = fields.StrField(required=True)
    file_size = fields.IntField(required=True)
    file_type = fields.StrField(allow_none=True)
    mime_type = fields.StrField(allow_none=True)
    caption = fields.StrField(allow_none=True)
    search_terms = fields.ListField(fields.StrField(), default=[])
    normalized_name = fields.StrField(allow_none=True)
    keywords = fields.ListField(fields.StrField(), default=[])
    year = fields.IntField(allow_none=True)
    language = fields.StrField(allow_none=True)
    quality = fields.StrField(allow_none=True)
    added_date = fields.DateTimeField(default=datetime.utcnow)

    class Meta:
        indexes = (
            "$file_name",
            "$search_terms",
            "$keywords",
            "$normalized_name",
            ("file_type", "year"),
        )
        collection_name = COLLECTION_NAME


# ========== ADVANCED TEXT PROCESSING ==========

class TextProcessor:
    """Advanced text processing for better search and suggestions"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text for search"""
        if not text:
            return ""
        # Remove special characters but keep important ones
        text = re.sub(r'[^\w\s\-\.\(\)\[\]]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text.lower()
    
    @staticmethod
    def extract_keywords(text: str) -> List[str]:
        """Extract meaningful keywords from text"""
        if not text:
            return []
        # Common stopwords to ignore
        stopwords = {'the', 'a', 'an', 'of', 'for', 'on', 'at', 'to', 'in', 'with', 
                    'without', 'and', 'or', 'but', 'by', 'from', 'into', 'through',
                    'during', 'including', 'etc', 'feat', 'ft', 'hindi', 'english',
                    'dubbed', 'sub', 'uncut', 'full', 'movie', 'series', 'episode'}
        
        # Extract words and filter
        words = re.findall(r'\b[a-zA-Z0-9]{2,}\b', text.lower())
        keywords = [w for w in words if w not in stopwords]
        return list(set(keywords))  # Remove duplicates
    
    @staticmethod
    def extract_year(text: str) -> Optional[int]:
        """Extract year from text"""
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        if year_match:
            return int(year_match.group())
        return None
    
    @staticmethod
    def extract_quality(text: str) -> Optional[str]:
        """Extract quality from text"""
        quality_patterns = {
            '4k': r'\b4[Kk]\b',
            '2160p': r'\b2160p\b',
            '1080p': r'\b1080p\b',
            '720p': r'\b720p\b',
            '480p': r'\b480p\b',
            '360p': r'\b360p\b',
            'hdr': r'\bHDR\b',
            'hd': r'\bHD\b',
            'bluray': r'\bBlu[ -]?Ray\b',
            'web': r'\bWEB[ -]?DL\b',
            'dvd': r'\bDVD\b',
        }
        for quality, pattern in quality_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                return quality
        return None
    
    @staticmethod
    def extract_language(text: str) -> Optional[str]:
        """Extract language from text"""
        languages = {
            'hindi': r'\bHindi\b',
            'tamil': r'\bTamil\b',
            'telugu': r'\bTelugu\b',
            'malayalam': r'\bMalayalam\b',
            'kannada': r'\bKannada\b',
            'english': r'\bEnglish\b',
            'bengali': r'\bBengali\b',
            'marathi': r'\bMarathi\b',
            'gujarati': r'\bGujarati\b',
        }
        for lang, pattern in languages.items():
            if re.search(pattern, text, re.IGNORECASE):
                return lang
        return None
    
    @staticmethod
    def normalize_title(text: str) -> str:
        """Normalize title for better matching"""
        if not text:
            return ""
        # Remove common patterns
        text = re.sub(r'\(?\d{4}\)?', '', text)  # Remove years
        text = re.sub(r'[Ss]\d{1,2}[Ee]\d{1,2}', '', text)  # Remove season/episode
        text = re.sub(r'[\(\{\[]?[^\)\}\]]*[\)\}\]]', '', text)  # Remove parentheses content
        text = re.sub(r'[_\-\+\=\[\]]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text.lower()


# ========== ENHANCED SEARCH FUNCTIONS ==========

async def save_file(media):
    """Save file with advanced metadata extraction"""
    file_id, file_ref = unpack_new_file_id(media.file_id)
    file_name = str(media.file_name)
    
    # Clean and extract metadata
    clean_name = TextProcessor.clean_text(file_name)
    keywords = TextProcessor.extract_keywords(file_name)
    year = TextProcessor.extract_year(file_name)
    quality = TextProcessor.extract_quality(file_name)
    language = TextProcessor.extract_language(file_name)
    normalized_name = TextProcessor.normalize_title(file_name)
    
    # Create search terms
    search_terms = [normalized_name] + keywords
    if year:
        search_terms.append(str(year))
    if language:
        search_terms.append(language)
    if quality:
        search_terms.append(quality)
    
    # Clean filename for display
    file_name_clean = re.sub(r"[_\-\.#+$%^&*()!~`,;:\"'?/<>\[\]{}=|\\]", " ", file_name)
    file_name_clean = re.sub(r"\s+", " ", file_name_clean).strip()
    
    saveMedia = Media
    target_db = "Primary"
    if MULTIPLE_DB:
        try:
            exists = await Media.count_documents({"file_id": file_id}, limit=1)
            if exists:
                logger.info(f"[SKIP] '{file_name}' already in Primary DB.")
                return False, 0
            primary_db_size = await check_db_size(db)
            if primary_db_size >= 407:
                saveMedia = Media2
                target_db = "Secondary"
                logger.warning("Switching to Secondary DB due to size threshold.")
        except Exception as e:
            logger.error("Error during MULTIPLE_DB check; defaulting to primary DB.", exc_info=e)
    
    try:
        record = saveMedia(
            file_id=file_id,
            file_ref=file_ref,
            file_name=file_name_clean,
            file_size=media.file_size,
            file_type=media.file_type,
            mime_type=media.mime_type,
            caption=(media.caption.html if media.caption and INDEX_CAPTION else None),
            search_terms=search_terms,
            normalized_name=normalized_name,
            keywords=keywords,
            year=year,
            language=language,
            quality=quality,
            added_date=datetime.utcnow()
        )
    except ValidationError as e:
        logger.exception(f"[VALIDATION ERROR] '{file_name}' → {e}")
        return False, 2
    
    try:
        await record.commit()
    except DuplicateKeyError:
        logger.info(f"[SKIP] DuplicateKey: '{file_name}' already exists in {target_db} DB.")
        return False, 0
    except Exception as e:
        logger.exception(f"[ERROR] Failed commit of '{file_name}' to {target_db} DB.", exc_info=e)
        return False, 3
    
    logger.info(f"[SUCCESS] '{file_name}' saved to {target_db} DB with metadata.")
    return True, 1


async def advanced_search(
    chat_id: int,
    query: str,
    file_type: Optional[str] = None,
    max_results: int = 10,
    offset: int = 0,
    use_fuzzy: bool = True,
    year: Optional[int] = None,
    quality: Optional[str] = None,
    language: Optional[str] = None,
    min_score: int = 60
) -> Tuple[List[Dict], str, int]:
    """
    Advanced search with multiple strategies:
    1. Exact match
    2. Fuzzy matching
    3. Keyword search
    4. Metadata filtering
    """
    # Check cache first
    cache_key = f"{chat_id}:{query}:{file_type}:{year}:{quality}:{language}"
    if cache_key in _search_cache:
        return _search_cache[cache_key]
    
    # Get settings
    if chat_id is not None:
        settings = await get_settings(int(chat_id))
        try:
            max_results = 10 if settings.get("max_btn") else int(MAX_B_TN)
        except KeyError:
            await save_group_settings(int(chat_id), "max_btn", False)
            settings = await get_settings(int(chat_id))
            max_results = 10 if settings.get("max_btn") else int(MAX_B_TN)
    
    query = query.strip()
    if not query:
        return [], "", 0
    
    # Clean query
    clean_query = TextProcessor.clean_text(query)
    query_keywords = TextProcessor.extract_keywords(query)
    query_year = TextProcessor.extract_year(query) or year
    query_quality = TextProcessor.extract_quality(query) or quality
    query_language = TextProcessor.extract_language(query) or language
    
    # Build search filter
    filter_mongo = {}
    
    # Strategy 1: Exact/near-exact match using search terms
    search_terms = [clean_query] + query_keywords
    if query_year:
        search_terms.append(str(query_year))
    if query_quality:
        search_terms.append(query_quality)
    if query_language:
        search_terms.append(query_language)
    
    # Use $in for search_terms matching
    if USE_CAPTION_FILTER and query:
        filter_mongo = {
            "$or": [
                {"search_terms": {"$in": search_terms}},
                {"caption": {"$regex": re.escape(clean_query), "$options": "i"}}
            ]
        }
    else:
        filter_mongo = {"search_terms": {"$in": search_terms}}
    
    # Add file type filter
    if file_type:
        filter_mongo["file_type"] = file_type
    
    # Add metadata filters
    if query_year:
        filter_mongo["year"] = query_year
    if query_quality:
        filter_mongo["quality"] = query_quality
    if query_language:
        filter_mongo["language"] = query_language
    
    # Get initial results
    total_results = await Media.count_documents(filter_mongo)
    if MULTIPLE_DB:
        total_results += await Media2.count_documents(filter_mongo)
    
    cursor1 = Media.find(filter_mongo).sort("$natural", -1).skip(offset).limit(max_results * 2)
    files1 = await cursor1.to_list(length=max_results * 2)
    
    if MULTIPLE_DB:
        remaining = max_results * 2 - len(files1)
        cursor2 = Media2.find(filter_mongo).sort("$natural", -1).skip(offset).limit(remaining)
        files2 = await cursor2.to_list(length=remaining)
        files = files1 + files2
    else:
        files = files1
    
    # Strategy 2: Fuzzy matching for better results
    if use_fuzzy and len(files) < max_results and query_keywords:
        # Get more results with relaxed filter
        relaxed_filter = {}
        if file_type:
            relaxed_filter["file_type"] = file_type
        if query_year:
            relaxed_filter["year"] = query_year
        
        # Search by keywords
        if query_keywords:
            relaxed_filter["keywords"] = {"$in": query_keywords}
        
        cursor1 = Media.find(relaxed_filter).sort("$natural", -1).limit(max_results * 3)
        more_files = await cursor1.to_list(length=max_results * 3)
        
        if MULTIPLE_DB:
            cursor2 = Media2.find(relaxed_filter).sort("$natural", -1).limit(max_results * 3)
            more_files2 = await cursor2.to_list(length=max_results * 3)
            more_files.extend(more_files2)
        
        # Score and sort by relevance
        scored_files = []
        for file in more_files:
            if file in files:
                continue
            name = getattr(file, "file_name", "")
            score = fuzz.token_set_ratio(clean_query, name.lower())
            if score >= min_score:
                scored_files.append((score, file))
        
        scored_files.sort(key=lambda x: x[0], reverse=True)
        files.extend([f for _, f in scored_files[:max_results]])
    
    # Remove duplicates
    seen = set()
    unique_files = []
    for file in files:
        file_id = getattr(file, "file_id", None)
        if file_id and file_id not in seen:
            seen.add(file_id)
            unique_files.append(file)
    
    # Limit results
    unique_files = unique_files[:max_results]
    
    # Calculate next offset
    next_offset = offset + len(unique_files)
    if next_offset >= total_results:
        next_offset = ""
    
    result = (unique_files, next_offset, total_results)
    
    # Cache results
    _search_cache[cache_key] = result
    
    return result


# ========== ADVANCED SUGGESTIONS ==========

async def get_smart_suggestions(
    query: str,
    chat_id: Optional[int] = None,
    limit: int = 10,
    file_type: Optional[str] = None
) -> List[Dict[str, any]]:
    """
    Get smart suggestions with:
    1. Popular searches
    2. Similar titles
    3. Trending content
    4. Recent additions
    """
    if not query:
        return []
    
    # Check cache
    cache_key = f"smart:{query}:{file_type}:{limit}"
    if cache_key in _suggestion_cache:
        return _suggestion_cache[cache_key]
    
    clean_query = TextProcessor.clean_text(query)
    query_keywords = TextProcessor.extract_keywords(query)
    
    suggestions = []
    seen = set()
    
    # Strategy 1: Auto-complete from database
    if len(query) >= 2:
        regex = re.compile(re.escape(clean_query), re.IGNORECASE)
        filter_mongo = {
            "$or": [
                {"file_name": regex},
                {"normalized_name": regex},
                {"search_terms": {"$regex": regex}}
            ]
        }
        if file_type:
            filter_mongo["file_type"] = file_type
        
        cursor = Media.find(filter_mongo).sort("$natural", -1).limit(limit * 3)
        files = await cursor.to_list(length=limit * 3)
        
        if MULTIPLE_DB:
            cursor2 = Media2.find(filter_mongo).sort("$natural", -1).limit(limit * 3)
            files2 = await cursor2.to_list(length=limit * 3)
            files.extend(files2)
        
        # Extract unique titles
        for file in files:
            name = getattr(file, "file_name", "")
            if name and name not in seen:
                seen.add(name)
                # Get metadata
                year = getattr(file, "year", None)
                quality = getattr(file, "quality", None)
                language = getattr(file, "language", None)
                suggestion = {
                    "title": name,
                    "year": year,
                    "quality": quality,
                    "language": language,
                    "type": getattr(file, "file_type", "unknown"),
                    "display": f"{name}{f' ({year})' if year else ''}{f' [{quality}]' if quality else ''}"
                }
                suggestions.append(suggestion)
    
    # Strategy 2: Keywords-based suggestions
    if len(suggestions) < limit and query_keywords:
        keyword_filter = {"keywords": {"$in": query_keywords}}
        if file_type:
            keyword_filter["file_type"] = file_type
        
        cursor = Media.find(keyword_filter).sort("$natural", -1).limit(limit * 2)
        keyword_files = await cursor.to_list(length=limit * 2)
        
        if MULTIPLE_DB:
            cursor2 = Media2.find(keyword_filter).sort("$natural", -1).limit(limit * 2)
            keyword_files2 = await cursor2.to_list(length=limit * 2)
            keyword_files.extend(keyword_files2)
        
        for file in keyword_files:
            name = getattr(file, "file_name", "")
            if name and name not in seen:
                seen.add(name)
                year = getattr(file, "year", None)
                quality = getattr(file, "quality", None)
                suggestion = {
                    "title": name,
                    "year": year,
                    "quality": quality,
                    "type": getattr(file, "file_type", "unknown"),
                    "display": f"{name}{f' ({year})' if year else ''}"
                }
                suggestions.append(suggestion)
    
    # Strategy 3: Fuzzy matching
    if len(suggestions) < limit:
        # Get more files
        cursor = Media.find().sort("$natural", -1).limit(100)
        all_files = await cursor.to_list(length=100)
        
        if MULTIPLE_DB:
            cursor2 = Media2.find().sort("$natural", -1).limit(100)
            all_files2 = await cursor2.to_list(length=100)
            all_files.extend(all_files2)
        
        # Score and match
        scored = []
        for file in all_files:
            name = getattr(file, "file_name", "")
            if name in seen:
                continue
            score = fuzz.partial_ratio(clean_query, name.lower())
            if score > 60:  # Minimum threshold
                scored.append((score, name, file))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        for _, name, file in scored[:limit - len(suggestions)]:
            if name not in seen:
                seen.add(name)
                year = getattr(file, "year", None)
                suggestions.append({
                    "title": name,
                    "year": year,
                    "type": getattr(file, "file_type", "unknown"),
                    "display": f"{name}{f' ({year})' if year else ''} (fuzzy match)"
                })
    
    # Cache results
    _suggestion_cache[cache_key] = suggestions[:limit]
    
    return suggestions[:limit]


async def get_trending_content(limit: int = 10) -> List[Dict[str, any]]:
    """Get trending content based on recent additions"""
    try:
        # Get recent files
        recent_filter = {
            "added_date": {"$gte": datetime.utcnow() - timedelta(days=7)}
        }
        
        cursor = Media.find(recent_filter).sort("added_date", -1).limit(50)
        recent_files = await cursor.to_list(length=50)
        
        if MULTIPLE_DB:
            cursor2 = Media2.find(recent_filter).sort("added_date", -1).limit(50)
            recent_files2 = await cursor2.to_list(length=50)
            recent_files.extend(recent_files2)
        
        # Group by normalized title and count
        title_counter = defaultdict(int)
        title_info = {}
        
        for file in recent_files:
            norm = getattr(file, "normalized_name", "")
            if norm:
                title_counter[norm] += 1
                if norm not in title_info:
                    title_info[norm] = {
                        "title": getattr(file, "file_name", ""),
                        "year": getattr(file, "year", None),
                        "type": getattr(file, "file_type", "unknown"),
                        "quality": getattr(file, "quality", None),
                        "language": getattr(file, "language", None)
                    }
        
        # Sort by frequency
        sorted_titles = sorted(
            title_counter.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        trending = []
        for norm, count in sorted_titles:
            info = title_info.get(norm, {})
            info["trending_score"] = count
            info["display"] = f"{info.get('title', norm)} (🔥 {count}x)"
            trending.append(info)
        
        return trending
        
    except Exception as e:
        logger.error(f"Error in get_trending_content: {e}")
        return []


async def get_search_stats() -> Dict[str, any]:
    """Get search statistics and insights"""
    try:
        # Get total counts
        total_primary = await Media.count_documents({})
        total_secondary = await Media2.count_documents({}) if MULTIPLE_DB else 0
        
        # Get file type distribution
        type_counts = {}
        file_types = ["document", "video", "audio", "photo", "animation"]
        for ftype in file_types:
            count = await Media.count_documents({"file_type": ftype})
            if MULTIPLE_DB:
                count += await Media2.count_documents({"file_type": ftype})
            if count > 0:
                type_counts[ftype] = count
        
        # Get language distribution
        lang_pipeline = [
            {"$match": {"language": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$language", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        
        lang_counts = {}
        if hasattr(Media, 'aggregate'):
            cursor = Media.aggregate(lang_pipeline)
            async for doc in cursor:
                lang_counts[doc["_id"]] = doc["count"]
        
        # Get year distribution
        year_pipeline = [
            {"$match": {"year": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$year", "count": {"$sum": 1}}},
            {"$sort": {"_id": -1}},
            {"$limit": 20}
        ]
        
        year_counts = {}
        if hasattr(Media, 'aggregate'):
            cursor = Media.aggregate(year_pipeline)
            async for doc in cursor:
                year_counts[doc["_id"]] = doc["count"]
        
        stats = {
            "total_files": total_primary + total_secondary,
            "primary_db_size": total_primary,
            "secondary_db_size": total_secondary,
            "file_type_distribution": type_counts,
            "language_distribution": dict(sorted(lang_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            "year_distribution": dict(sorted(year_counts.items(), key=lambda x: x[0], reverse=True)[:20]),
            "last_updated": datetime.utcnow().isoformat()
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error in get_search_stats: {e}")
        return {}


# ========== MAINTENANCE FUNCTIONS ==========

async def rebuild_search_indexes():
    """Rebuild search indexes for better performance"""
    try:
        # Drop existing indexes
        await Media.collection.drop_indexes()
        if MULTIPLE_DB:
            await Media2.collection.drop_indexes()
        
        # Create new indexes
        await Media.collection.create_index([("search_terms", "text")])
        await Media.collection.create_index([("keywords", "text")])
        await Media.collection.create_index([("normalized_name", "text")])
        await Media.collection.create_index([("year", 1), ("file_type", 1)])
        await Media.collection.create_index([("language", 1), ("file_type", 1)])
        await Media.collection.create_index([("quality", 1), ("file_type", 1)])
        await Media.collection.create_index([("added_date", -1)])
        
        if MULTIPLE_DB:
            await Media2.collection.create_index([("search_terms", "text")])
            await Media2.collection.create_index([("keywords", "text")])
            await Media2.collection.create_index([("normalized_name", "text")])
            await Media2.collection.create_index([("year", 1), ("file_type", 1)])
            await Media2.collection.create_index([("language", 1), ("file_type", 1)])
            await Media2.collection.create_index([("quality", 1), ("file_type", 1)])
            await Media2.collection.create_index([("added_date", -1)])
        
        logger.info("Search indexes rebuilt successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error rebuilding search indexes: {e}")
        return False


# ========== COMPATIBILITY FUNCTIONS ==========

# Keep original functions for backward compatibility
async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False):
    """Wrapper for backward compatibility"""
    result = await advanced_search(chat_id, query, file_type, max_results, offset)
    return result


async def get_bad_files(query, file_type=None):
    """Enhanced version of get_bad_files"""
    # Original implementation with minor improvements
    query = query.strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r"(\b|[\.\+\-_])" + query + r"(\b|[\.\+\-_])"
    else:
        raw_pattern = query.replace(" ", r".*[\s\.\+\-_()]")
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except:
        return []
    
    # Use search_terms for better matching
    if USE_CAPTION_FILTER:
        filter = {
            '$or': [
                {'file_name': regex},
                {'caption': regex},
                {'search_terms': {'$regex': regex}}
            ]
        }
    else:
        filter = {
            '$or': [
                {'file_name': regex},
                {'search_terms': {'$regex': regex}}
            ]
        }
    
    if file_type:
        filter['file_type'] = file_type
    
    cursor1 = Media.find(filter).sort('$natural', -1)
    files1 = await cursor1.to_list(length=(await Media.count_documents(filter)))
    
    if MULTIPLE_DB:
        cursor2 = Media2.find(filter).sort('$natural', -1)
        files2 = await cursor2.to_list(length=(await Media2.count_documents(filter)))
        files = files1 + files2
    else:
        files = files1
    
    total_results = len(files)
    return files, total_results


# Keep other original functions
async def get_file_details(query):
    filter = {"file_id": query}
    cursor = Media.find(filter)
    filedetails = await cursor.to_list(length=1)
    if not filedetails and MULTIPLE_DB:
        cursor2 = Media2.find(filter)
        filedetails = await cursor2.to_list(length=1)
    return filedetails


def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0
    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0
            r += bytes([i])
    return base64.urlsafe_b64encode(r).decode().rstrip("=")


def encode_file_ref(file_ref: bytes) -> str:
    return base64.urlsafe_b64encode(file_ref).decode().rstrip("=")


def unpack_new_file_id(new_file_id):
    """Return file_id, file_ref"""
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash,
        )
    )
    file_ref = encode_file_ref(decoded.file_reference)
    return file_id, file_ref


async def check_db_size(db):
    try:
        now = datetime.utcnow()
        cache_stale_by_time = _db_stats_cache["timestamp"] is None or (
            now - _db_stats_cache["timestamp"] > timedelta(minutes=10)
        )
        refresh_if_size_threshold = _db_stats_cache["primary_size"] >= 10.0
        if not cache_stale_by_time and not refresh_if_size_threshold:
            return _db_stats_cache["primary_size"]
        stats = await db.command("dbstats")
        db_logical_size = stats["dataSize"]
        db_index_size = stats["indexSize"]
        db_logical_size_mb = db_logical_size / (1024 * 1024)
        db_index_size_mb = db_index_size / (1024 * 1024)
        db_size_mb = db_logical_size_mb + db_index_size_mb
        _db_stats_cache["primary_size"] = db_size_mb
        _db_stats_cache["timestamp"] = now
        return db_size_mb
    except Exception as e:
        print(f"Error Checking Database Size: {e}")
        return 0


# Advanced versions of dreamxbotz functions
async def dreamxbotz_fetch_media(limit: int) -> List[dict]:
    try:
        if MULTIPLE_DB:
            db_size = await check_db_size(Media)
            if db_size > 407:
                cursor = Media2.find().sort("$natural", -1).limit(limit)
                files = await cursor.to_list(length=limit)
                return files
        cursor = Media.find().sort("$natural", -1).limit(limit)
        files = await cursor.to_list(length=limit)
        return files
    except Exception as e:
        logger.error(f"Error in dreamxbotz_fetch_media: {e}")
        return []


async def dreamxbotz_clean_title(filename: str, is_series: bool = False) -> str:
    # Enhanced version using TextProcessor
    try:
        if is_series:
            season_match = re.search(
                r"(.*?)(?:S(\d{1,2})|Season\s*(\d+)|Season(\d+))(?:\s*Combined)?",
                filename,
                re.IGNORECASE,
            )
            if season_match:
                title = season_match.group(1).strip()
                season = (
                    season_match.group(2)
                    or season_match.group(3)
                    or season_match.group(4)
                )
                title = TextProcessor.normalize_title(title).title()
                return f"{title} S{int(season):02}"
        
        year_match = re.search(r"^(.*?(\d{4}|\(\d{4}\)))", filename, re.IGNORECASE)
        if year_match:
            title = year_match.group(1).replace("(", "").replace(")", "")
            return TextProcessor.normalize_title(title).title()
        
        return TextProcessor.normalize_title(filename).title()
        
    except Exception as e:
        logger.error(f"Error in dreamxbotz_clean_title: {e}")
        return filename


async def dreamxbotz_get_movies(limit: int = 20) -> List[str]:
    try:
        cursor = await dreamxbotz_fetch_media(limit * 2)
        results = set()
        pattern = r"(?:s\d{1,2}|season\s*\d+|season\d+)(?:\s*combined)?(?:e\d{1,2}|episode\s*\d+)?\b"
        for file in cursor:
            file_name = getattr(file, "file_name", "")
            if not re.search(pattern, file_name, re.IGNORECASE):
                title = await dreamxbotz_clean_title(file_name)
                results.add(title)
            if len(results) >= limit:
                break
        return sorted(list(results))[:limit]
    except Exception as e:
        logger.error(f"Error in dreamxbotz_get_movies: {e}")
        return []


async def dreamxbotz_get_series(limit: int = 30) -> Dict[str, List[int]]:
    try:
        cursor = await dreamxbotz_fetch_media(limit * 5)
        grouped = defaultdict(list)
        pattern = r"(.*?)(?:S(\d{1,2})|Season\s*(\d+)|Season(\d+))(?:\s*Combined)?(?:E(\d{1,2})|Episode\s*(\d+))?\b"
        for file in cursor:
            file_name = getattr(file, "file_name", "")
            match = re.search(pattern, file_name, re.IGNORECASE)
            if match:
                title = await dreamxbotz_clean_title(match.group(1), is_series=True)
                season = int(match.group(2) or match.group(3) or match.group(4))
                grouped[title].append(season)
        return {
            title: sorted(set(seasons))[:10]
            for title, seasons in grouped.items()
            if seasons
        }
    except Exception as e:
        logger.error(f"Error in dreamxbotz_get_series: {e}")
        return []
