
# core/micro_rag.py - Sistem Micro-RAG untuk Profiling User
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from groq import Groq
from dotenv import load_dotenv
from utils.logger import setup_logging

load_dotenv()
logger = setup_logging()

# Konfigurasi
GROQ_API_KEY_M_RAG = os.getenv("GROQ_API_KEY_M_RAG")
USER_PROFILES_PATH = Path("data/user_profiles.json")
HISTORY_PATH = Path("history.json")
MODEL_NAME = "llama-3.1-8b-instant"

class MicroRAG:
    """
    AI Worker untuk menganalisis riwayat percakapan dan membangun profil kepribadian user.
    """
    def __init__(self, api_key: Optional[str] = GROQ_API_KEY_M_RAG):
        if not api_key:
            logger.warning("[Micro-RAG] GROQ_API_KEY_M_RAG tidak ditemukan. Fitur dinonaktifkan.")
            self.client = None
        else:
            self.client = Groq(api_key=api_key)
        
        self.profiles = self._load_profiles()

    def _load_profiles(self) -> Dict:
        if USER_PROFILES_PATH.exists():
            try:
                return json.loads(USER_PROFILES_PATH.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"[Micro-RAG] Gagal memuat profil: {e}")
        return {}

    def _save_profiles(self):
        USER_PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            USER_PROFILES_PATH.write_text(json.dumps(self.profiles, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"[Micro-RAG] Gagal menyimpan profil: {e}")

    def _extract_user_messages(self) -> Dict[str, List[str]]:
        """Mengelompokkan pesan user dari history.json berdasarkan user_id."""
        user_data = {}
        if not HISTORY_PATH.exists():
            return user_data

        try:
            history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
            for entry in history:
                user_field = entry.get("user", "")
                message = entry.get("message", "")
                if not user_field or not message:
                    continue
                # Format user_field: "Nama | ID"
                parts = user_field.rsplit(" | ", 1)
                if len(parts) == 2:
                    user_id = parts[1].strip()
                else:
                    # fallback: pakai ID dari string jika ada, atau skip
                    continue
                if user_id not in user_data:
                    user_data[user_id] = []
                user_data[user_id].append(message)
        except Exception as e:
            logger.error(f"[Micro-RAG] Gagal ekstraksi history: {e}")
        
        return user_data

    async def analyze_all_users(self):
        """Menganalisis semua user yang ada di history."""
        if not self.client:
            return

        logger.info("[Micro-RAG] Memulai analisis profil harian...")
        user_messages = self._extract_user_messages()
        
        for user_id, messages in user_messages.items():
            # Hanya analisis jika ada pesan baru atau cukup banyak data
            if len(messages) < 3:
                continue
                
            logger.info(f"[Micro-RAG] Menganalisis user {user_id}...")
            profile = await self._generate_profile(user_id, messages)
            if profile:
                self.profiles[user_id] = profile
        
        self._save_profiles()
        logger.info("[Micro-RAG] Analisis profil selesai.")

    async def _generate_profile(self, user_id: str, messages: List[str]) -> Optional[Dict]:
        """Meminta AI untuk merangkum kepribadian berdasarkan pesan."""
        chat_sample = "\n".join(messages[-20:]) # Ambil 20 pesan terakhir
        
        prompt = f"""
        Analisis riwayat percakapan berikut dan buatlah profil kepribadian singkat untuk user dengan ID {user_id}.
        
        Riwayat Percakapan:
        {chat_sample}
        
        Tugasmu:
        1. Simpulkan kepribadiannya (misal: ramah, pemarah, melankolis, ceria).
        2. Identifikasi minat atau hobi yang sering dibahas (misal: novel, coding, musik).
        3. Berikan ringkasan suasana hati (mood) mereka belakangan ini.
        
        Output harus dalam format JSON murni:
        {{
            "personality": "string",
            "interests": ["list", "of", "strings"],
            "mood_summary": "string",
            "notable_facts": ["fakta unik tentang user"]
        }}
        """
        
        try:
            completion = await self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "Kamu adalah AI Profiler yang tajam dan empatik."},
                    {"role": "user", "content": prompt}
                ],
                response_format={ "type": "json_object" }
            )
            
            analysis = json.loads(completion.choices[0].message.content)
            
            # Tambahkan metadata manusiawi
            now = datetime.now(ZoneInfo('Asia/Jakarta'))
            existing_profile = self.profiles.get(user_id, {})
            current_exp = existing_profile.get("exp", 0) + 10 # Tambah EXP setiap analisis
            
            return {
                "user_id": user_id,
                "personality": analysis.get("personality", "Misterius"),
                "interests": analysis.get("interests", []),
                "mood_summary": analysis.get("mood_summary", "Stabil"),
                "notable_facts": analysis.get("notable_facts", []),
                "exp": current_exp,
                "last_updated": now.strftime("%Y-%m-%d %H:%M:%S WIB"),
                "human_meta": f"Profil ini diperbarui pada {now.strftime('%A, %d %B %Y')} pukul {now.strftime('%H:%M')}."
            }
        except Exception as e:
            logger.error(f"[Micro-RAG] Gagal generate profil untuk {user_id}: {e}")
            return None

    def get_user_context(self, user_id: str) -> str:
        """Mendapatkan string konteks profil untuk disuntikkan ke prompt Mirai."""
        profile = self.profiles.get(str(user_id))
        if not profile:
            return ""
            
        context = f"\n\n[MEMORI JANGKA PANJANG USER]\n"
        context += f"Kepribadian: {profile['personality']}\n"
        context += f"Minat: {', '.join(profile['interests'])}\n"
        context += f"Mood Terakhir: {profile['mood_summary']}\n"
        if profile['notable_facts']:
            context += f"Fakta Unik: {', '.join(profile['notable_facts'])}\n"
        context += f"Catatan: Gunakan informasi ini untuk bersikap lebih personal dan akrab seolah kamu sudah lama mengenalnya."
        
        return context
