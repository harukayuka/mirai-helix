# ai/gemini.py - Klien Gemini API untuk Mirai
"""
GeminiClient untuk komunikasi dengan Google Gemini API.
Mendukung multiple API keys dengan automatic rotation dan cooldown management.
"""

import json
import os
import requests
import time
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict, Optional
from ai.time import get_wib_time
from ai.cuaca import BMKGClient
from config import (
    GEMINI_MODEL, GEMINI_API_VERSION, MAX_KEY_WAIT,
    TEMPERATURE, MAX_OUTPUT_TOKENS, TOP_P,
    MAX_RETRIES, REQUEST_TIMEOUT, GENERATE_DEADLINE, KEY_COOLDOWN_DURATION,
    NEWS_SUMMARY_PATH
)
from utils.logger import setup_logging

VALID_ROLES = {"user", "model", "assistant"}

load_dotenv()
logger = setup_logging()

BASE_URL = f"https://generativelanguage.googleapis.com/{GEMINI_API_VERSION}/models"

raw_keys = os.getenv("GEMINI_KEYS", "")
API_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

if not API_KEYS:
    raise ValueError("❌ Tidak ada GEMINI_KEYS di .env!")

# Load system prompt
PROMPT_PATH = Path(__file__).parent / "prompts" / "mirai_system_prompt.txt"
NEWS_SUMMARY_FILE = Path(NEWS_SUMMARY_PATH)

def load_mirai_prompt() -> str:
    """Load Mirai system prompt dari file."""
    if PROMPT_PATH.exists():
        try:
            content = PROMPT_PATH.read_text(encoding="utf-8").strip()
            if content:
                logger.info("[INFO] Loaded Mirai system prompt dari: %s", PROMPT_PATH)
                return content
        except Exception as e:
            logger.exception("[ERROR] Gagal baca prompt file: %s", e)
    
    logger.warning("[FALLBACK] Pakai prompt minimal Mirai")
    return """
Kamu adalah Mirai, asisten kesehatan dan pendamping emosional.
Dewasa, ramah, peka, profesional. Tidak pernah diagnosis atau resep obat.
Gaya bicara semi-informal Jakarta, hangat, sesekali keibuan ringan.
"""

MIRAI_SYSTEM_PROMPT = load_mirai_prompt()


def load_news_summary() -> str:
    """Load ringkasan berita dari summary.json untuk diinject ke system prompt."""
    try:
        if not NEWS_SUMMARY_FILE.exists():
            return ""
        raw = NEWS_SUMMARY_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        summary = str(data.get("summary", "")).strip()
        sources = data.get("sources", [])
        generated_at = str(data.get("generated_at", "")).strip()

        if not summary:
            return ""

        sources_text = ""
        if isinstance(sources, list) and sources:
            sources_text = "\nSumber: " + ", ".join(str(s).strip() for s in sources if str(s).strip())

        meta = f" (generated_at: {generated_at})" if generated_at else ""
        return f"\n\n[RINGKASAN BERITA TERKINI{meta}]\n{summary}{sources_text}\n"
    except Exception as err:
        logger.exception("[NEWS] Gagal membaca summary.json: %s", err)
        return ""

