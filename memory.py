# memory.py - Sistem penyimpanan history percakapan Mirai
"""
Simple disk-based memory system untuk menyimpan history percakapan.
Menggunakan JSON file untuk persistensi data dan deque untuk cache RAM.

PERBAIKAN: History dipisah per context (server/DM) agar nama user tidak tercampur.
"""

import asyncio
import threading
import json
import os
import time
from typing import List, Dict, Optional
from collections import deque
from itertools import islice
from config import MAX_HISTORY, HISTORY_FILE
from utils.logger import setup_logging

logger = setup_logging()

# ===== CACHE RAM =====
_history_cache = deque(maxlen=MAX_HISTORY)
_cache_lock = threading.Lock()

# Context tracking untuk deteksi perpindahan server ↔ DM
_current_context_id: Optional[str] = None  # Format: "server:GUILD_ID" atau "dm:USER_ID"

# ===== DISK OPERATIONS =====

def _load_history():
    """Load history dari disk ke cache RAM."""
    if not os.path.exists(HISTORY_FILE):
        logger.info("[Memory] File %s tidak ditemukan, mulai dengan history kosong", HISTORY_FILE)
        return
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                _history_cache.extend(data[-MAX_HISTORY:])
        logger.info("[Memory] Loaded %s pesan dari disk", len(_history_cache))
    except json.JSONDecodeError:
        corrupt_name = f"{HISTORY_FILE}.corrupt-{int(time.time())}"
        try:
            os.replace(HISTORY_FILE, corrupt_name)
            logger.error("[Memory] File %s corrupt, dipindahkan ke %s", HISTORY_FILE, corrupt_name)
        except Exception:
            logger.exception("[Memory] File %s corrupt dan gagal dipindahkan", HISTORY_FILE)
    except Exception as e:
        logger.exception("[Memory] Load error: %s", e)

def _save_history():
    """Simpan history dari cache RAM ke disk."""
    try:
        with _cache_lock:
            data = list(_history_cache)
        tmp_path = f"{HISTORY_FILE}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, HISTORY_FILE)
    except Exception as e:
        logger.exception("[Memory] Save error: %s", e)

# ===== PUBLIC API =====

def detect_context(guild_id: Optional[int], user_id: int) -> str:
    """
    Deteksi context ID berdasarkan guild_id dan user_id.
    
    Returns:
        str: "server:GUILD_ID" atau "dm:USER_ID"
    """
    if guild_id:
        return f"server:{guild_id}"
    return f"dm:{user_id}"


def reset_on_context_change(guild_id: Optional[int], user_id: int) -> bool:
    """
    Reset history jika user berpindah context (server ↔ DM atau antar server).
    
    Returns:
        bool: True jika history di-reset, False jika tidak
    """
    global _current_context_id
    
    new_context = detect_context(guild_id, user_id)
    
    if _current_context_id is None:
        _current_context_id = new_context
        logger.info("[Memory] Context initialized: %s", new_context)
        return False
    
    if new_context != _current_context_id:
        logger.info("[Memory] Context changed: %s -> %s. Resetting history...", _current_context_id, new_context)
        clear_history()
        _current_context_id = new_context
        return True
    
    return False


async def add_message(role: str, content: str):
    """
    Tambah pesan ke history.
    
    Args:
        role: "user" atau "assistant"
        content: Isi pesan
    """
    formatted = {
        "role": "model" if role == "assistant" else "user",
        "parts": [{"text": content.strip()}]
    }
    with _cache_lock:
        _history_cache.append(formatted)
    await asyncio.to_thread(_save_history)

def get_history() -> List[Dict]:
    """
    Ambil seluruh history.
    
    Returns:
        List of dict dengan format {"role": str, "parts": list}
    """
    return list(_history_cache)

def get_recent_history(count: int = 5) -> List[Dict]:
    """
    Ambil N pesan terakhir dari history.
    
    Args:
        count: Jumlah pesan yang diambil
        
    Returns:
        List of dict dengan format {"role": str, "parts": list}
    """
    total = len(_history_cache)
    if total <= count:
        return list(_history_cache)
    return list(islice(_history_cache, total - count, total))

def clear_history():
    """Hapus seluruh history."""
    _history_cache.clear()
    _save_history()
    logger.info("[Memory] History cleared")

def get_history_length():
    """
    Ambil jumlah pesan di history.
    
    Returns:
        int: Jumlah pesan
    """
    return len(_history_cache)

# ===== INITIALIZATION =====
_load_history()
logger.info("[Memory] Ready - Simple disk mode (context-aware)")
logger.info("[Memory] Max History: %s | File: %s", MAX_HISTORY, HISTORY_FILE)
