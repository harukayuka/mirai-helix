"""
core/command.py — Slash Commands Loader
────────────────────────────────────────
Memuat & mendaftarkan semua slash commands dari folder commands/.
Setiap command group ada di file terpisah:
  - commands/info_command.py          → /ask, /ping, /info, /clear, /status, /cuaca
  - commands/health_command.py        → /bmi, /water
  - commands/deepseek_command.py      → /deepseek (add, remove, status, toggle, run, ...)
  - commands/qwen_command.py          → /qwen (add, remove, status, toggle, run, ...)
  - commands/module_command.py        → /module
  - commands/greeting_command.py      → /greeting
  - commands/bedtime_command.py       → /bedtime
  - commands/online_counter_command.py → /online_counter
  - commands/general.py               → /report
"""

from typing import Optional
import discord
from discord import app_commands
from utils.logger import setup_logging

logger = setup_logging()


class CommandGroup:
    """Loader untuk semua slash commands Mirai."""

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.tree = app_commands.CommandTree(bot)
        self._register_all()

    def _register_all(self):
        """Register semua command dari file-file di folder commands/."""
        # ── Commands sederhana ──────────────────────────────────────────────
        from commands.info_command import InfoCommands
        InfoCommands(self.bot).register(self.tree)

        from commands.health_command import HealthCommands
        HealthCommands(self.bot).register(self.tree)

        from commands.general import GeneralCommands
        GeneralCommands(self.bot).register(self.tree)

        # ── Command groups ──────────────────────────────────────────────────
        from commands.deepseek_command import DeepSeekCommands
        DeepSeekCommands(self.bot).register(self.tree)

        from commands.qwen_command import QwenCommands
        QwenCommands(self.bot).register(self.tree)

        from commands.module_command import ModuleCommands
        ModuleCommands(self.bot).register(self.tree)

        from commands.greeting_command import GreetingCommands
        GreetingCommands(self.bot).register(self.tree)

        from commands.bedtime_command import BedtimeCommands, set_reminder_manager
        # reminder_manager akan di-set dari luar
        self._bedtime_set_rm = set_reminder_manager
        BedtimeCommands(self.bot).register(self.tree)

        from commands.online_counter_command import OnlineCounterCommands, set_online_counter_manager
        self._oc_set_ocm = set_online_counter_manager
        OnlineCounterCommands(self.bot).register(self.tree)

    def set_reminder_manager(self, manager):
        """Set reminder manager untuk /bedtime commands."""
        if hasattr(self, "_bedtime_set_rm"):
            self._bedtime_set_rm(manager)

    def set_online_counter_manager(self, manager):
        """Set online counter manager untuk /online_counter commands."""
        if hasattr(self, "_oc_set_ocm"):
            self._oc_set_ocm(manager)

    async def sync_commands(self, guild_id: Optional[int] = None):
        """Sinkronisasi commands ke Discord."""
        if guild_id:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("✅ Commands synced to guild %s", guild_id)
        else:
            await self.tree.sync()
            logger.info("✅ Global commands synced")