import json
import os
import time
import requests
import feedparser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Import konfigurasi dari config.py
from config import (
    GEMINI_MODEL, GEMINI_API_VERSION, MAX_RETRIES,
    REQUEST_TIMEOUT, GENERATE_DEADLINE,
    TEMPERATURE, MAX_OUTPUT_TOKENS, TOP_P,
    MAX_KEY_WAIT, KEY_COOLDOWN_DURATION,
    NEWS_SUMMARY_PATH, NEWS_REFRESH_SECONDS
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

# Daftar RSS Feed Media Indonesia (10 Media)
RSS_FEEDS = {
    "Antara News": "https://www.antaranews.com/rss/top-news",
    "Tempo": "https://rss.tempo.co/nasional",
    "CNN Indonesia": "https://www.cnnindonesia.com/nasional/rss",
    "Republika": "https://www.republika.co.id/rss",
    "Okezone": "https://www.okezone.com/rss/index.xml",
    "Sindonews": "https://www.sindonews.com/rss",
    "Inews": "https://www.inews.id/feed/news",
    "Tribunnews": "https://www.tribunnews.com/rss",
    "Kumparan": "https://lapi.kumparan.com/v1.0/rss/",
    "BBC Indonesia": "https://www.bbc.com/indonesia/index.xml"
}

def _resolve_data_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else Path(__file__).resolve().parent.parent / path

def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

def _fetch_rss_news() -> List[Dict[str, str]]:
    """Mengambil 2 berita terbaru dari setiap media di RSS_FEEDS."""
    all_news = []
    for media_name, url in RSS_FEEDS.items():
        try:
            logger.info(f"[RSS] Mengambil berita dari {media_name}...")
            feed = feedparser.parse(url)
            # Ambil maksimal 2 berita per media
            entries = feed.entries[:2]
            for entry in entries:
                all_news.append({
                    "source": media_name,
                    "title": entry.get("title", "No Title"),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", entry.get("description", ""))[:300]
                })
            logger.info(f"[RSS] Berhasil mengambil {len(entries)} berita dari {media_name}")
        except Exception as e:
            logger.error(f"[RSS] Gagal mengambil berita dari {media_name}: {e}")
    return all_news

def _build_prompt(news_list: List[Dict[str, str]]) -> str:
    context = ""
    for idx, item in enumerate(news_list, start=1):
        context += f"{idx}. [{item['source']}] {item['title']}\n   Link: {item['link']}\n   Ringkasan: {item['summary']}\n\n"
    
    return (
        "Tugasmu adalah merangkum berita-berita terkini berikut dalam format yang padat dan informatif untuk asisten AI bernama Mirai.\n"
        "Mirai adalah asisten kesehatan, jadi jika ada berita kesehatan, berikan penekanan lebih.\n\n"
        "Berikut kumpulan berita:\n"
        f"{context}\n\n"
        "Format output:\n"
        "1) Ringkasan berita dalam poin-poin singkat (maksimal 20 poin).\n"
        "2) Kelompokkan berdasarkan topik jika memungkinkan.\n"
        "3) Sebutkan sumber medianya di setiap poin.\n"
        "4) Gunakan gaya bahasa yang ramah namun profesional.\n"
    )

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
                logger.info("[GEMINI] Mengirim permintaan ringkasan berita (Attempt %s/%s)", attempt + 1, MAX_RETRIES)
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
                    time.sleep(wait)
                    continue

                data = response.json()
                if not data.get("candidates"):
                    return ""

                candidate = data["candidates"][0]
                if candidate.get("finishReason") in ["SAFETY", "RECITATION"]:
                    return ""

                generated_text = "".join(part.get("text", "") for part in candidate.get("content", {}).get("parts", []))
                return generated_text.strip()

            except Exception as e:
                logger.exception("[GEMINI] Error: %s", e)
                time.sleep(min(2 ** attempt, 30))
                continue

        return ""

def run_summary() -> Path:
    """Fungsi utama untuk mengambil RSS dan merangkum berita."""
    news_list = _fetch_rss_news()
    if not news_list:
        raise RuntimeError("Gagal mengambil berita dari semua RSS feed.")
    
    prompt = _build_prompt(news_list)
    gemini = GeminiSummaryClient()
    response = gemini.generate(prompt)
    
    if not response:
        raise RuntimeError("Gagal mendapatkan ringkasan dari Gemini.")
    
    summary_path = _resolve_data_path(NEWS_SUMMARY_PATH)
    _ensure_parent(summary_path)
    
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "item_count": len(news_list),
        "summary": response,
        "sources": list(RSS_FEEDS.keys())
    }
    
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("[NEWS] Ringkasan RSS berhasil disimpan ke %s", summary_path)
    return summary_path

if __name__ == "__main__":
    try:
        path = run_summary()
        print(f"✅ Ringkasan RSS berhasil disimpan: {path}")
    except Exception as err:
        logger.exception("[NEWS] Gagal membuat ringkasan RSS: %s", err)
        print(f"❌ Kesalahan: {err}")
