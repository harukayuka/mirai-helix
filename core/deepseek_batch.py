import os
import json
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from openai import OpenAI
from dotenv import load_dotenv
from utils.logger import setup_logging
from core.module_manager import module_manager

load_dotenv()
logger = setup_logging()

# Konfigurasi
QWEN_API_KEY = os.getenv("QWEN_API_KEY")
QWEN_BASE_URL = "https://integrate.api.nvidia.com/v1"
USER_CHATS_DIR = Path("data/user_chats")
QWEN_CONFIG_PATH = Path("data/qwen_config.json")
RPM_LIMIT = 40
RPM_INTERVAL = 60 / RPM_LIMIT # Jeda antar request untuk menjaga RPM

class QwenBatchProcessor:
    """
    Mengelola pengumpulan chat per user dan pemrosesan batch terjadwal menggunakan Qwen-3.5.
    """
    def __init__(self):
        USER_CHATS_DIR.mkdir(parents=True, exist_ok=True)
        self.client = OpenAI(base_url=QWEN_BASE_URL, api_key=QWEN_API_KEY) if QWEN_API_KEY else None
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        if QWEN_CONFIG_PATH.exists():
            try:
                return json.loads(QWEN_CONFIG_PATH.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"[Qwen] Gagal memuat config: {e}")
        return {"enabled_channels": [], "last_run": None}

    def _save_config(self):
        QWEN_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            QWEN_CONFIG_PATH.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"[Qwen] Gagal menyimpan config: {e}")

    def add_channel(self, channel_id: int):
        if channel_id not in self.config["enabled_channels"]:
            self.config["enabled_channels"].append(channel_id)
            self._save_config()
            return True
        return False

    def remove_channel(self, channel_id: int):
        if channel_id in self.config["enabled_channels"]:
            self.config["enabled_channels"].remove(channel_id)
            self._save_config()
            return True
        return False

    def is_channel_enabled(self, channel_id: int) -> bool:
        return channel_id in self.config["enabled_channels"]

    def collect_message(self, user_id: int, user_name: str, message: str, channel_id: int):
        """Simpan pesan user ke file .txt per user jika channel aktif."""
        if not self.is_channel_enabled(channel_id) or not module_manager.is_enabled("qwen"):
            return

        file_path = USER_CHATS_DIR / f"{user_id}.txt"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {user_name}: {message}\n")
        except Exception as e:
            logger.error(f"[Qwen] Gagal menyimpan pesan user {user_id}: {e}")

    async def process_batch(self, bot):
        """Proses semua file chat user satu per satu dan kirim hasil ke channel."""
        if not self.client:
            logger.warning("[Qwen] API Key tidak ditemukan. Batch processing dibatalkan.")
            return

        if not module_manager.is_enabled("qwen"):
            logger.info("[Qwen] Modul dinonaktifkan. Batch processing dilewati.")
            return

        files = list(USER_CHATS_DIR.glob("*.txt"))
        if not files:
            logger.info("[Qwen] Tidak ada data chat untuk diproses.")
            return

        logger.info(f"[Qwen] Memulai pemrosesan batch untuk {len(files)} user...")

        for file_path in files:
            user_id = file_path.stem
            try:
                content = file_path.read_text(encoding="utf-8")
                if not content.strip():
                    continue

                # Generate analisis menggunakan Qwen
                analysis = await self._get_qwen_analysis(content)
                
                if analysis:
                    # Kirim ke channel yang di-enable (untuk sementara kirim ke channel pertama yang aktif)
                    # Idealnya kita simpan channel_id terakhir user mengirim pesan
                    if self.config["enabled_channels"]:
                        target_channel_id = self.config["enabled_channels"][0]
                        channel = bot.get_channel(target_channel_id)
                        if channel:
                            header = f"📊 **Laporan Analisis Harian Mirai (Qwen-3.5)**\nUser ID: <@{user_id}>\n"
                            await channel.send(header + analysis)
                            logger.info(f"[Qwen] Berhasil mengirim analisis untuk user {user_id}")
                        
                        # Hapus file setelah diproses agar tidak menumpuk
                        file_path.unlink()
                
                # Jeda untuk menjaga RPM
                await asyncio.sleep(RPM_INTERVAL)

            except Exception as e:
                logger.error(f"[Qwen] Gagal memproses user {user_id}: {e}")

        self.config["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save_config()
        logger.info("[Qwen] Pemrosesan batch selesai.")

    async def _get_qwen_analysis(self, chat_history: str) -> Optional[str]:
        """Panggil API Qwen untuk menganalisis riwayat chat."""
        prompt = f"""
        Analisis riwayat percakapan berikut dari perspektif psikologi CBT/DBT. 
        Berikan ringkasan kondisi emosional, pola pikir yang muncul, dan saran kesehatan mental yang relevan.
        Gunakan gaya bahasa Mirai (ramah, dewasa, empatik).

        Riwayat Percakapan:
        {chat_history}
        """

        try:
            # Menggunakan loop untuk menangani streaming jika diperlukan, 
            # tapi untuk batch kita ambil hasil akhirnya saja.
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="qwen/qwen3.5-397b-a17b",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.60,
                top_p=0.95,
                top_k=20,
                max_tokens=16384,
                presence_penalty=0,
                repetition_penalty=1,
                extra_body={"chat_template_kwargs": {"enable_thinking": True}}
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"[Qwen] API Error: {e}")
            return None

# Instance global
qwen_batch = QwenBatchProcessor()