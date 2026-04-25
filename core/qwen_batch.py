import os
import json
import sys
# Tambahkan folder proyek (satu level di atas) ke sys.path agar import utils/* dapat ditemukan
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

import datetime
import asyncio
from pathlib import Path
import aiofiles
import discord
from discord import File
from utils.logger import setup_logging
# Import helper AI yang baru dipindahkan ke folder ai
from ai.qwen_client import ask_qwen
from core.module_manager import module_manager
from utils.cleanup import clean_old_reports

logger = setup_logging()

# -------------------------------------------------------------------------
# Konfigurasi & penyimpanan
# -------------------------------------------------------------------------
BASE_DIR = Path(__file__).parents[1]
USER_DIR = BASE_DIR / "data" / "qwen_user"
RESULT_DIR = BASE_DIR / "data" / "qwen_results"
CONFIG_PATH = BASE_DIR / "data" / "qwen_config.json"

USER_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)

def _load_config():
    default = {
        "enabled": module_manager.is_enabled("qwen"),
        "enabled_channels": [],  # ID channel yang dipantau
        "forced_delivery_channel_id": None,  # optional, paksa kirim ke channel ini
        "last_run": None,
        "auto_run": {
            "enabled": False,
            "hour": 0,
            "minute": 0,
            "delivery_channel_id": None
        }
    }
    
    if CONFIG_PATH.exists():
        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            # PERBAIKAN: Pastikan key 'auto_run' ada, jika tidak tambahkan default
            if "auto_run" not in loaded:
                loaded["auto_run"] = default["auto_run"]
                logger.info("Key 'auto_run' tidak ada di config, menambahkan default.")
                try:
                    CONFIG_PATH.write_text(json.dumps(loaded, indent=2), encoding="utf-8")
                except IOError as e:
                    logger.error("Gagal update config dengan auto_run: %s", e)
            return loaded
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Error membaca config Qwen: %s. Menggunakan default.", e)
            try:
                CONFIG_PATH.write_text(json.dumps(default, indent=2), encoding="utf-8")
            except IOError as e:
                logger.error("Gagal menulis config Qwen: %s", e)
            return default
    else:
        # File config belum ada, buat baru
        try:
            CONFIG_PATH.write_text(json.dumps(default, indent=2), encoding="utf-8")
        except IOError as e:
            logger.error("Gagal membuat config Qwen baru: %s", e)
        return default

def _save_config(cfg):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except IOError as e:
        logger.error("Gagal menyimpan config Qwen: %s", e)

config = _load_config()
_auto_run_task = None  # placeholder untuk task asyncio

# -------------------------------------------------------------------------
# Helper fungsi
# -------------------------------------------------------------------------
async def add_channel(channel_id: int) -> bool:
    """Tambah channel ke daftar pantauan. Return True bila ditambahkan."""
    if channel_id not in config["enabled_channels"]:
        config["enabled_channels"].append(channel_id)
        _save_config(config)
        return True
    return False

async def remove_channel(channel_id: int) -> bool:
    """Hapus channel dari daftar pantauan. Return True bila dihapus."""
    if channel_id in config["enabled_channels"]:
        config["enabled_channels"].remove(channel_id)
        _save_config(config)
        return True
    return False

def split_for_discord(text: str, limit: int = 1900):
    """Pecah teks panjang menjadi potongan <limit> karakter (tanpa memotong kata)."""
    lines = text.splitlines()
    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks

# -------------------------------------------------------------------------
# Penyimpanan pesan user (dipanggil dari event on_message di command.py)
# -------------------------------------------------------------------------
async def store_message(message: discord.Message):
    """Simpan pesan yang relevan ke file per‑user."""
    if message.author.bot:
        return
    
    try:
        user_file = USER_DIR / f"{message.author.id}.txt"
        line = f"{message.id}\t{message.channel.id}\t{message.created_at.isoformat()}\t{message.author.display_name}\t{message.content}\n"
        async with aiofiles.open(user_file, "a", encoding="utf-8") as f:
            await f.write(line)
    except IOError as e:
        logger.error("Gagal menyimpan pesan user %s: %s", message.author.id, e)
    except Exception as e:
        logger.exception("Error tak terduga saat menyimpan pesan: %s", e)

