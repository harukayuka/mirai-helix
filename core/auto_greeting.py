# core/auto_greeting.py - Fitur Welcome & Goodbye Otomatis untuk Mirai
import asyncio
import discord
import json
import random
from pathlib import Path
from utils.logger import setup_logging
from core.module_manager import module_manager

logger = setup_logging()

CONFIG_PATH = Path("data/greeting_config.json")

class AutoGreeting:
    """
    Kelas untuk menangani pesan sambutan dan perpisahan otomatis.
    """
    def __init__(self, bot: discord.Client, gemini_client):
        self.bot = bot
        self.gemini = gemini_client
        self._ensure_config_exists()
        self.setup_events()

    def _ensure_config_exists(self):
        """Memastikan file konfigurasi ada."""
        if not CONFIG_PATH.parent.exists():
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'w') as f:
                json.dump({"enabled": True, "guilds": {}}, f, indent=4)

    def _load_config(self):
        """Membaca konfigurasi dari file JSON."""
        try:
            with open(CONFIG_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[GREETING] Error loading config: {e}")
            return {"enabled": True, "guilds": {}}

    def _save_config(self, config):
        """Menyimpan konfigurasi ke file JSON."""
        try:
            with open(CONFIG_PATH, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            logger.error(f"[GREETING] Error saving config: {e}")

    def is_enabled(self, guild_id: int) -> bool:
        """Cek apakah fitur aktif untuk guild tertentu."""
        # Cek status modul global dulu
        if not module_manager.is_enabled("greeting"):
            return False
            
        config = self._load_config()
        if not config.get("enabled", True):
            return False
        guild_config = config.get("guilds", {}).get(str(guild_id), {})
        return guild_config.get("enabled", True)

    def set_enabled(self, guild_id: int, status: bool):
        """Mengatur status aktif/nonaktif untuk guild tertentu."""
        config = self._load_config()
        if str(guild_id) not in config["guilds"]:
            config["guilds"][str(guild_id)] = {}
        config["guilds"][str(guild_id)]["enabled"] = status
        self._save_config(config)

    def set_channel(self, guild_id: int, channel_id: int):
        """Mengatur ID channel khusus untuk greeting di guild tertentu."""
        config = self._load_config()
        if str(guild_id) not in config["guilds"]:
            config["guilds"][str(guild_id)] = {}
        config["guilds"][str(guild_id)]["channel_id"] = channel_id
        self._save_config(config)

    def _get_fallback_welcome(self, member: discord.Member) -> str:
        """Pesan sambutan cadangan jika API error/limit."""
        fallbacks = [
            f"Halo {member.mention}! Selamat datang di **{member.guild.name}**. Senang sekali kamu bisa bergabung bersama kami di sini. Semoga betah ya! ✨",
            f"Selamat datang {member.mention}! 👋 Mari bergabung dalam obrolan dan jangan ragu untuk bertanya jika butuh bantuan. Semoga harimu menyenangkan di {member.guild.name}!",
            f"Hai {member.mention}, selamat bergabung! 🌟 Kami sangat senang memilikimu di sini. Jangan lupa cek channel info ya!"
        ]
        return random.choice(fallbacks)

    def _get_fallback_goodbye(self, member: discord.Member) -> str:
        """Pesan perpisahan cadangan jika API error/limit."""
        fallbacks = [
            f"Sampai jumpa lagi, **{member.display_name}**. Terima kasih sudah pernah menjadi bagian dari {member.guild.name}. Semoga sukses di perjalananmu selanjutnya! 👋",
            f"Selamat jalan {member.display_name}. Kami akan merindukan kehadiranmu di sini. Sampai bertemu lagi di lain waktu! ✨",
            f"Terima kasih atas waktunya di {member.guild.name}, {member.display_name}. Hati-hati di jalan dan sukses selalu! 💙"
        ]
        return random.choice(fallbacks)

    def setup_events(self):
        @self.bot.event
        async def on_member_join(member: discord.Member):
            """Event saat member baru bergabung."""
            if member.bot or not self.is_enabled(member.guild.id):
                return

            channel = self._get_greeting_channel(member.guild)
            if not channel:
                return

            await asyncio.sleep(2)
            try:
                async with channel.typing():
                    welcome_msg = None
                    try:
                        # Coba generate dengan AI
                        welcome_msg = await asyncio.to_thread(self.gemini.generate_welcome, member.display_name)
                    except Exception as api_err:
                        logger.warning(f"[WELCOME] API Error/Limit: {api_err}. Using fallback.")
                    
                    # Gunakan fallback jika AI gagal, limit, atau memberikan pesan error
                    if not welcome_msg or any(err in welcome_msg for err in ["Maaf", "limit", "error", "⚠️"]):
                        welcome_msg = self._get_fallback_welcome(member)
                    else:
                        # Pastikan mention user ada di pesan AI
                        if member.mention not in welcome_msg:
                            welcome_msg = f"Halo {member.mention}! {welcome_msg}"

                    embed = discord.Embed(
                        description=welcome_msg,
                        color=discord.Color.teal()
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.set_footer(text=f"Member #{len(member.guild.members)}")
                    
                    await channel.send(content=f"✨ **Selamat Datang!** ✨", embed=embed)
                    logger.info(f"[WELCOME] Sent welcome message for {member.display_name} in {channel.name}")
            except Exception as e:
                logger.error(f"[WELCOME] Critical Error: {e}")

        @self.bot.event
        async def on_member_remove(member: discord.Member):
            """Event saat member keluar."""
            if member.bot or not self.is_enabled(member.guild.id):
                return

            channel = self._get_greeting_channel(member.guild)
            if not channel:
                return

            try:
                goodbye_msg = None
                try:
                    # Coba generate dengan AI
                    goodbye_msg = await asyncio.to_thread(self.gemini.generate_goodbye, member.display_name)
                except Exception as api_err:
                    logger.warning(f"[GOODBYE] API Error/Limit: {api_err}. Using fallback.")
                
                # Gunakan fallback jika AI gagal, limit, atau memberikan pesan error
                if not goodbye_msg or any(err in goodbye_msg for err in ["Maaf", "limit", "error", "⚠️"]):
                    goodbye_msg = self._get_fallback_goodbye(member)

                embed = discord.Embed(
                    description=goodbye_msg,
                    color=discord.Color.red()
                )
                embed.set_footer(text="Kami akan merindukanmu.")
                
                await channel.send(content=f"👋 **Sampai Jumpa...**", embed=embed)
                logger.info(f"[GOODBYE] Sent goodbye message for {member.display_name} in {channel.name}")
            except Exception as e:
                logger.error(f"[GOODBYE] Critical Error: {e}")

    def _get_greeting_channel(self, guild: discord.Guild) -> discord.TextChannel:
        """Mencari channel terbaik untuk mengirim pesan sambutan."""
        config = self._load_config()
        guild_config = config.get("guilds", {}).get(str(guild.id), {})
        
        # 1. Coba channel ID yang dikonfigurasi manual
        custom_channel_id = guild_config.get("channel_id")
        if custom_channel_id:
            channel = guild.get_channel(int(custom_channel_id))
            if channel and isinstance(channel, discord.TextChannel) and channel.permissions_for(guild.me).send_messages:
                return channel

        # 2. Coba system channel
        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            return guild.system_channel
            
        # 3. Cari channel dengan nama umum
        common_names = ['welcome', 'greetings', 'halo', 'selamat-datang', 'general', 'umum']
        for name in common_names:
            channel = discord.utils.get(guild.text_channels, name=name)
            if channel and channel.permissions_for(guild.me).send_messages:
                return channel
                
        # 4. Fallback
        return next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