class GeminiClient:
    """Klien untuk Google Gemini API dengan key rotation dan cooldown management."""
    
    def __init__(self, api_keys: List[str] = API_KEYS, system_prompt: str = MIRAI_SYSTEM_PROMPT):
        """
        Initialize GeminiClient.
        
        Args:
            api_keys: List of Gemini API keys
            system_prompt: System prompt untuk Mirai
        """
        if not api_keys:
            raise ValueError("❌ Tidak ada API key.")
        self.api_keys = api_keys
        self.current_index = 0
        self.system_prompt = system_prompt
        self.key_status = {k: {"cooldown_until": 0} for k in api_keys}
        self.bmkg = BMKGClient()

    def _get_next_available_key(self) -> Optional[str]:
        """
        Cari API key yang tersedia, dengan batas waktu tunggu MAX_KEY_WAIT detik.
        
        Returns:
            str: Available API key, atau None jika semua key masih cooldown
        """
        start = self.current_index
        waited = 0
        while True:
            key = self.api_keys[self.current_index]
            if time.time() >= self.key_status[key]["cooldown_until"]:
                self.current_index = (self.current_index + 1) % len(self.api_keys)
                return key
            self.current_index = (self.current_index + 1) % len(self.api_keys)
            if self.current_index == start:
                if waited >= MAX_KEY_WAIT:
                    logger.warning("[KEY ROTATION] Semua key masih cooldown setelah %ss, menyerah.", MAX_KEY_WAIT)
                    return None
                logger.info("[KEY ROTATION] Semua key cooldown, tunggu 5s... (total waited: %ss)", waited)
                time.sleep(5)
                waited += 5

    def _parse_history(self, history: List[Dict]) -> List[Dict]:
        """
        Validasi dan normalisasi history untuk Gemini API.
        
        Args:
            history: Raw history dari memory
            
        Returns:
            List of validated history entries
        """
        contents = []
        for i, msg in enumerate(history):
            raw_role = msg.get("role", "")

            # Skip role yang tidak dikenal
            if raw_role not in VALID_ROLES:
                logger.warning("[HISTORY] Skip msg[%s]: role tidak valid '%s'", i, raw_role)
                continue

            role = "model" if raw_role in ("assistant", "model") else "user"
            text = ""

            # Normalisasi format parts vs content
            if "parts" in msg and isinstance(msg["parts"], list) and msg["parts"]:
                text = msg["parts"][0].get("text", "") if isinstance(msg["parts"][0], dict) else str(msg["parts"][0])
            elif "content" in msg:
                text = msg["content"] if isinstance(msg["content"], str) else ""

            text = text.strip()
            if not text:
                logger.warning("[HISTORY] Skip msg[%s]: text kosong (role=%s)", i, role)
                continue

            # Gemini tidak boleh 2 role sama berturutan
            if contents and contents[-1]["role"] == role:
                logger.warning("[HISTORY] Skip msg[%s]: consecutive role '%s' tidak diizinkan Gemini", i, role)
                continue

            contents.append({"role": role, "parts": [{"text": text}]})

        return contents

    def generate(
        self,
        history: List[Dict[str, str]],
        temperature: float = TEMPERATURE,
        max_output_tokens: int = MAX_OUTPUT_TOKENS,
        max_retries: int = MAX_RETRIES
    ) -> str:
        """
        Generate respons menggunakan Gemini API.
        
        Args:
            history: Chat history
            temperature: Kreativitas respons (0.0 - 1.0)
            max_output_tokens: Maksimal output tokens
            max_retries: Maksimal retry attempts
            
        Returns:
            str: Generated response
        """
        time_info = get_wib_time()
        
        # Cek apakah user bertanya tentang cuaca di pesan terakhir
        weather_context = ""
        if history and history[-1]["role"] == "user":
            last_msg = history[-1].get("parts", [{}])[0].get("text", "")
            if "cuaca" in last_msg.lower():
                loc_name = self.bmkg.extract_location_from_text(last_msg)
                if loc_name:
                    loc_code = self.bmkg.search_location_code(loc_name)
                    weather_raw = self.bmkg.get_weather_raw(loc_code)
                    if weather_raw:
                        weather_context = (
                            f"\n\n[DATA CUACA BMKG UNTUK {loc_name.upper()}]\n"
                            f"Lokasi: {weather_raw['lokasi']['desa']}, {weather_raw['lokasi']['kecamatan']}, {weather_raw['lokasi']['kotkab']}\n"
                            f"Prakiraan terdekat:\n"
                        )
                        for f in weather_raw['prakiraan']:
                            weather_context += f"- Jam {f['local_datetime']}: {f['weather_desc']}, Suhu {f['t']}°C, Kelembapan {f['hu']}%\n"
                        weather_context += "\nInstruksi: Sampaikan data cuaca di atas dengan gaya bicaramu yang ramah, dewasa, dan peduli sebagai Mirai. Jangan hanya sebutkan angka, tapi berikan saran kesehatan yang relevan (misal: sedia payung jika hujan, atau minum air jika panas)."

        news_context = load_news_summary()

        full_system_instruction = (
            self.system_prompt +
            f"\n\nInformasi waktu saat ini: {time_info}\n"
            "Gunakan informasi ini untuk menyesuaikan sapaan dan respons jika relevan secara alami." +
            weather_context +
            news_context
        )

        contents = self._parse_history(history)

        # Fallback kalau history kosong/semua invalid
        if not contents:
            logger.warning("[HISTORY] History kosong setelah validasi, pakai dummy message.")
            contents.append({"role": "user", "parts": [{"text": "Halo"}]})

        payload = {
            "system_instruction": {
                "parts": [{"text": full_system_instruction}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
                "topP": TOP_P,
            }
        }

        deadline = time.time() + GENERATE_DEADLINE

        for attempt in range(max_retries):
            if time.time() > deadline:
                logger.error("[GENERATE] Deadline %ss tercapai, berhenti paksa.", GENERATE_DEADLINE)
                return "⚠️ Maaf, responsnya terlalu lama. Coba lagi ya! 🙏"

            api_key = self._get_next_available_key()

            if api_key is None:
                return "⚠️ Semua API key lagi limit dan habis waktu tunggu. Coba lagi nanti ya."

            url = f"{BASE_URL}/{GEMINI_MODEL}:generateContent?key={api_key}"
            logger.info("[GENERATE] Attempt %s/%s | Key: %s...", attempt + 1, max_retries, api_key[:8])

            try:
                response = requests.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=REQUEST_TIMEOUT
                )

                if response.status_code == 429:
                    logger.warning("[429] Key %s... cooldown %ss", api_key[:8], KEY_COOLDOWN_DURATION)
                    self.key_status[api_key]["cooldown_until"] = time.time() + KEY_COOLDOWN_DURATION
                    continue

                if response.status_code != 200:
                    logger.error("[ERROR] HTTP %s: %s", response.status_code, response.text[:400])
                    if response.status_code == 400:
                        logger.debug("[DEBUG PAYLOAD] contents count: %s, roles: %s", len(contents), [c["role"] for c in contents])
                    # Exponential backoff: 2s, 4s, 8s, dst (max 30s)
                    wait = min(2 ** attempt, 30)
                    logger.info("[RETRY] Tunggu %ss sebelum retry...", wait)
                    time.sleep(wait)
                    continue

                data = response.json()

                if not data.get("candidates"):
                    logger.warning("[BLOCKED/EMPTY] Response: %s", data)
                    return "Maaf, aku nggak bisa merespons itu sekarang. Coba topik lain ya? 💙"

                candidate = data["candidates"][0]
                finish_reason = candidate.get("finishReason", "UNKNOWN")
                content = candidate.get("content", {})
                parts = content.get("parts", [])

                generated_text = "".join(part.get("text", "") for part in parts).strip()

                logger.info("[GENERATE] finish_reason=%s | text_len=%s", finish_reason, len(generated_text))

                # Cek SAFETY/RECITATION duluan sebelum cek text
                if finish_reason in ["SAFETY", "RECITATION"]:
                    logger.warning("[BLOCKED] finish_reason=%s", finish_reason)
                    return "Maaf, aku nggak bisa bahas itu karena alasan keamanan. 💙"

                if generated_text:
                    return generated_text

                return "Maaf, aku gagal merespons. Coba lagi ya? 🙏"

            except requests.exceptions.Timeout:
                logger.warning("[TIMEOUT] Attempt %s timeout setelah %ss", attempt + 1, REQUEST_TIMEOUT)
                wait = min(2 ** attempt, 30)
                time.sleep(wait)
                continue
            except Exception as e:
                logger.exception("[ERROR] Attempt %s: %s", attempt + 1, e)
                wait = min(2 ** attempt, 30)
                time.sleep(wait)
                continue

        return "⚠️ Semua API key lagi limit. Coba lagi nanti ya."

if __name__ == "__main__":
    client = GeminiClient()
    print(client.generate([{"role": "user", "content": "Halo"}]))