# -------------------------------------------------------------------------
# Proses batch utama
# -------------------------------------------------------------------------
async def process_batch(bot: discord.Client):
    """Kumpulkan semua file user, kirim ke Qwen, simpan & kirim hasil."""
    if not module_manager.is_enabled("qwen"):
        return {"status": "disabled"}

    # Kumpulkan semua pesan
    prompt_parts = []
    files = list(USER_DIR.glob("*.txt"))
    total_users = len(files)
    processed_users = 0
    retained_users = 0
    skipped_empty_users = 0
    
    try:
        for txt_file in files:
            try:
                content = txt_file.read_text(encoding="utf-8")
                if not content.strip():
                    skipped_empty_users += 1
                    continue
                prompt_parts.append(f"--- Pesan dari user {txt_file.stem} ---\n{content}")
            except IOError as e:
                logger.error("Gagal membaca file %s: %s", txt_file, e)
    except Exception as e:
        logger.exception("Error saat mengumpulkan pesan user: %s", e)
        return {"status": "error", "message": str(e)}

    if not prompt_parts:
        return {"status": "empty", "total_users": total_users}

    # Instruksi CBT/DBT
    system_msg = (
        "Berikan ringkasan terapeutik menggunakan pendekatan CBT dan DBT. "
        "Buat poin‑poin singkat, fokus pada validasi diri, reframing, "
        "dan saran suportif yang dapat dipraktikkan. "
        "Hasilkan dalam format teks (TXT) saja, tidak dalam embed atau markdown yang panjang."
    )
    full_prompt = system_msg + "\n\n" + "\n".join(prompt_parts)

    try:
        response = await ask_qwen(full_prompt)
    except Exception as e:
        logger.error("Error calling Qwen: %s", e)
        return {"status": "client_unavailable", "message": str(e)}

    # Simpan laporan
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = RESULT_DIR / f"qwen_report_{ts}.txt"
    try:
        result_file.write_text(response, encoding="utf-8")
    except IOError as e:
        logger.error("Gagal menyimpan laporan Qwen: %s", e)
        return {"status": "save_error", "message": str(e)}

    config["last_run"] = ts
    _save_config(config)

    # Tentukan channel tujuan (paksa atau default)
    delivery_id = config.get("forced_delivery_channel_id")
    target = None
    if delivery_id:
        target = bot.get_channel(int(delivery_id))
    else:
        # gunakan channel pertama yang ada di enabled_channels
        enabled = config.get("enabled_channels", [])
        if enabled:
            target = bot.get_channel(int(enabled[0]))

    if target:
        try:
            await target.send(file=File(result_file))
        except discord.Forbidden:
            logger.error("Tidak ada izin untuk mengirim file ke channel tujuan.")
        except discord.NotFound:
            logger.error("Channel tujuan tidak ditemukan.")
        except Exception as e:
            logger.exception("Error saat mengirim file hasil Qwen: %s", e)
    else:
        logger.warning("Tidak ada channel tujuan untuk kirim hasil Qwen.")

    # Hapus file user yang sudah diproses
    for txt_file in files:
        try:
            content = txt_file.read_text(encoding="utf-8")
            if not content.strip():
                txt_file.unlink()
                continue
            
            # Cek apakah file berhasil diproses
            if response:
                txt_file.unlink()  # Hapus file setelah diproses
                processed_users += 1
            else:
                retained_users += 1  # File disimpan untuk retry
        except IOError as e:
            logger.error("Gagal membaca/hapus file %s: %s", txt_file, e)

    return {
        "status": "completed",
        "result_file": str(result_file),
        "total_users": total_users,
        "processed_users": processed_users,
        "retained_users": retained_users,
        "skipped_empty_users": skipped_empty_users
    }

