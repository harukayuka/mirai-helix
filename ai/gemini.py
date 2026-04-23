# ai/gemini.py
"""Klien async untuk Google Gemini.

Fitur utama:
- Semaphore (max 3 concurrent requests)
- Circuit‑breaker (threshold 5×503, cooldown 30 s)
- Cache TTL 5 menit
- Rotasi API‑key dengan cooldown per key
- Dynamic temperature (lebih rendah untuk pertanyaan faktual)
- Sistem prompt + cuaca + ringkasan berita + konteks user

FIXED ISSUES:
- Improved async/await consistency
- Better error handling and logging
- Proper timeout handling
- Cleaner code structure
- Fixed potential race conditions
"""

import os
import json
import time
import asyncio
import aiohttp
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict, Optional, Tuple
from ai.time import get_wib_time
from ai.cuaca import BMKGClient
from config import (
    GEMINI_MODEL,
    GEMINI_API_VERSION,
    TEMPERATURE,
    MAX_OUTPUT_TOKENS,
    TOP_P,
    REQUEST_TIMEOUT,
    KEY_COOLDOWN_DURATION,
    NEWS_SUMMARY_PATH,
)
from utils.logger import setup_logging

load_dotenv()
logger = setup_logging()

# ----------------------------------------------------------------------
# 1️⃣  Prompt & ringkasan berita
# ----------------------------------------------------------------------
BASE_URL = f"https://generativelanguage.googleapis.com/{GEMINI_API_VERSION}/models"
PROMPT_PATH = Path(__file__).parent / "prompts" / "mirai_system_prompt.txt"
NEWS_SUMMARY_FILE = Path(NEWS_SUMMARY_PATH)

def _load_system_prompt() -> str:
    """Load system prompt from file with fallback."""
    if PROMPT_PATH.exists():
        try:
            txt = PROMPT_PATH.read_text(encoding="utf-8").strip()
            if txt:
                logger.info("[Gemini] Loaded system prompt from %s", PROMPT_PATH)
                return txt
        except Exception as e:
            logger.exception("[Gemini] Gagal baca system prompt: %s", e)
    
    logger.warning("[Gemini] Fallback system prompt (minimal).")
    return (
        "Kamu adalah Mirai, asisten kesehatan dan pendamping emosional. "
        "Dewasa, ramah, peka, profesional. Tidak memberi diagnosis atau resep. "
        "Gaya bicara semi‑informal Jakarta, hangat, sesekali keibuan."
    )

def _load_news_summary() -> str:
    """Load news summary from file with error handling."""
    try:
        if not NEWS_SUMMARY_FILE.exists():
            return ""
        
        data = json.loads(NEWS_SUMMARY_FILE.read_text(encoding="utf-8"))
        summary = str(data.get("summary", "")).strip()
        if not summary:
            return ""
        
        sources = data.get("sources", [])
        generated_at = str(data.get("generated_at", "")).strip()
        
        src_txt = ""
        if isinstance(sources, list) and sources:
            src_txt = "\nSumber: " + ", ".join(str(s).strip() for s in sources if str(s).strip())
        
        meta = f" (generated_at: {generated_at})" if generated_at else ""
        return f"\n\n[RINGKASAN BERITA TERKINI{meta}]\n{summary}{src_txt}\n"
    except Exception as e:
        logger.exception("[Gemini] Gagal baca news summary: %s", e)
        return ""

SYSTEM_PROMPT = _load_system_prompt()
NEWS_SUMMARY = _load_news_summary()

# ----------------------------------------------------------------------
# 2️⃣  Circuit‑breaker & semaphore
# ----------------------------------------------------------------------
_gemini_semaphore = asyncio.Semaphore(3)
_circuit_breaker_until = 0
_circuit_breaker_failures = 0
_circuit_breaker_lock = asyncio.Lock()  # FIXED: Added lock for thread safety
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_COOLDOWN = 30

async def _increase_503_counter():
    """Increase 503 failure counter with thread safety."""
    global _circuit_breaker_failures, _circuit_breaker_until
    async with _circuit_breaker_lock:
        _circuit_breaker_failures += 1
        if _circuit_breaker_failures >= CIRCUIT_BREAKER_THRESHOLD:
            _circuit_breaker_until = time.time() + CIRCUIT_BREAKER_COOLDOWN
            logger.critical(
                f"[CircuitBreaker] Aktif! Istirahat {CIRCUIT_BREAKER_COOLDOWN}s karena "
                f"{_circuit_breaker_failures}x 503 berturut‑turut."
            )

