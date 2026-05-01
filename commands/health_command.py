"""
commands/health_command.py
──────────────────────────
Slash commands untuk /bmi dan /water.
"""

from typing import Optional
import discord
from discord import app_commands
from commands.base import BaseCommand
from core.module_manager import module_manager
from utils.calculator import calculate_bmi, calculate_daily_water_intake


class HealthCommands(BaseCommand):
    def register(self, tree: app_commands.CommandTree):
        # ── /bmi ────────────────────────────────────────────────────────────
        @tree.command(name="bmi", description="Hitung Body Mass Index (BMI) kamu")
        @app_commands.describe(
            berat_badan="Berat badanmu dalam kilogram (contoh: 65.5)",
            tinggi_badan="Tinggi badanmu dalam centimeter (contoh: 170)",
        )
        async def bmi_command(interaction: discord.Interaction, berat_badan: float, tinggi_badan: float):
            if not module_manager.is_enabled("calculator"):
                await interaction.response.send_message("⚠️ Modul Kalkulator Kesehatan sedang dinonaktifkan.", ephemeral=True)
                return
            await interaction.response.defer()
            try:
                result = calculate_bmi(berat_badan, tinggi_badan)
                embed = discord.Embed(
                    title="📊 Hasil Perhitungan BMI",
                    description=f"Berat badan: {berat_badan} kg\nTinggi badan: {tinggi_badan} cm",
                    color=0x00ff88,
                )
                embed.add_field(name="BMI", value=result["bmi"], inline=True)
                embed.add_field(name="Kategori", value=result["category"], inline=True)
                embed.add_field(name="Saran Mirai", value=result["advice"], inline=False)
                embed.set_footer(text=f"Diminta oleh {interaction.user.display_name}")
                await interaction.followup.send(embed=embed)
            except ValueError as e:
                await interaction.followup.send(f"⚠️ Error: {e}", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"⚠️ Terjadi kesalahan: {str(e)[:100]}", ephemeral=True)

        # ── /water ──────────────────────────────────────────────────────────
        @tree.command(name="water", description="Hitung perkiraan kebutuhan air harianmu")
        @app_commands.describe(berat_badan="Berat badanmu dalam kilogram (contoh: 65.5)")
        async def water_command(interaction: discord.Interaction, berat_badan: float):
            if not module_manager.is_enabled("calculator"):
                await interaction.response.send_message("⚠️ Modul Kalkulator Kesehatan sedang dinonaktifkan.", ephemeral=True)
                return
            await interaction.response.defer()
            try:
                result = calculate_daily_water_intake(berat_badan)
                embed = discord.Embed(
                    title="💧 Kebutuhan Air Harian",
                    description=f"Berat badan: {berat_badan} kg",
                    color=0x00aaff,
                )
                embed.add_field(name="Perkiraan Kebutuhan", value=result["water_liter"], inline=True)
                embed.add_field(name="Saran Mirai", value=result["advice"], inline=False)
                embed.set_footer(text=f"Diminta oleh {interaction.user.display_name}")
                await interaction.followup.send(embed=embed)
            except ValueError as e:
                await interaction.followup.send(f"⚠️ Error: {e}", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"⚠️ Terjadi kesalahan: {str(e)[:100]}", ephemeral=True)