# -------------------------------------------------------------------------
# Auto‑run scheduler
# -------------------------------------------------------------------------
def set_auto_run(hour: int, minute: int, delivery_channel_id: int | None = None) -> bool:
    """Set konfigurasi auto‑run. Return True bila berhasil."""
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return False
    
    # PERBAIKAN: Gunakan .get() untuk menghindari KeyError jika 'auto_run' tidak ada
    cfg = config.get("auto_run", {
        "enabled": False,
        "hour": 0,
        "minute": 0,
        "delivery_channel_id": None
    })
    
    cfg.update({
        "enabled": True,
        "hour": hour,
        "minute": minute,
        "delivery_channel_id": delivery_channel_id
    })
    
    # Pastikan key 'auto_run' di-update di config utama
    config["auto_run"] = cfg
    
    _save_config(config)
    return True

def get_auto_run_config():
    return config.get("auto_run", {})

def start_auto_run(bot: discord.Client):
    """Mulai task asyncio yang menjalankan batch pada jam yang ditentukan."""
    global _auto_run_task
    if _auto_run_task and not _auto_run_task.done():
        return  # sudah berjalan

    async def _runner():
        while True:
            try:
                cfg = get_auto_run_config()
                if not cfg.get("enabled"):
                    await asyncio.sleep(60)  # cek kembali tiap menit
                    continue

                now = datetime.datetime.now()
                target_time = now.replace(hour=cfg["hour"], minute=cfg["minute"], second=0, microsecond=0)
                if now >= target_time:
                    # sudah lewat, tunggu sampai besok
                    target_time += datetime.timedelta(days=1)
                
                wait_seconds = (target_time - now).total_seconds()
                logger.info("[Qwen Auto-Run] Menunggu %.2f jam untuk batch processing.", wait_seconds / 3600)
                await asyncio.sleep(wait_seconds)
                await process_batch(bot)
            except asyncio.CancelledError:
                logger.info("[Qwen Auto-Run] Task dibatalkan.")
                break
            except Exception as e:
                logger.exception("[Qwen Auto-Run] Error: %s", e)
                await asyncio.sleep(60)  # tunggu 1 menit sebelum retry

    _auto_run_task = asyncio.create_task(_runner())
    return True

def stop_auto_run():
    global _auto_run_task
    if _auto_run_task:
        _auto_run_task.cancel()
        _auto_run_task = None
    return True

# -------------------------------------------------------------------------
# Tes prompt langsung (digunakan oleh /qwen test)
# -------------------------------------------------------------------------
async def run_test_prompt(prompt: str) -> dict:
    try:
        resp = await ask_qwen(prompt)
        return {"status": "completed", "response": resp}
    except Exception as e:
        logger.error("Error running test prompt: %s", e)
        return {"status": "invalid", "message": str(e)}

# -------------------------------------------------------------------------
# Forced channel handling
# -------------------------------------------------------------------------
def set_forced_channel(channel_id: int):
    config["forced_delivery_channel_id"] = channel_id
    _save_config(config)

def remove_forced_channel():
    config["forced_delivery_channel_id"] = None
    _save_config(config)

# Fungsi tambahan yang dibutuhkan main.py
def is_channel_enabled(channel_id: int) -> bool:
    """Cek apakah channel aktif untuk pemantauan."""
    return channel_id in config.get("enabled_channels", [])

async def collect_message(user_id: int, user_name: str, content: str, channel_id: int, 
                    channel_name: str = "", server_name: str = "", server_id: str = "",
                    attachment_context: str = "", timestamp=None):
    """Kumpulkan pesan untuk diproses nanti (async)."""
    try:
        file_path = USER_DIR / f"{user_id}.txt"
        line = f"{timestamp}\t{channel_id}\t{user_name}\t{content}\n"
        # gunakan aiofiles untuk operasi async
        import aiofiles
        async with aiofiles.open(file_path, "a", encoding="utf-8") as f:
            await f.write(line)
    except Exception as e:
        logger.error(f"Gagal collect message: {e}")

# Export yang dibutuhkan oleh command.py
__all__ = [
    "add_channel",
    "remove_channel",
    "store_message",
    "process_batch",
    "set_auto_run",
    "get_auto_run_config",
    "start_auto_run",
    "stop_auto_run",
    "run_test_prompt",
    "set_forced_channel",
    "remove_forced_channel",
    "split_for_discord",
    "config",
    "is_channel_enabled",
    "collect_message"
]