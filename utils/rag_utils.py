import os
import json
import time
import threading
import tempfile
import shutil
from datetime import datetime
from typing import Any, Dict, Optional
from utils.logger import setup_logging

logger = setup_logging()

USER_PROFILE_PATH = "data/user_profiles.json"
TTL_DAYS = 3
TTL_SECONDS = TTL_DAYS * 24 * 60 * 60

# Lock untuk thread safety saat akses file
_profile_lock = threading.Lock()

def _ensure_dir():
    """Memastikan direktori data ada."""
    dir_path = os.path.dirname(USER_PROFILE_PATH)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)

def _atomic_save(data: Dict[str, Any]):
    """Menyimpan data JSON secara atomik untuk mencegah korupsi file."""
    _ensure_dir()
    
    # Tulis ke file sementara dulu
    fd, temp_path = tempfile.mkstemp(suffix='.json', dir=os.path.dirname(USER_PROFILE_PATH))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        # Ganti file asli dengan file sementara
        shutil.move(temp_path, USER_PROFILE_PATH)
    except Exception as e:
        # Jika gagal, hapus file sementara
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e

def load_profiles() -> Dict[str, Any]:
    """
    Memuat profil user dari file JSON.
    Menggunakan lock untuk mencegah race condition.
    """
    with _profile_lock:
        if not os.path.exists(USER_PROFILE_PATH):
            return {}
        try:
            with open(USER_PROFILE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"[Micro-RAG] Gagal memuat profil: {e}")
            return {}

def save_profiles(profiles: Dict[str, Any]):
    """
    Menyimpan profil user ke file JSON secara atomik.
    """
    with _profile_lock:
        try:
            _atomic_save(profiles)
        except Exception as e:
            logger.error(f"[Micro-RAG] Gagal menyimpan profil: {e}")

def clean_old_profiles() -> int:
    """
    Menghapus profil user yang lebih tua dari TTL (3 hari).
    Returns: Jumlah profil yang dihapus.
    """
    with _profile_lock:
        if not os.path.exists(USER_PROFILE_PATH):
            return 0
            
        try:
            with open(USER_PROFILE_PATH, 'r', encoding='utf-8') as f:
                profiles = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"[Micro-RAG] Gagal memuat profil untuk cleaning: {e}")
            return 0

        current_time = time.time()
        expired_users = []

        for user_id, data in profiles.items():
            last_updated = data.get("last_updated", 0)
            if current_time - last_updated > TTL_SECONDS:
                expired_users.append(user_id)

        if not expired_users:
            return 0

        for user_id in expired_users:
            del profiles[user_id]

        try:
            _atomic_save(profiles)
            logger.info(f"[Micro-RAG] Dibersihkan {len(expired_users)} profil user yang sudah > {TTL_DAYS} hari.")
            return len(expired_users)
        except Exception as e:
            logger.error(f"[Micro-RAG] Gagal menyimpan hasil cleaning: {e}")
            return 0

def update_profile(user_id: str, new_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mengupdate atau membuat profil user baru.
    Otomatis memperbarui timestamp 'last_updated' dan memastikan TTL logic terjaga.
    
    Args:
        user_id: ID unik user (string)
        new_data: Dictionary data profil yang akan diupdate
        
    Returns:
        Profil user yang sudah diupdate
    """
    # Pastikan user_id string
    user_id = str(user_id)
    
    with _profile_lock:
        # Load data saat ini (dalam lock agar konsisten)
        if os.path.exists(USER_PROFILE_PATH):
            try:
                with open(USER_PROFILE_PATH, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
            except (json.JSONDecodeError, IOError):
                profiles = {}
        else:
            profiles = {}

        current_time = time.time()
        
        if user_id not in profiles:
            profiles[user_id] = {
                "created_at": current_time,
                "last_updated": current_time,
                "data": {} # Container untuk data spesifik
            }
        
        # Update data profil
        # Jika new_data punya key 'last_updated', kita abaikan karena akan di-set otomatis
        data_payload = new_data.copy()
        if "last_updated" in data_payload:
            del data_payload["last_updated"]
            
        # Merge data ke dalam 'data' key atau update langsung? 
        # Strategi: Update langsung ke root profil agar mudah diakses, 
        # kecuali ada key reserved (created_at, last_updated)
        for key, value in data_payload.items():
            if key not in ("created_at", "last_updated"):
                profiles[user_id][key] = value
        
        # Update timestamp
        profiles[user_id]["last_updated"] = current_time

        # Simpan secara atomik
        try:
            _atomic_save(profiles)
            logger.debug(f"[Micro-RAG] Profil user {user_id} diupdate.")
            return profiles[user_id]
        except Exception as e:
            logger.error(f"[Micro-RAG] Gagal menyimpan profil user {user_id}: {e}")
            # Return data yang sudah diupdate di memori meskipun gagal save (fallback)
            return profiles[user_id]

def get_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Mengambil profil user spesifik.
    """
    profiles = load_profiles()
    return profiles.get(str(user_id))

def is_profile_expired(user_id: str) -> bool:
    """
    Mengecek apakah profil user sudah kadaluarsa (expired).
    """
    profile = get_profile(user_id)
    if not profile:
        return True
    
    current_time = time.time()
    last_updated = profile.get("last_updated", 0)
    return (current_time - last_updated) > TTL_SECONDS
