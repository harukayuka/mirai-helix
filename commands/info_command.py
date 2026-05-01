"""
commands/info_command.py
────────────────────────
Slash commands sederhana: /ask, /ping, /info, /clear, /status, /cuaca.
"""

import sys
import os
from typing import Optional
from datetime import datetime
import discord
from discord import app_commands

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from commands.base import BaseCommand
from ai.gemini import GeminiClient
from core.module_manager import module_manager
from memory import get_history, clear_history, reset_on_context_change
from utils.identity import resolve_name, clean_name, build_user_context
from utils.logger import setup_logging

logger = setup_logging()
gemini = GeminiClient()


class InfoCommands(BaseCommand):
    def register(self, tree: app_commands.CommandTree):
        # ── /ask ────────────────────────────────────────────────────────────
        @tree.command(name="ask", description="Tanya Mirai tentang kesehatan atau ceritakan keluhanmu")
        @app_commands.describe(
            pertanyaan="Apa yang ingin kamu tanyakan atau ceritakan?",
            private="Jawaban hanya kamu yang bisa lihat? (default: False)",
        )
        async def ask_command(interaction: discord.Interaction, pertanyaan: str, private: bool = False):
            await interaction.response.defer(ephemeral=private, thinking=True)
            try:
                from memory import add_message

                user = interaction.user
                guild = interaction.guild
                channel_name = (
                    interaction.channel.name
                    if interaction.channel and hasattr(interaction.channel, "name")
                    else "DM"
                )

                reset_on_context_change(guild_id=guild.id if guild else None, user_id=user.id)
                user_name = clean_name(resolve_name(interaction))
                user_context = build_user_context(
                    interaction,
                    extra_info={
                        "Channel": channel_name,
                        "Server": guild.name if guild else "DM",
                        "Pesan": pertanyaan,
                    },
                )

                await add_message("user", pertanyaan)
                history = get_history()
                reply = await gemini.generate(history, user_context=user_context)
                await add_message("assistant", reply)

                if len(reply) > 1900:
                    reply = reply[:1900] + "\n…*(pesan dipotong)*"

                embed = discord.Embed(description=reply, color=0x00FF88)
                embed.set_author(name=f"Jawaban untuk {user_name}", icon_url=user.display_avatar.url)
                embed.set_footer(text="Mirai • Helix Health Assistant")
                await interaction.followup.send(embed=embed, ephemeral=private)
            except Exception as e:
                logger.exception("[/ask] Error: %s", e)
                await interaction.followup.send(f"⚠️ Terjadi kesalahan: {str(e)[:100]}", ephemeral=private)

        # ── /ping ───────────────────────────────────────────────────────────
        @tree.command(name="ping", description="Cek respons bot")
        async def ping_command(interaction: discord.Interaction):
            latency = round(self.bot.latency * 1000)
            await interaction.response.send_message(f"Pong! 🏓 **{latency}ms**")

        # ── /info ───────────────────────────────────────────────────────────
        @tree.command(name="info", description="Info tentang Mirai")
        async def info_command(interaction: discord.Interaction):
            embed = discord.Embed(
                title="🤖 **Mirai - Health Assistant**",
                description="Asisten kesehatan dan pendamping emosional di server Helix",
                color=0x00ff88,
            )
            embed.add_field(name="Fitur", value="• Curhat & konseling ringan\n• Edukasi kesehatan\n• Pendengar yang baik", inline=False)
            embed.add_field(name="Cara pakai", value="• Mention aku di channel\n• Reply ke pesanku\n• Pakai `/ask`", inline=False)
            embed.add_field(name="Note", value="Aku bukan dokter! Untuk kondisi serius, segera ke profesional.", inline=False)
            embed.set_footer(text=f"Diminta oleh {interaction.user.display_name}")
            await interaction.response.send_message(embed=embed)

        # ── /clear ──────────────────────────────────────────────────────────
        @tree.command(name="clear", description="Hapus riwayat percakapan (hanya admin)")
        @app_commands.default_permissions(administrator=True)
        async def clear_command(interaction: discord.Interaction):
            try:
                clear_history()
                await interaction.response.send_message("✅ Riwayat percakapan telah dibersihkan!", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Gagal: {e}", ephemeral=True)

        # ── /status ─────────────────────────────────────────────────────────
        @tree.command(name="status", description="Lihat status bot")
        async def status_command(interaction: discord.Interaction):
            total_history = len(get_history())
            embed = discord.Embed(title="📊 **Status Bot**", color=0x3498db)
            embed.add_field(name="Model AI", value="Gemini 2.5 Flash", inline=True)
            embed.add_field(name="Total Pesan di History", value=str(total_history), inline=True)
            embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
            await interaction.response.send_message(embed=embed)

        # ── /cuaca ──────────────────────────────────────────────────────────
        @tree.command(name="cuaca", description="Cek prakiraan cuaca dari BMKG")
        @app_commands.describe(kode_wilayah="Kode wilayah adm4. Default: Kemayoran (31.71.03.1001)")
        async def cuaca_command(interaction: discord.Interaction, kode_wilayah: Optional[str] = "31.71.03.1001"):
            if not module_manager.is_enabled("weather"):
                await interaction.response.send_message("⚠️ Modul Cuaca sedang dinonaktifkan oleh admin.", ephemeral=True)
                return
            await interaction.response.defer()
            try:
                weather_data = await gemini.bmkg.get_weather_raw(kode_wilayah or "31.71.03.1001")
                if not weather_data:
                    await interaction.followup.send("⚠️ Gagal mengambil data cuaca dari BMKG. Coba lagi nanti!")
                    return

                lokasi = weather_data["lokasi"]
                prakiraan = weather_data["prakiraan"]
                first = prakiraan[0] if prakiraan else {}

                embed = discord.Embed(
                    title=f"🌤️ Prakiraan Cuaca: {lokasi.get('desa', '-')}",
                    description=f"Wilayah: {lokasi.get('kecamatan', '-')}, {lokasi.get('kotkab', '-')}, {lokasi.get('provinsi', '-')}",
                    color=0x3498db,
                    timestamp=datetime.now().astimezone(),
                )
                embed.add_field(name="☁️ Kondisi", value=first.get("weather_desc", "-"), inline=True)
                embed.add_field(name="🌡️ Suhu", value=f"{first.get('t', '-')}°C", inline=True)
                embed.add_field(name="💧 Kelembapan", value=f"{first.get('hu', '-')}%", inline=True)
                embed.add_field(name="💨 Kec. Angin", value=f"{first.get('ws', '-')} km/jam", inline=True)
                embed.add_field(name="🧭 Arah Angin", value=first.get("wd", "-"), inline=True)
                embed.add_field(name="☁️ Tutupan Awan", value=f"{first.get('tcc', '-')}%", inline=True)

                if len(prakiraan) > 1:
                    lines = []
                    for f in prakiraan[1:]:
                        lines.append(f"`{f.get('local_datetime', '-')}` — {f.get('weather_desc', '-')}, {f.get('t', '-')}°C")
                    embed.add_field(name="📅 Prakiraan Berikutnya", value="\n".join(lines), inline=False)

                embed.set_footer(text=f"Sumber: {weather_data.get('sumber', 'BMKG')} | Kode: {kode_wilayah}")
                await interaction.followup.send(embed=embed)
            except Exception as e:
                await interaction.followup.send(f"⚠️ Terjadi kesalahan: {str(e)[:100]}")