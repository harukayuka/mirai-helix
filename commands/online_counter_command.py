"""
commands/online_counter_command.py
───────────────────────────────────
Slash command group untuk /online_counter.
"""

import discord
from discord import app_commands
from commands.base import BaseCommand

# Will be set by CommandGroup at init
_online_counter_manager = None


def set_online_counter_manager(ocm):
    global _online_counter_manager
    _online_counter_manager = ocm


class OnlineCounterCommands(BaseCommand):
    def register(self, tree: app_commands.CommandTree):
        oc_group = app_commands.Group(
            name="online_counter", description="Pengaturan penghitung user online"
        )

        @oc_group.command(name="on", description="Aktifkan penghitung user online di voice channel")
        @app_commands.describe(channel="Voice channel untuk menampilkan jumlah user online")
        @app_commands.default_permissions(administrator=True)
        async def oc_on(interaction: discord.Interaction, channel: discord.VoiceChannel):
            if not _online_counter_manager:
                await interaction.response.send_message("⚠️ Online counter manager belum diinisialisasi.", ephemeral=True)
                return
            await _online_counter_manager.start_counter(interaction.guild_id, channel.id)
            await interaction.response.send_message(
                f"✅ Penghitung user online diaktifkan di {channel.mention}.", ephemeral=True
            )

        @oc_group.command(name="off", description="Nonaktifkan penghitung user online")
        @app_commands.default_permissions(administrator=True)
        async def oc_off(interaction: discord.Interaction):
            if not _online_counter_manager:
                await interaction.response.send_message("⚠️ Online counter manager belum diinisialisasi.", ephemeral=True)
                return
            if await _online_counter_manager.stop_counter(interaction.guild_id):
                await interaction.response.send_message("✅ Penghitung user online dinonaktifkan.", ephemeral=True)
            else:
                await interaction.response.send_message("ℹ️ Penghitung user online tidak aktif di server ini.", ephemeral=True)

        @oc_group.command(name="status", description="Cek status penghitung user online")
        async def oc_status(interaction: discord.Interaction):
            if not _online_counter_manager:
                await interaction.response.send_message("⚠️ Online counter manager belum diinisialisasi.", ephemeral=True)
                return
            st = await _online_counter_manager.get_counter_status(interaction.guild_id)
            if st["active"]:
                mention = f"<#{st['channel_id']}>" if st["channel_id"] else "Tidak diatur"
                await interaction.response.send_message(f"✅ Penghitung user online aktif di {mention}.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Penghitung user online tidak aktif.", ephemeral=True)

        tree.add_command(oc_group)