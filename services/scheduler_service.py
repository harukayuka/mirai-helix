import asyncio
import random
import discord
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from utils.logger import setup_logging
from ai.news_summary import run_summary
from core.module_manager import module_manager
import core.qwen_batch as qwen_batch
import psutil
import requests
import aiohttp
from config import RPC_UPDATE_INTERVAL, NEWS_REFRESH_SECONDS, WEBHOOK_URL, ALERT_CHANNEL_ID

logger = setup_logging()
WIB = ZoneInfo("Asia/Jakarta")

class SchedulerService:
    def __init__(self, bot, micro_rag, reminder_manager, online_counter_manager):
        self.bot = bot
        self.micro_rag = micro_rag
        self.reminder_manager = reminder_manager
        self.online_counter_manager = online_counter_manager
        self.modules_paused = False  # Track apakah modul sedang dipause
        self.prev_module_status = {}
        self.rpc_statuses = [
            {"type": "playing", "text": "Mirai Health Assistant"},
            {"type": "watching", "text": "over Helix members"},
            {"type": "listening", "text": "cerita kesehatanmu"},
            {"type": "playing", "text": "dengan algoritma empati"},
            {"type": "watching", "text": "tumbuh kembang server"},
        ]
        # FIXED: Reuse aiohttp session instead of creating new one each time
        self._webhook_session = None

    async def _get_webhook_session(self):
        """Get or create webhook session."""
        if self._webhook_session is None or self._webhook_session.closed:
            self._webhook_session = aiohttp.ClientSession()
        return self._webhook_session

    async def close(self):
        """Clean up resources."""
        if self._webhook_session and not self._webhook_session.closed:
            await self._webhook_session.close()

    def start_all(self):
        self.bot.loop.create_task(self.update_presence())
        self.bot.loop.create_task(self.schedule_news_summary())
        self.bot.loop.create_task(self.schedule_micro_rag())
        self.bot.loop.create_task(self.reminder_manager.initialize_all_reminders())
        self.bot.loop.create_task(self.online_counter_manager.initialize_all_counters())
        self.bot.loop.create_task(self.monitor_resources())  # Monitor CPU & RAM
        self.bot.loop.create_task(self._start_qwen_batch())
        logger.info("[Scheduler] All background tasks started.")

    async def update_presence(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                status = random.choice(self.rpc_statuses)
                rpc_type = status["type"]
                rpc_text = status["text"]
                if rpc_type == "playing":
                    activity = discord.Game(name=rpc_text)
                elif rpc_type == "watching":
                    activity = discord.Activity(type=discord.ActivityType.watching, name=rpc_text)
                elif rpc_type == "listening":
                    activity = discord.Activity(type=discord.ActivityType.listening, name=rpc_text)
                else:
                    activity = discord.Game(name=rpc_text)
                await self.bot.change_presence(activity=activity)
            except Exception as err:
                logger.exception("[Scheduler] Error updating presence: %s", err)
            await asyncio.sleep(RPC_UPDATE_INTERVAL)

    async def schedule_news_summary(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            if module_manager.is_enabled("news"):
                try:
                    # FIXED: Added timeout to prevent hanging
                    await asyncio.wait_for(
                        asyncio.to_thread(run_summary),
                        timeout=300  # 5 minutes max
                    )
                except asyncio.TimeoutError:
                    logger.error("[NEWS] Timeout saat menjalankan ringkasan berita")
                except Exception as err:
                    logger.exception("[NEWS] Gagal menjalankan ringkasan: %s", err)
            await asyncio.sleep(NEWS_REFRESH_SECONDS)

    async def schedule_micro_rag(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                # FIXED: Added timeout to prevent hanging
                await asyncio.wait_for(
                    self.micro_rag.analyze_all_users(),
                    timeout=600  # 10 minutes max
                )
            except asyncio.TimeoutError:
                logger.error("[Micro-RAG] Timeout saat analisis harian")
            except Exception as err:
                logger.exception("[Micro-RAG] Gagal menjalankan analisis harian: %s", err)
            await asyncio.sleep(86400)

    async def monitor_resources(self):
        """Pantau CPU & RAM, kirim ke webhook, dan kontrol modul.
        - CPU >= 50% → kirim peringatan ke webhook (jika ada).
        - CPU >= 70% → nonaktifkan semua modul sampai CPU < 50%.
        """
        await self.bot.wait_until_ready()
        last_webhook_time = 0
        webhook_cooldown = 300  # 5 menit cooldown antar webhook
        
        while not self.bot.is_closed():
            try:
                cpu = psutil.cpu_percent(interval=1)
                ram = psutil.virtual_memory().percent
                
                # Kirim webhook untuk peringatan (CPU >= 50%) dan kritis (CPU >= 70%)
                current_time = asyncio.get_event_loop().time()
                # Jika webhook URL ada dan cooldown selesai, kirim payload sesuai level
                if WEBHOOK_URL and (current_time - last_webhook_time) >= webhook_cooldown:
                    severity = None
                    embed_color = 0x00ff00
                    status_text = "✅ Normal"
                    if cpu >= 70:
                        severity = "critical"
                        embed_color = 0xff0000
                        status_text = "⚠️ CPU Tinggi"
                    elif cpu >= 50:
                        severity = "warning"
                        embed_color = 0xffa500
                        status_text = "⚠️ CPU Sedang"
                    
                    if severity:
                        embed = {
                            "title": "📊 Monitoring Server",
                            "description": f"CPU: {cpu}%\nRAM: {ram}%",
                            "color": embed_color,
                            "fields": [{"name": "Status", "value": status_text}],
                            "severity": severity,
                        }
                        payload = {"embeds": [embed]}
                        try:
                            await self._send_webhook(payload)
                            logger.info(f"[Monitor] Webhook {severity} dikirim (CPU {cpu}%)")
                            last_webhook_time = current_time
                        except Exception as e:
                            logger.error(f"[Monitor] Gagal mengirim webhook: {e}")
                
                # Handle high CPU - pause modules
                if cpu >= 70 and not self.modules_paused:
                    logger.warning("[Monitor] CPU >=70%%, menonaktifkan semua modul.")
                    # Simpan status modul sebelum pause
                    self.prev_module_status = {mod: module_manager.is_enabled(mod) for mod in module_manager.modules}
                    for mod in module_manager.modules:
                        module_manager.set_status(mod, False)
                    self.modules_paused = True
                    
                    # Kirim embed peringatan ke channel jika diatur
                    if ALERT_CHANNEL_ID:
                        try:
                            channel = self.bot.get_channel(ALERT_CHANNEL_ID)
                            if channel:
                                embed = discord.Embed(
                                    title="⚠️ Peringatan CPU Tinggi",
                                    description="Penggunaan CPU server meninggi! Semua fitur dihentikan sementara, harap bersabar.",
                                    color=0xFF0000
                                )
                                await channel.send(embed=embed)
                        except Exception as e:
                            logger.error(f"[Monitor] Gagal mengirim embed peringatan: {e}")
                
                # Handle CPU recovery - resume modules
                elif cpu < 50 and self.modules_paused:
                    logger.info("[Monitor] CPU turun <50%%, mengaktifkan kembali modul.")
                    for mod, was_enabled in self.prev_module_status.items():
                        if was_enabled:
                            module_manager.set_status(mod, True)
                    self.modules_paused = False
                    
                    # Kirim notifikasi recovery
                    if ALERT_CHANNEL_ID:
                        try:
                            channel = self.bot.get_channel(ALERT_CHANNEL_ID)
                            if channel:
                                embed = discord.Embed(
                                    title="✅ CPU Normal Kembali",
                                    description="Penggunaan CPU sudah normal. Semua fitur telah diaktifkan kembali.",
                                    color=0x00FF00
                                )
                                await channel.send(embed=embed)
                        except Exception as e:
                            logger.error(f"[Monitor] Gagal mengirim embed recovery: {e}")
            
            except Exception as e:
                logger.exception(f"[Monitor] Error dalam monitoring resources: {e}")
            
            await asyncio.sleep(60)

    async def _send_webhook(self, payload):
        """Send webhook with proper session management and error handling."""
        try:
            session = await self._get_webhook_session()
            async with session.post(WEBHOOK_URL, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status >= 400:
                    txt = await resp.text()
                    logger.error(f"[Monitor] Webhook gagal {resp.status}: {txt}")
                else:
                    logger.debug(f"[Monitor] Webhook berhasil dikirim (status {resp.status})")
        except asyncio.TimeoutError:
            logger.error("[Monitor] Webhook timeout setelah 5 detik")
        except Exception as e:
            logger.error(f"[Monitor] Gagal mengirim webhook: {e}")

    async def _start_qwen_batch(self):
        await self.bot.wait_until_ready()
        try:
            qwen_batch.start_auto_run(self.bot)
        except Exception as e:
            logger.exception(f"[Scheduler] Error starting qwen_batch: {e}")