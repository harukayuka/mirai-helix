import os
from core.events.message_handler import MessageHandler
from services.ai_service import AIService
from services.scheduler_service import SchedulerService
from managers.cooldown_manager import CooldownManager
from core.micro_rag import MicroRAG
from utils.reminder import ReminderManager
from utils.online_counter import OnlineCounterManager
from core.command import CommandGroup
from utils.logger import setup_logging

logger = setup_logging()

class Router:
    def __init__(self, bot):
        self.bot = bot
        
        # Initialize Services & Managers
        self.ai_service = AIService()
        self.cooldown_manager = CooldownManager()
        self.micro_rag = MicroRAG()
        self.reminder_manager = ReminderManager(bot)
        self.online_counter_manager = OnlineCounterManager(bot)
        
        # Initialize Handlers
        self.message_handler = MessageHandler(bot, self.ai_service, self.cooldown_manager, self.micro_rag)
        
        # Initialize Commands
        self.command_group = CommandGroup(bot)
        self.command_group.set_reminder_manager(self.reminder_manager)
        self.command_group.set_online_counter_manager(self.online_counter_manager)
        
        # Initialize Scheduler
        self.scheduler = SchedulerService(
            bot, 
            self.micro_rag, 
            self.reminder_manager, 
            self.online_counter_manager
        )
        
        self.setup_events()

    def setup_events(self):
        @self.bot.event
        async def on_ready():
            logger.info("✅ Bot connected as %s", self.bot.user)
            # Initialize AutoGreeting singleton for greeting commands
            from core.auto_greeting import AutoGreeting
            from ai.gemini import GeminiClient
            # Buat instance global yang dapat di‑import oleh command
            global auto_greeting
            auto_greeting = AutoGreeting(self.bot, GeminiClient())
            guild_id = os.getenv("GUILD_ID")
            if guild_id:
                await self.command_group.sync_commands(guild_id=int(guild_id))
            else:
                await self.command_group.sync_commands()
            
            if not getattr(self.bot, "_mirai_background_started", False):
                self.bot._mirai_background_started = True
                self.scheduler.start_all()

        @self.bot.event
        async def on_message(message):
            await self.message_handler.handle(message)
