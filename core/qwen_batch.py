"""
core/qwen_batch.py  (v2 — DeepSeek-R1 via NVIDIA NIM)
──────────────────────────────────────────────────────
Modul batch processing yang sebelumnya memakai Qwen, sekarang diganti ke DeepSeek-R1.
Nama file dipertahankan agar kompatibel dengan import di command.py dan scheduler.

Bugs yang diperbaiki vs versi lama:
  1. Import ask_qwen -> ask_deepseek (module key juga diganti ke "deepseek")
  2. process_batch: loop penghapusan pakai tracked valid_files (tidak re-read)
  3. process_batch: cek `if response is not None` bukan `if response:`
  4. collect_message: import aiofiles dipindah ke top-level
  5. _load_config: key "deepseek" konsisten dengan module_manager
  6. start_auto_run: pakai asyncio.ensure_future (safe inside running loop)
"""

import os
import sys
import json
import datetime
import asyncio
from pathlib import Path

import aiofiles
import discord
from discord import File
from utils.logger import setup_logging

from ai.deepseek_client import ask_deepseek, ask_qwen, THINK_MODE_HIGH  # V4 Pro
from core.module_manager import module_manager
from utils.cleanup import clean_old_reports

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

logger = setup_logging()

BASE_DIR    = Path(__file__).parents[1]
USER_DIR    = BASE_DIR / "data" / "deepseek_user"
RESULT_DIR  = BASE_DIR / "data" / "deepseek_results"
CONFIG_PATH = BASE_DIR / "data" / "deepseek_config.json"

USER_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)

_MODULE_KEY = "deepseek"


def _default_config() -> dict:
    return {
        "enabled":                    module_manager.is_enabled(_MODULE_KEY),
        "enabled_channels":           [],
        "forced_delivery_channel_id": None,
        "last_run":                   None,
        "auto_run": {
            "enabled":             False,
            "hour":                0,
            "minute":              0,
            "delivery_channel_id": None,
        },
    }


def _load_config() -> dict:
    default = _default_config()
    old_path = BASE_DIR / "data" / "qwen_config.json"

    if CONFIG_PATH.exists():
        source = CONFIG_PATH
    elif old_path.exists():
        source = old_path
        logger.info("[DeepSeek] Migrasi config dari qwen_config.json")
    else:
        source = None

    if source:
        try:
            loaded: dict = json.loads(source.read_text(encoding="utf-8"))
            if "auto_run" not in loaded:
                loaded["auto_run"] = default["auto_run"]
            CONFIG_PATH.write_text(json.dumps(loaded, indent=2), encoding="utf-8")
            return loaded
        except (json.JSONDecodeError, IOError) as e:
            logger.error("[DeepSeek] Error membaca config: %s. Gunakan default.", e)

    try:
        CONFIG_PATH.write_text(json.dumps(default, indent=2), encoding="utf-8")
    except IOError as e:
        logger.error("[DeepSeek] Gagal tulis config baru: %s", e)

    return default


