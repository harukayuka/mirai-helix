
# core/micro_rag.py - Sistem Micro-RAG untuk Profiling User
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from groq import AsyncGroq
from dotenv import load_dotenv
from utils.logger import setup_logging

load_dotenv()
logger = setup_logging()

# Konfigurasi
GROQ_API_KEY_M_RAG = os.getenv("GROQ_API_KEY_M_RAG")
USER_PROFILES_PATH = Path("data/user_profiles.json")
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
            self.client = AsyncGroq(api_key=api_key)
        
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
        """Mengelompokkan pesan user dari data/chat_log.json berdasarkan user_id.
        
        Format entry di chat_log.json (dari message_handler._save_to_history):
        {
            "timestamp": "...",
            "user": "Nama | ID",
            "channel": "Channel | ID",
            "message": "pesan user",
            "response": "respon bot",
            "response_timestamp": "..."
        }
        """
        CHAT_LOG_PATH = Path("data/chat_log.json")
        user_data = {}
        if not CHAT_LOG_PATH.exists():
            return user_data

        try:
            history = json.loads(CHAT_LOG_PATH.read_text(encoding="utf-8"))
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
                    continue
                if user_id not in user_data:
                    user_data[user_id] = []
                user_data[user_id].append(message)
        except Exception as e:
            logger.error(f"[Micro-RAG] Gagal ekstraksi history: {e}")
        
        return user_data

    async def analyze_all_users(self):
        """Menganalisis semua user yang ada di chat log. Skip user yang profilnya masih fresh (< 20 jam)."""
        if not self.client:
            return

        logger.info("[Micro-RAG] Memulai analisis profil harian...")
        user_messages = self._extract_user_messages()
        now = datetime.now(ZoneInfo("Asia/Jakarta"))

        for user_id, messages in user_messages.items():
            # Hanya analisis jika ada cukup pesan
            if len(messages) < 3:
                continue

            # Cek freshness — jangan analisis ulang profil yang baru saja diperbarui
            existing = self.profiles.get(user_id, {})
            last_updated_str = existing.get("last_updated", "")
            if last_updated_str:
                try:
                    last_dt = datetime.strptime(last_updated_str, "%Y-%m-%d %H:%M:%S WIB")
                    last_dt = last_dt.replace(tzinfo=ZoneInfo("Asia/Jakarta"))
                    hours_since = (now - last_dt).total_seconds() / 3600
                    if hours_since < 20:
                        logger.debug(f"[Micro-RAG] Profil {user_id} masih fresh (%.1f jam lalu), skip.", hours_since)
                        continue
                except ValueError:
                    pass  # format tanggal tidak dikenal → tetap analisis

            logger.info(f"[Micro-RAG] Menganalisis user {user_id}...")
            profile = await self._generate_profile(user_id, messages)
            if profile:
                self.profiles[user_id] = profile

        self._save_profiles()
        logger.info("[Micro-RAG] Analisis profil selesai.")

    async def _generate_profile(self, user_id: str, messages: List[str]) -> Optional[Dict]:
        """Meminta AI untuk merangkum kepribadian berdasarkan pesan."""
        chat_sample = "\n".join(messages[-20:])  # ambil 20 pesan terakhir

        prompt = f"""Analisis riwayat percakapan berikut dan buatlah profil kepribadian singkat untuk user dengan ID {user_id}.

Riwayat Percakapan:
{chat_sample}

Tugasmu:
1. Simpulkan kepribadiannya (misal: ramah, pemarah, melankolis, ceria).
2. Identifikasi minat atau hobi yang sering dibahas (misal: novel, coding, musik). Format HARUS berupa list/array.
3. Berikan ringkasan suasana hati (mood) mereka belakangan ini.

Output HARUS dalam format JSON murni:
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
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )

            # Validasi response Groq — cegah IndexError jika choices kosong
            if not completion.choices:
                logger.warning(f"[Micro-RAG] Groq return 0 choices untuk user {user_id}. Skip.")
                return None

            content = completion.choices[0].message.content
            if not content or not content.strip():
                logger.warning(f"[Micro-RAG] Groq return konten kosong untuk user {user_id}. Skip.")
                return None

            try:
                analysis = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"[Micro-RAG] JSON tidak valid dari Groq untuk {user_id}: {e}\nContent: {content[:200]}")
                return None

            # Tambahkan metadata manusiawi
            now = datetime.now(ZoneInfo("Asia/Jakarta"))
            existing_profile = self.profiles.get(user_id, {})
            current_exp = existing_profile.get("exp", 0) + 10  # tambah EXP setiap analisis

            return {
                "user_id": user_id,
                "personality": str(analysis.get("personality", "Misterius")),
                "interests": self._normalize_list(analysis.get("interests")),
                "mood_summary": str(analysis.get("mood_summary", "Stabil")),
                "notable_facts": self._normalize_list(analysis.get("notable_facts")),
                "exp": current_exp,
                "last_updated": now.strftime("%Y-%m-%d %H:%M:%S WIB"),
                "human_meta": f"Profil ini diperbarui pada {now.strftime('%A, %d %B %Y')} pukul {now.strftime('%H:%M')}.",
            }
        except Exception as e:
            logger.error(f"[Micro-RAG] Gagal generate profil untuk {user_id}: {e}")
            return None

    @staticmethod
    def _normalize_list(value, fallback=None) -> list:
        """Pastikan nilai selalu berupa list of strings.
        
        AI (Groq) kadang mengembalikan string CSV ("musik, coding") 
        alih-alih list. Normalisasi di sini mencegah crash saat join().
        """
        if isinstance(value, list):
            return [str(v) for v in value if v]
        if isinstance(value, str) and value.strip():
            return [v.strip() for v in value.split(",") if v.strip()]
        return fallback or []

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
