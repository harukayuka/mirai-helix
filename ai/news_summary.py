import json
import os
import time
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Import konfigurasi dari config.py
from config import (
    GEMINI_MODEL, GEMINI_API_VERSION, MAX_RETRIES,
    REQUEST_TIMEOUT, GENERATE_DEADLINE,
    TEMPERATURE, MAX_OUTPUT_TOKENS, TOP_P,
    MAX_KEY_WAIT, KEY_COOLDOWN_DURATION,
    NEWS_SOURCE_URL, NEWS_JSON_PATH,
    NEWS_SUMMARY_PATH, NEWS_REFRESH_SECONDS,
    NEWS_MAX_ITEMS, NEWS_MAX_CHARS
)

# Load API keys dari .env
load_dotenv()
GEMINI_KEYS = [k.strip() for k in os.getenv("GEMINI_KEYS", "").split(",") if k.strip()]
if not GEMINI_KEYS:
    raise ValueError("❌ Tidak ada GEMINI_KEYS di .env!")

# Setup logger
from utils.logger import setup_logging
logger = setup_logging()

# URL dasar Gemini API
BASE_URL = f"https://generativelanguage.googleapis.com/{GEMINI_API_VERSION}/models"

# Fungsi utilitas
def _resolve_data_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else Path(__file__).resolve().parent.parent / path

def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

# Fungsi unduh berita
def _download_news(url: str, dest: Path) -> None:
    logger.info("[NEWS] Mengunduh berita.json dari %s", url)
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Download gagal, HTTP {resp.status_code}: {resp.text[:200]}")
    _ensure_parent(dest)
    dest.write_bytes(resp.content)
    logger.info("[NEWS] Berhasil disimpan ke %s", dest)

def _load_news_json(path: Path) -> Any:
    should_download = not path.exists()
    if path.exists():
        file_age = time.time() - path.stat().st_mtime
        should_download = file_age >= NEWS_REFRESH_SECONDS
        if should_download:
            logger.info("[NEWS] File berita.json sudah %d detik, mengunduh ulang...", file_age)
    if should_download:
        _download_news(NEWS_SOURCE_URL, path)
    return json.loads(path.read_text(encoding="utf-8"))

def _pick_items(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("items", "data", "berita", "news", "result"):
            if isinstance(data.get(key), list):
                return [x for x in data[key] if isinstance(x, dict)]
        return [data]
    return []

def _extract_fields(item: Dict[str, Any]) -> Tuple[str, str, str]:
    title = str(item.get("title") or item.get("judul") or "").strip()
    url = str(item.get("url") or item.get("link") or "").strip()
    content = str(item.get("content") or item.get("summary") or "").strip()
    return title, content, url

def _build_context(items: List[Dict[str, Any]]) -> str:
    chunks = []
    total_chars = 0
    for idx, item in enumerate(items, start=1):
        title, content, url = _extract_fields(item)
        if not title and not content:
            continue
        entry = f"{idx}. {title} ({url})\n{content[:200]}..." if url else f"{idx}. {title}\n{content[:200]}..."
        if total_chars + len(entry) > NEWS_MAX_CHARS:
            break
        chunks.append(entry)
        total_chars += len(entry)
        if len(chunks) >= NEWS_MAX_ITEMS:
            break
    return "\n\n".join(chunks)

def _build_prompt(context: str) -> str:
    return (
        "Tugasmu adalah merangkum berita berikut dalam format yang mudah dipahami bot.\n"
        "Gunakan format sederhana tanpa gaya bahasa khusus.\n\n"
        "Berikut kumpulan berita:\n"
        f"{context}\n\n"
        "Format output:\n"
        "1) Ringkasan berita dalam 10-30 poin singkat.\n"
        "2) Sumber (daftar link atau nama media).\n"
        "3) Gunakan format JSON tanpa markdown.\n"
    )

# Gemini API Client
class GeminiSummaryClient:
    def __init__(self, api_keys: List[str] = GEMINI_KEYS):
        self.api_keys = api_keys
        self.current_index = 0
        self.key_status = {k: {"cooldown_until": 0} for k in api_keys}

    def _get_next_available_key(self) -> Optional[str]:
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

    def generate(self, prompt: str) -> str:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": TEMPERATURE,
                "maxOutputTokens": 4096,
                "topP": TOP_P,
            }
        }

        deadline = time.time() + GENERATE_DEADLINE
        for attempt in range(MAX_RETRIES):
            if time.time() > deadline:
                logger.error("[GENERATE] Deadline %ss tercapai, berhenti paksa.", GENERATE_DEADLINE)
                return ""

            api_key = self._get_next_available_key()
            if not api_key:
                return ""

            url = f"{BASE_URL}/{GEMINI_MODEL}:generateContent?key={api_key}"
            try:
                logger.info("[GEMINI] Mengirim permintaan ke Gemini API (Attempt %s/%s)", attempt + 1, MAX_RETRIES)
                response = requests.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=REQUEST_TIMEOUT
                )

                if response.status_code == 429:
                    logger.warning("[GEMINI] Rate limit tercapai, cooldown %ss", KEY_COOLDOWN_DURATION)
                    self.key_status[api_key]["cooldown_until"] = time.time() + KEY_COOLDOWN_DURATION
                    continue

                if response.status_code != 200:
                    logger.error("[GEMINI] HTTP %s: %s", response.status_code, response.text[:400])
                    wait = min(2 ** attempt, 30)
                    logger.info("[GEMINI] Tunggu %ss sebelum retry...", wait)
                    time.sleep(wait)
                    continue

                data = response.json()
                if not data.get("candidates"):
                    logger.warning("[GEMINI] Respons kosong: %s", data)
                    return ""

                candidate = data["candidates"][0]
                finish_reason = candidate.get("finishReason", "UNKNOWN")
                if finish_reason in ["SAFETY", "RECITATION"]:
                    logger.warning("[GEMINI] Respons terblokir: %s", finish_reason)
                    return ""

                generated_text = "".join(part.get("text", "") for part in candidate.get("content", {}).get("parts", []))
                return generated_text.strip()

            except requests.exceptions.Timeout:
                logger.warning("[GEMINI] Timeout (Attempt %s/%s)", attempt + 1, MAX_RETRIES)
                wait = min(2 ** attempt, 30)
                time.sleep(wait)
                continue
            except Exception as e:
                logger.exception("[GEMINI] Error: %s", e)
                wait = min(2 ** attempt, 30)
                time.sleep(wait)
                continue

        return ""

# Fungsi utama
def run_summary() -> Path:
    news_path = _resolve_data_path(NEWS_JSON_PATH)
    raw = _load_news_json(news_path)
    items = _pick_items(raw)
    if not items:
        raise RuntimeError("Tidak ada item berita yang ditemukan.")
    
    context = _build_context(items)
    if not context:
        raise RuntimeError("Konteks berita kosong setelah diproses.")
    
    prompt = _build_prompt(context)
    gemini = GeminiSummaryClient()
    response = gemini.generate(prompt)
    
    summary_path = _resolve_data_path(NEWS_SUMMARY_PATH)
    _ensure_parent(summary_path)
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_url": NEWS_SOURCE_URL,
        "item_count": len(items),
        "summary": response,
    }
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("[NEWS] Ringkasan berita berhasil disimpan ke %s", summary_path)
    return summary_path

if __name__ == "__main__":
    try:
        path = run_summary()
        print(f"✅ Ringkasan berhasil disimpan: {path}")
    except Exception as err:
        logger.exception("[NEWS] Gagal membuat ringkasan: %s", err)
        print(f"❌ Kesalahan: {err}")
