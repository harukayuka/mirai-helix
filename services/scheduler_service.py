import asyncio
import random
import discord
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from utils.logger import setup_logging
from ai.news_summary import run_summary
from core.module_manager import module_manager
import core.qwen_batch as qwen_batch
from config import RPC_UPDATE_INTERVAL, NEWS_REFRESH_SECONDS

logger = setup_logging()
WIB = ZoneInfo("Asia/Jakarta")

class SchedulerService:
    def __init__(self, bot, micro_rag, reminder_manager, online_counter_manager):
        self.bot = bot
        self.micro_rag = micro_rag
        self.reminder_manager = reminder_manager
        self.online_counter_manager = online_counter_manager
        self.rpc_statuses = [
            {"type": "playing", "text": "Mirai Health Assistant"},
            {"type": "watching", "text": "over Helix members"},
            {"type": "listening", "text": "cerita kesehatanmu"},
            {"type": "playing", "text": "dengan algoritma empati"},
            {"type": "watching", "text": "tumbuh kembang server"},
        ]

    def start_all(self):
        self.bot.loop.create_task(self.update_presence())
        self.bot.loop.create_task(self.schedule_news_summary())
        self.bot.loop.create_task(self.schedule_micro_rag())
        self.bot.loop.create_task(self.reminder_manager.initialize_all_reminders())
        self.bot.loop.create_task(self.online_counter_manager.initialize_all_counters())
        qwen_batch.start_auto_run(self.bot)
        logger.info("[Scheduler] All background tasks started.")

    async def update_presence(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
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
            await asyncio.sleep(RPC_UPDATE_INTERVAL)

    async def schedule_news_summary(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            if module_manager.is_enabled("news"):
                try:
                    await asyncio.to_thread(run_summary)
                except Exception as err:
                    logger.exception("[NEWS] Gagal menjalankan ringkasan: %s", err)
            await asyncio.sleep(NEWS_REFRESH_SECONDS)

    async def schedule_micro_rag(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self.micro_rag.analyze_all_users()
            except Exception as err:
                logger.exception("[Micro-RAG] Gagal menjalankan analisis harian: %s", err)
            await asyncio.sleep(86400)