async def _reset_503_counter():
    """Reset 503 failure counter with thread safety."""
    global _circuit_breaker_failures
    async with _circuit_breaker_lock:
        _circuit_breaker_failures = 0

def _is_circuit_breaker_active() -> bool:
    """Check if circuit breaker is currently active."""
    return time.time() < _circuit_breaker_until

# ----------------------------------------------------------------------
# 3️⃣  GeminiClient (async)
# ----------------------------------------------------------------------
class GeminiClient:
    """Async client for Google Gemini API with advanced features."""
    
    _CACHE: dict = {}          # key → (timestamp, response)
    _CACHE_TTL = 300           # 5 menit
    _KEY_COOLDOWN: dict = {}   # api_key → timestamp kembali tersedia
    _cache_lock = asyncio.Lock()  # FIXED: Added lock for cache thread safety

    def __init__(self):
        raw_keys = os.getenv("GEMINI_KEYS", "")
        self.api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
        if not self.api_keys:
            raise ValueError("❌ Tidak ada GEMINI_KEYS di .env!")
        
        self.key_index = 0
        self.api_key = self.api_keys[0]
        self.endpoint = f"{BASE_URL}/{GEMINI_MODEL}:generateContent"
        self.bmkg = BMKGClient()
        self.system_prompt = SYSTEM_PROMPT
        self.news_summary = NEWS_SUMMARY
        logger.info(f"[Gemini] Initialized with {len(self.api_keys)} API key(s)")

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------
    def _make_cache_key(self, history: List[Dict], user_context: str, temperature: float) -> int:
        """Create cache key from request parameters."""
        try:
            payload = json.dumps(
                {"h": history, "c": user_context, "t": temperature}, 
                sort_keys=True
            )
            return hash(payload)
        except Exception as e:
            logger.warning(f"[Gemini] Failed to create cache key: {e}")
            return hash(str(time.time()))  # Fallback to time-based key

    async def _get_cached(self, key: int) -> Optional[str]:
        """Get cached response if still valid."""
        async with self._cache_lock:
            entry = self._CACHE.get(key)
            if entry:
                ts, val = entry
                if time.time() - ts < self._CACHE_TTL:
                    logger.debug("[Gemini] Cache hit")
                    return val
                # Expired cache entry
                self._CACHE.pop(key, None)
        return None

    async def _set_cached(self, key: int, val: str):
        """Store response in cache."""
        async with self._cache_lock:
            self._CACHE[key] = (time.time(), val)
            # FIXED: Clean old cache entries to prevent memory leak
            if len(self._CACHE) > 100:
                await self._clean_old_cache()

    async def _clean_old_cache(self):
        """Remove expired cache entries."""
        now = time.time()
        expired_keys = [
            k for k, (ts, _) in self._CACHE.items() 
            if now - ts >= self._CACHE_TTL
        ]
        for k in expired_keys:
            self._CACHE.pop(k, None)
        logger.debug(f"[Gemini] Cleaned {len(expired_keys)} expired cache entries")

    # ------------------------------------------------------------------
    # Simple fallback (jam / tanggal)
    # ------------------------------------------------------------------
    def _simple_response(self, history: List[Dict], user_context: str) -> Optional[str]:
        """Provide simple responses for time/date queries without API call."""
        for msg in reversed(history):
            if msg.get("role") == "user":
                txt = self._extract_text_from_message(msg)
                txt_lower = txt.lower()
                
                if "jam" in txt_lower and "berapa" in txt_lower:
                    return f"Sekarang jam {get_wib_time().strftime('%H:%M')} WIB."
                if "tanggal" in txt_lower or "hari ini" in txt_lower:
                    return f"Hari ini tanggal {get_wib_time().strftime('%d-%m-%Y')} WIB."
                break
        return None

    def _extract_text_from_message(self, msg: Dict) -> str:
        """Extract text content from message dict."""
        if "parts" in msg and isinstance(msg["parts"], list) and msg["parts"]:
            part = msg["parts"][0]
            return part.get("text", "") if isinstance(part, dict) else str(part)
        return msg.get("content", "")

    # ------------------------------------------------------------------
    # Dynamic temperature
    # ------------------------------------------------------------------
    def _smart_temperature(self, history: List[Dict]) -> float:
        """Adjust temperature based on query type."""
        for msg in reversed(history):
            if msg.get("role") == "user":
                txt = self._extract_text_from_message(msg).lower()
                
                # Lower temperature for factual questions
                factual_keywords = ["apa", "siapa", "berapa", "kapan", "jam", "tanggal", "dimana", "mengapa"]
                if any(kw in txt for kw in factual_keywords):
                    return 0.3
                break
        return TEMPERATURE

    # ------------------------------------------------------------------
    # Weather context
    # ------------------------------------------------------------------
    async def _get_weather_context(self, user_message: str) -> str:
        """Get weather context if user asks about weather."""
        if "cuaca" not in user_message.lower():
            return ""
        
        try:
            loc = self.bmkg.extract_location_from_text(user_message)
            if not loc:
                return ""
            
            code = self.bmkg.search_location_code(loc)
            if not code:
                return ""
            
            data = self.bmkg.get_weather_raw(code)
            if not data:
                return ""
            
            weather_ctx = (
                f"\n\n[DATA CUACA BMKG UNTUK {loc.upper()}]\n"
                f"Lokasi: {data['lokasi']['desa']}, {data['lokasi']['kecamatan']}, {data['lokasi']['kotkab']}\n"
                "Prakiraan terdekat:\n"
            )
            for f in data["prakiraan"]:
                weather_ctx += (
                    f"- Jam {f['local_datetime']}: {f['weather_desc']}, "
                    f"Suhu {f['t']}°C, Kelembapan {f['hu']}%\n"
                )
            weather_ctx += (
                "\nBerikan data di atas dengan gaya ramah Mirai, "
                "sertakan saran kesehatan bila relevan."
            )
            return weather_ctx
        except Exception as e:
            logger.warning(f"[Gemini] Failed to get weather context: {e}")
            return ""

    # ------------------------------------------------------------------
    # Build payload (system instruction + contents)
    # ------------------------------------------------------------------
    async def _build_payload(
        self, 
        history: List[Dict], 
        temperature: float, 
        user_context: str
    ) -> Dict:
        """Build API request payload."""
        # Get weather context if needed
        weather_ctx = ""
        if history and history[-1].get("role") == "user":
            last_msg = self._extract_text_from_message(history[-1])
            weather_ctx = await self._get_weather_context(last_msg)
        
        # Build full system instruction
        full_system = (
            self.system_prompt +
            f"\n\nInformasi waktu saat ini: {get_wib_time()}\n" +
            weather_ctx +
            self.news_summary +
            user_context
        )
        system_instruction = {"parts": [{"text": full_system}]}

        # Prepare conversation history (max 6 messages to save tokens)
        trimmed = history[-6:] if isinstance(history, list) else []
        contents = []
        
        for msg in trimmed:
            role = msg.get("role")
            if role == "assistant":
                role = "model"
            
            text = self._extract_text_from_message(msg)
            if text:
                contents.append({"role": role, "parts": [{"text": text}]})
        
        # Ensure at least one message
        if not contents:
            contents.append({"role": "user", "parts": [{"text": "Halo"}]})

        return {
            "system_instruction": system_instruction,
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": MAX_OUTPUT_TOKENS,
                "topP": TOP_P,
            },
        }

    # ------------------------------------------------------------------
    # API request with retry logic
    # ------------------------------------------------------------------
    async def _make_api_request(
        self, 
        payload: Dict, 
        attempt: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Make API request with current key.
        Returns (success: bool, response: Optional[str])
        """
        # Check if current key is in cooldown
        if (
            self.api_key in self._KEY_COOLDOWN and
            time.time() < self._KEY_COOLDOWN[self.api_key]
        ):
            return False, None
        
        params = {"key": self.api_key}
        
        try:
            async with _gemini_semaphore:
                timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                async with aiohttp.ClientSession(timeout=timeout) as sess:
                    async with sess.post(
                        self.endpoint,
                        params=params,
                        json=payload,
                    ) as resp:
                        # Handle 503 Service Unavailable
                        if resp.status == 503:
                            await _increase_503_counter()
                            logger.warning(f"[Gemini] 503 error with key #{self.key_index+1}")
                            await asyncio.sleep(min(2 ** attempt, 60))
                            return False, None
                        
                        # Handle client errors (4xx)
                        if 400 <= resp.status < 500:
                            txt = await resp.text()
                            logger.error(f"[Gemini] Client error {resp.status}: {txt}")
                            # Jangan cache error client, tandai gagal sehingga rotasi key
                            return False, None
                        
                        # Handle server errors (5xx) except 503
                        if resp.status >= 500:
                            txt = await resp.text()
                            logger.error(f"[Gemini] Server error {resp.status}: {txt}")
                            return False, None
                        
                        # Success - parse response
                        data = await resp.json()
                        await _reset_503_counter()
                        
                        candidates = data.get("candidates", [])
                        if not candidates:
                            return True, "[Gemini] Tidak ada kandidat dalam response."
                        
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if not parts:
                            return True, "[Gemini] Response kosong."
                        
                        text = "".join(p.get("text", "") for p in parts).strip()
                        return True, text
                        
        except asyncio.TimeoutError:
            logger.warning(f"[Gemini] Timeout dengan key #{self.key_index+1}")
            self._KEY_COOLDOWN[self.api_key] = time.time() + KEY_COOLDOWN_DURATION
            return False, None
        except Exception as e:
            logger.warning(f"[Gemini] Error dengan key #{self.key_index+1}: {e}")
            self._KEY_COOLDOWN[self.api_key] = time.time() + KEY_COOLDOWN_DURATION
            return False, None

    def _rotate_to_next_key(self):
        """Rotate to the next available API key, menunggu cooldown bila diperlukan."""
        self.key_index = (self.key_index + 1) % len(self.api_keys)
        self.api_key = self.api_keys[self.key_index]
        # Jika key baru masih dalam cooldown, tunggu hingga tersedia
        if self.api_key in self._KEY_COOLDOWN:
            wait = max(0, self._KEY_COOLDOWN[self.api_key] - time.time())
            if wait:
                logger.info(f"[Gemini] Menunggu {wait:.1f}s untuk key selanjutnya")
                time.sleep(wait)

    # ------------------------------------------------------------------
    # Public async generate
    # ------------------------------------------------------------------
    async def generate(
        self,
        history: List[Dict],
        temperature: float = TEMPERATURE,
        user_context: str = "",
    ) -> str:
        """
        Generate AI response from conversation history.
        
        Args:
            history: List of conversation messages
            temperature: Sampling temperature (0.0-1.0)
            user_context: Additional context about the user
            
        Returns:
            Generated response text
        """
        # Check circuit breaker
        if _is_circuit_breaker_active():
            logger.warning("[Gemini] Circuit breaker active, request blocked")
            return "[Gemini] Service overload, coba lagi nanti."

        # Try simple response for common queries
        quick = self._simple_response(history, user_context)
        if quick:
            logger.debug("[Gemini] Using quick response")
            return quick

        # Use dynamic temperature
        dyn_temp = self._smart_temperature(history)

        # Check cache
        cache_key = self._make_cache_key(history, user_context, dyn_temp)
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        # Build request payload
        payload = await self._build_payload(history, dyn_temp, user_context)

        # Try all API keys with retry logic
        attempts = 0
        max_attempts = len(self.api_keys) * 2  # Try each key twice
        
        while attempts < max_attempts:
            success, response = await self._make_api_request(payload, attempts)
            
            if success:
                # Got a response (either valid or error)
                if response:
                    await self._set_cached(cache_key, response)
                return response or "[Gemini] Response kosong."
            
            # Failed - rotate to next key
            self._rotate_to_next_key()
            attempts += 1

        # All keys failed
        await _increase_503_counter()
        logger.error("[Gemini] Semua API key gagal setelah semua attempts")
        return "[Gemini] Semua API key gagal, silakan coba lagi nanti."

    # ------------------------------------------------------------------
    # Convenience async methods
    # ------------------------------------------------------------------
    async def generate_welcome(self, user_name: str) -> str:
        """Generate welcome message for new member."""
        prompt = (
            f"Buatkan pesan sambutan hangat, ramah, dan sedikit puitis untuk member baru "
            f"bernama '{user_name}' yang baru bergabung di server Helix. "
            "Gunakan gaya bicara Mirai (dewasa, empati, semi‑informal Jakarta). "
            "Maksimal 3 kalimat."
        )
        return await self.generate([{"role": "user", "parts": [{"text": prompt}]}])

    async def generate_goodbye(self, user_name: str) -> str:
        """Generate goodbye message for leaving member."""
        prompt = (
            f"Buatkan pesan perpisahan menyentuh dan penuh doa untuk member "
            f"bernama '{user_name}' yang meninggalkan server Helix. "
            "Gunakan gaya Mirai (dewasa, empati, hangat). "
            "Maksimal 3 kalimat."
        )
        return await self.generate([{"role": "user", "parts": [{"text": prompt}]}])

# ----------------------------------------------------------------------
# Test block (debug)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    async def _test():
        client = GeminiClient()
        res = await client.generate([{"role": "user", "content": "Halo"}])
        print(res)
    asyncio.run(_test())