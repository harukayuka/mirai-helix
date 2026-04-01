# core/command.py - Slash Commands untuk Mirai Bot
"""
Implementasi slash commands untuk Mirai Discord Bot.
Commands: /ask, /ping, /info, /clear, /status
"""

import asyncio
import discord
from discord import app_commands
from typing import Optional
from datetime import datetime
import sys
import os
from utils.logger import setup_logging

# Tambahkan path parent ke sys.path agar bisa import dari folder lain
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory import get_history, clear_history
from ai.gemini import GeminiClient
logger = setup_logging()

# Inisialisasi Gemini client (BMKGClient sudah ada di dalam gemini.bmkg)
gemini = GeminiClient()

class CommandGroup:
    """Kelas untuk mengelompokkan semua slash commands Mirai."""
    
    def __init__(self, bot: discord.Client):
        """
        Initialize CommandGroup.
        
        Args:
            bot: Discord client instance
        """
        self.bot = bot
        self.tree = app_commands.CommandTree(bot)
        self.setup_commands()
    
    def setup_commands(self):
        """Daftarkan semua slash commands."""
        
        # ===== COMMAND: /ask =====
        @self.tree.command(name="ask", description="Tanya Mirai tentang kesehatan atau ceritakan keluhanmu")
        @app_commands.describe(
            pertanyaan="Apa yang ingin kamu tanyakan atau ceritakan?",
            private="Jawaban hanya kamu yang bisa lihat? (default: False)"
        )
        async def ask_command(
            interaction: discord.Interaction, 
            pertanyaan: str,
            private: bool = False
        ):
            """Slash command untuk bertanya kepada Mirai."""
            await interaction.response.defer(ephemeral=private)
            
            try:
                # Ambil nama user
                user_name = interaction.user.display_name
                
                # Format pesan dengan nama
                user_msg = f"{user_name}: {pertanyaan}"
                
                # Simpan ke history global
                from memory import add_message
                add_message("user", user_msg)
                
                # Ambil history
                history = get_history()
                
                # Generate respons
                reply = await asyncio.to_thread(gemini.generate, history)
                
                # Simpan respons bot
                add_message("assistant", reply)
                
                # Kirim balasan
                await interaction.followup.send(reply, ephemeral=private)
                
            except Exception as e:
                await interaction.followup.send(f"⚠️ Error: {str(e)[:100]}", ephemeral=private)
        
        # ===== COMMAND: /ping =====
        @self.tree.command(name="ping", description="Cek respons bot")
        async def ping_command(interaction: discord.Interaction):
            """Slash command untuk cek latency bot."""
            latency = round(self.bot.latency * 1000)
            await interaction.response.send_message(f"Pong! 🏓 **{latency}ms**")
        
        # ===== COMMAND: /info =====
        @self.tree.command(name="info", description="Info tentang Mirai")
        async def info_command(interaction: discord.Interaction):
            """Slash command untuk lihat informasi Mirai."""
            embed = discord.Embed(
                title="🤖 **Mirai - Health Assistant**",
                description="Asisten kesehatan dan pendamping emosional di server Helix",
                color=0x00ff88
            )
            embed.add_field(
                name="Fitur", 
                value="• Curhat & konseling ringan\n• Edukasi kesehatan\n• Pendengar yang baik", 
                inline=False
            )
            embed.add_field(
                name="Cara pakai", 
                value="• Mention aku di channel\n• Reply ke pesanku\n• Pakai `/ask`", 
                inline=False
            )
            embed.add_field(
                name="Note", 
                value="Aku bukan dokter! Untuk kondisi serius, segera ke profesional.", 
                inline=False
            )
            embed.set_footer(text=f"Diminta oleh {interaction.user.display_name}")
            
            await interaction.response.send_message(embed=embed)
        
        # ===== COMMAND: /clear =====
        @self.tree.command(name="clear", description="Hapus riwayat percakapan (hanya admin)")
        @app_commands.default_permissions(administrator=True)
        async def clear_command(interaction: discord.Interaction):
            """Slash command untuk hapus history (admin only)."""
            try:
                from memory import clear_history
                clear_history()
                await interaction.response.send_message(
                    "✅ Riwayat percakapan telah dibersihkan!", 
                    ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(f"❌ Gagal: {e}", ephemeral=True)
        
        # ===== COMMAND: /status =====
        @self.tree.command(name="status", description="Lihat status bot")
        async def status_command(interaction: discord.Interaction):
            """Slash command untuk lihat status bot."""
            total_history = len(get_history())
            
            embed = discord.Embed(
                title="📊 **Status Bot**",
                color=0x3498db
            )
            embed.add_field(name="Model AI", value="Gemini 2.5 Flash", inline=True)
            embed.add_field(name="Total Pesan di History", value=str(total_history), inline=True)
            embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
            
            await interaction.response.send_message(embed=embed)
        
        # ===== COMMAND: /cuaca =====
        @self.tree.command(name="cuaca", description="Cek prakiraan cuaca dari BMKG")
        @app_commands.describe(
            kode_wilayah="Kode wilayah adm4 (Kelurahan/Desa). Default: Kemayoran (31.71.03.1001)"
        )
        async def cuaca_command(
            interaction: discord.Interaction, 
            kode_wilayah: Optional[str] = None
        ):
            """Slash command untuk cek cuaca BMKG."""
            await interaction.response.defer()
            
            try:
                # Ambil data cuaca menggunakan get_weather_raw()
                from ai.cuaca import DEFAULT_ADM4
                adm4 = kode_wilayah if kode_wilayah else DEFAULT_ADM4
                weather_data = gemini.bmkg.get_weather_raw(adm4)
                
                if not weather_data:
                    await interaction.followup.send("⚠️ Maaf, aku gagal mengambil data cuaca dari BMKG. Coba lagi nanti ya! 🙏")
                    return
                
                lokasi = weather_data["lokasi"]
                prakiraan = weather_data["prakiraan"]  # list of up to 3 forecasts
                
                # Ambil prakiraan pertama (terdekat) untuk header embed
                first = prakiraan[0] if prakiraan else {}
                
                embed = discord.Embed(
                    title=f"🌤️ Prakiraan Cuaca: {lokasi.get('desa', '-')}",
                    description=f"Wilayah: {lokasi.get('kecamatan', '-')}, {lokasi.get('kotkab', '-')}, {lokasi.get('provinsi', '-')}",
                    color=0x3498db,
                    timestamp=datetime.now().astimezone()
                )
                
                # Field dari prakiraan terdekat
                embed.add_field(name="☁️ Kondisi", value=first.get("weather_desc", "-"), inline=True)
                embed.add_field(name="🌡️ Suhu", value=f"{first.get('t', '-')}°C", inline=True)
                embed.add_field(name="💧 Kelembapan", value=f"{first.get('hu', '-')}%", inline=True)
                embed.add_field(name="💨 Kec. Angin", value=f"{first.get('ws', '-')} km/jam", inline=True)
                embed.add_field(name="🧭 Arah Angin", value=first.get("wd", "-"), inline=True)
                embed.add_field(name="☁️ Tutupan Awan", value=f"{first.get('tcc', '-')}%", inline=True)
                
                # Jadwal prakiraan berikutnya (jika ada)
                if len(prakiraan) > 1:
                    jadwal_lines = []
                    for f in prakiraan[1:]:
                        dt = f.get("local_datetime", "-")
                        desc = f.get("weather_desc", "-")
                        suhu = f.get("t", "-")
                        jadwal_lines.append(f"`{dt}` — {desc}, {suhu}°C")
                    embed.add_field(
                        name="📅 Prakiraan Berikutnya",
                        value="\n".join(jadwal_lines),
                        inline=False
                    )
                
                embed.set_footer(text=f"Sumber: {weather_data.get('sumber', 'BMKG')} | Kode wilayah: {adm4}")
                
                await interaction.followup.send(embed=embed)
                
            except Exception as e:
                await interaction.followup.send(f"⚠️ Terjadi kesalahan: {str(e)[:100]}")
    
    async def sync_commands(self, guild_id: Optional[int] = None):
        """
        Sinkronisasi commands ke Discord.
        
        Args:
            guild_id: Guild ID untuk sinkronisasi (None untuk global)
        """
        if guild_id:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("✅ Commands synced to guild %s", guild_id)
        else:
            await self.tree.sync()
            logger.info("✅ Global commands synced")
