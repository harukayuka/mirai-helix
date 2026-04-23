import json
import os
import time
import feedparser
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from groq import Groq

# Import konfigurasi dari config.py
from config import (
    TEMPERATURE, NEWS_SUMMARY_PATH
)

# Load API keys dari .env
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Setup logger
from utils.logger import setup_logging
logger = setup_logging()

# Konfigurasi Groq
GROQ_MODEL = "llama-3.1-8b-instant"

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
            # Ambil RSS dengan timeout agar tidak menggantung
            import requests
            resp = requests.get(url, headers={"User-Agent": "MiraiBot/1.0"}, timeout=10)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
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

class GroqSummaryClient:
    def __init__(self, api_key: Optional[str] = GROQ_API_KEY):
        if not api_key:
            raise ValueError("❌ GROQ_API_KEY tidak ditemukan di .env!")
        self.client = Groq(api_key=api_key)

    def generate(self, prompt: str) -> str:
        try:
            logger.info(f"[GROQ] Mengirim permintaan ringkasan berita menggunakan {GROQ_MODEL}")
            completion = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "Kamu adalah asisten yang ahli dalam merangkum berita Indonesia secara akurat dan informatif."},
                    {"role": "user", "content": prompt}
                ],
                temperature=TEMPERATURE,
                max_tokens=1024,
                top_p=1,
                stream=False,
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"[GROQ] Error saat generate ringkasan: {e}")
            return ""

def run_summary() -> Path:
    """Fungsi utama untuk mengambil RSS dan merangkum berita."""
    news_list = _fetch_rss_news()
    if not news_list:
        raise RuntimeError("Gagal mengambil berita dari semua RSS feed.")
    
    prompt = _build_prompt(news_list)
    
    # Gunakan Groq sebagai pengganti Gemini
    groq_client = GroqSummaryClient()
    response = groq_client.generate(prompt)
    
    if not response:
        raise RuntimeError("Gagal mendapatkan ringkasan dari Groq.")
    
    summary_path = _resolve_data_path(NEWS_SUMMARY_PATH)
    _ensure_parent(summary_path)
    
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "item_count": len(news_list),
        "summary": response,
        "sources": list(RSS_FEEDS.keys()),
        "model_used": GROQ_MODEL
    }
    
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("[NEWS] Ringkasan RSS berhasil disimpan ke %s menggunakan Groq", summary_path)
    return summary_path

if __name__ == "__main__":
    try:
        path = run_summary()
        print(f"✅ Ringkasan RSS berhasil disimpan: {path}")
    except Exception as err:
        logger.exception("[NEWS] Gagal membuat ringkasan RSS: %s", err)
        print(f"❌ Kesalahan: {err}")
