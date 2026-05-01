"""
commands/bedtime_command.py
───────────────────────────
Slash command group untuk /bedtime (pengingat waktu tidur).
"""

import discord
from discord import app_commands
from commands.base import BaseCommand
from utils.logger import setup_logging

logger = setup_logging()

# Will be set by CommandGroup at init
_reminder_manager = None


def set_reminder_manager(rm):
    global _reminder_manager
    _reminder_manager = rm


class BedtimeCommands(BaseCommand):
    def register(self, tree: app_commands.CommandTree):
        bedtime_group = app_commands.Group(
            name="bedtime", description="Pengaturan pengingat waktu tidur"
        )

        @bedtime_group.command(name="on", description="Aktifkan pengingat waktu tidur")
        @app_commands.describe(channel="Channel untuk mengirim pengingat")
        @app_commands.default_permissions(administrator=True)
        async def bedtime_on(interaction: discord.Interaction, channel: discord.TextChannel):
            if not _reminder_manager:
                await interaction.response.send_message("⚠️ Reminder manager belum diinisialisasi.", ephemeral=True)
                return
            await _reminder_manager.start_reminder(interaction.guild_id, channel.id)
            await interaction.response.send_message(
                f"✅ Pengingat waktu tidur diaktifkan di {channel.mention} setiap jam 21:00.", ephemeral=True
            )

        @bedtime_group.command(name="off", description="Nonaktifkan pengingat waktu tidur")
        @app_commands.default_permissions(administrator=True)
        async def bedtime_off(interaction: discord.Interaction):
            if not _reminder_manager:
                await interaction.response.send_message("⚠️ Reminder manager belum diinisialisasi.", ephemeral=True)
                return
            if await _reminder_manager.stop_reminder(interaction.guild_id):
                await interaction.response.send_message("✅ Pengingat waktu tidur dinonaktifkan.", ephemeral=True)
            else:
                await interaction.response.send_message("ℹ️ Pengingat waktu tidur tidak aktif di server ini.", ephemeral=True)

        @bedtime_group.command(name="status", description="Cek status pengingat waktu tidur")
        async def bedtime_status(interaction: discord.Interaction):
            if not _reminder_manager:
                await interaction.response.send_message("⚠️ Reminder manager belum diinisialisasi.", ephemeral=True)
                return
            st = await _reminder_manager.get_reminder_status(interaction.guild_id)
            if st["active"]:
                mention = f"<#{st['channel_id']}>" if st["channel_id"] else "Tidak diatur"
                await interaction.response.send_message(
                    f"✅ Pengingat waktu tidur aktif di {mention} setiap jam 21:00.", ephemeral=True
                )
            else:
                await interaction.response.send_message("❌ Pengingat waktu tidur tidak aktif.", ephemeral=True)

        tree.add_command(bedtime_group)