def _save_config(cfg: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except IOError as e:
        logger.error("[DeepSeek] Gagal simpan config: %s", e)


config = _load_config()
_auto_run_task: asyncio.Task | None = None


async def add_channel(channel_id: int) -> bool:
    if channel_id not in config["enabled_channels"]:
        config["enabled_channels"].append(channel_id)
        _save_config(config)
        return True
    return False


async def remove_channel(channel_id: int) -> bool:
    if channel_id in config["enabled_channels"]:
        config["enabled_channels"].remove(channel_id)
        _save_config(config)
        return True
    return False


def is_channel_enabled(channel_id: int) -> bool:
    return channel_id in config.get("enabled_channels", [])


def split_for_discord(text: str, limit: int = 1900) -> list:
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


async def store_message(message: discord.Message) -> None:
    if message.author.bot:
        return
    try:
        user_file = USER_DIR / f"{message.author.id}.txt"
        line = (
            f"{message.id}\t{message.channel.id}\t"
            f"{message.created_at.isoformat()}\t"
            f"{message.author.display_name}\t{message.content}\n"
        )
        async with aiofiles.open(user_file, "a", encoding="utf-8") as f:
            await f.write(line)
    except IOError as e:
        logger.error("[DeepSeek] Gagal simpan pesan user %s: %s", message.author.id, e)
    except Exception as e:
        logger.exception("[DeepSeek] Error menyimpan pesan: %s", e)


async def collect_message(
    user_id: int,
    user_name: str,
    content: str,
    channel_id: int,
    channel_name: str = "",
    server_name: str = "",
    server_id: str = "",
    attachment_context: str = "",
    timestamp=None,
) -> None:
    try:
        file_path = USER_DIR / f"{user_id}.txt"
        ts = timestamp or datetime.datetime.utcnow().isoformat()
        line = f"{ts}\t{channel_id}\t{user_name}\t{content}\n"
        async with aiofiles.open(file_path, "a", encoding="utf-8") as f:
            await f.write(line)
    except Exception as e:
        logger.error("[DeepSeek] Gagal collect message user %s: %s", user_id, e)


async def process_batch(bot: discord.Client) -> dict:
    if not module_manager.is_enabled(_MODULE_KEY):
        return {"status": "disabled"}

    files = list(USER_DIR.glob("*.txt"))
    total_users = len(files)

    prompt_parts = []
    valid_files = []

    for txt_file in files:
        try:
            content = txt_file.read_text(encoding="utf-8")
            if content.strip():
                prompt_parts.append(f"--- Pesan dari user {txt_file.stem} ---\n{content}")
                valid_files.append(txt_file)
        except IOError as e:
            logger.error("[DeepSeek] Gagal baca %s: %s", txt_file, e)

    if not prompt_parts:
        return {"status": "empty", "total_users": total_users}

    system_msg = (
        "Berikan ringkasan terapeutik menggunakan pendekatan CBT dan DBT. "
        "Buat poin-poin singkat, fokus pada validasi diri, reframing, "
        "dan saran suportif yang dapat dipraktikkan. "
        "Hasilkan dalam format teks (TXT) saja, tidak dalam embed atau markdown panjang."
    )

    try:
        response = await ask_deepseek(
            "\n\n".join(prompt_parts),
            system_prompt=system_msg,
            think_mode=THINK_MODE_HIGH,  # reasoning mode untuk CBT/DBT analysis
            max_tokens=8192,
            timeout_seconds=180,
        )
    except Exception as e:
        logger.error("[DeepSeek] Error panggil API: %s", e)
        return {"status": "client_unavailable", "message": str(e)}

    # BUGFIX: cek None bukan falsy
    if response is None:
        return {"status": "client_unavailable", "message": "API mengembalikan None."}

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = RESULT_DIR / f"deepseek_report_{ts}.txt"
    try:
        result_file.write_text(response, encoding="utf-8")
    except IOError as e:
        logger.error("[DeepSeek] Gagal simpan laporan: %s", e)
        return {"status": "save_error", "message": str(e)}

    config["last_run"] = ts
    _save_config(config)

    delivery_id = config.get("forced_delivery_channel_id")
    target = None
    if delivery_id:
        target = bot.get_channel(int(delivery_id))
    else:
        enabled = config.get("enabled_channels", [])
        if enabled:
            target = bot.get_channel(int(enabled[0]))

    if target:
        try:
            await target.send(file=File(result_file))
        except discord.Forbidden:
            logger.error("[DeepSeek] Tidak ada izin kirim ke channel.")
        except discord.NotFound:
            logger.error("[DeepSeek] Channel tidak ditemukan.")
        except Exception as e:
            logger.exception("[DeepSeek] Error kirim laporan: %s", e)
    else:
        logger.warning("[DeepSeek] Tidak ada channel tujuan.")

    # BUGFIX: hapus hanya valid_files yang sudah diproses, tanpa re-read
    processed_users = 0
    for txt_file in valid_files:
        try:
            txt_file.unlink()
            processed_users += 1
        except FileNotFoundError:
            logger.warning("[DeepSeek] File sudah tidak ada: %s", txt_file)
        except IOError as e:
            logger.error("[DeepSeek] Gagal hapus file %s: %s", txt_file, e)

    try:
        clean_old_reports(str(RESULT_DIR))
    except Exception as e:
        logger.warning("[DeepSeek] Gagal bersihkan laporan lama: %s", e)

    return {
        "status":              "completed",
        "result_file":         str(result_file),
        "total_users":         total_users,
        "processed_users":     processed_users,
        "skipped_empty_users": total_users - len(valid_files),
    }


def set_auto_run(hour: int, minute: int, delivery_channel_id=None) -> bool:
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return False
    cfg = config.get("auto_run", {
        "enabled": False, "hour": 0, "minute": 0, "delivery_channel_id": None
    })
    cfg.update({"enabled": True, "hour": hour, "minute": minute,
                "delivery_channel_id": delivery_channel_id})
    config["auto_run"] = cfg
    _save_config(config)
    return True


def get_auto_run_config() -> dict:
    return config.get("auto_run", {})


def start_auto_run(bot: discord.Client) -> bool:
    global _auto_run_task
    if _auto_run_task and not _auto_run_task.done():
        return True

    async def _runner():
        while True:
            try:
                cfg = get_auto_run_config()
                if not cfg.get("enabled"):
                    await asyncio.sleep(60)
                    continue
                now = datetime.datetime.now()
                target_time = now.replace(
                    hour=cfg["hour"], minute=cfg["minute"], second=0, microsecond=0
                )
                if now >= target_time:
                    target_time += datetime.timedelta(days=1)
                wait_seconds = (target_time - now).total_seconds()
                logger.info("[DeepSeek Auto-Run] Menunggu %.2f jam.", wait_seconds / 3600)
                await asyncio.sleep(wait_seconds)
                await process_batch(bot)
            except asyncio.CancelledError:
                logger.info("[DeepSeek Auto-Run] Task dibatalkan.")
                break
            except Exception as e:
                logger.exception("[DeepSeek Auto-Run] Error: %s", e)
                await asyncio.sleep(60)

    _auto_run_task = asyncio.ensure_future(_runner())
    return True


def stop_auto_run() -> bool:
    global _auto_run_task
    if _auto_run_task:
        _auto_run_task.cancel()
        _auto_run_task = None
    return True


def set_forced_channel(channel_id: int) -> None:
    config["forced_delivery_channel_id"] = channel_id
    _save_config(config)


def remove_forced_channel() -> None:
    config["forced_delivery_channel_id"] = None
    _save_config(config)


async def run_test_prompt(prompt: str) -> dict:
    try:
        resp = await ask_deepseek(prompt)
        return {"status": "completed", "response": resp}
    except Exception as e:
        logger.error("[DeepSeek] Error test prompt: %s", e)
        return {"status": "invalid", "message": str(e)}


__all__ = [
    "add_channel", "remove_channel", "store_message", "collect_message",
    "process_batch", "set_auto_run", "get_auto_run_config", "start_auto_run",
    "stop_auto_run", "run_test_prompt", "set_forced_channel", "remove_forced_channel",
    "split_for_discord", "is_channel_enabled", "config", "_auto_run_task",
]
