"""
commands/module_command.py
──────────────────────────
Slash command group untuk /module (manajemen aktif/nonaktif modul).
"""

import discord
from discord import app_commands
from commands.base import BaseCommand
from core.module_manager import module_manager


class ModuleCommands(BaseCommand):
    def register(self, tree: app_commands.CommandTree):
        module_group = app_commands.Group(
            name="module", description="Pengaturan aktif/nonaktif modul bot"
        )

        @module_group.command(name="status", description="Cek status semua modul")
        @app_commands.default_permissions(administrator=True)
        async def module_status(interaction: discord.Interaction):
            status = module_manager.get_all_status()
            embed = discord.Embed(title="🛠️ Status Modul Mirai", color=0x3498db)
            for mod, enabled in status.items():
                embed.add_field(
                    name=mod.capitalize(),
                    value="✅ Aktif" if enabled else "❌ Nonaktif",
                    inline=True,
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @module_group.command(name="toggle", description="Aktifkan atau nonaktifkan modul")
        @app_commands.describe(modul="Pilih modul", status="Pilih status")
        @app_commands.choices(
            modul=[
                app_commands.Choice(name="Calculator", value="calculator"),
                app_commands.Choice(name="Weather", value="weather"),
                app_commands.Choice(name="News", value="news"),
                app_commands.Choice(name="Greeting", value="greeting"),
                app_commands.Choice(name="Wellness", value="wellness"),
            ],
            status=[
                app_commands.Choice(name="Aktifkan", value="enable"),
                app_commands.Choice(name="Nonaktifkan", value="disable"),
            ],
        )
        @app_commands.default_permissions(administrator=True)
        async def module_toggle(
            interaction: discord.Interaction,
            modul: app_commands.Choice[str],
            status: app_commands.Choice[str],
        ):
            is_enabled = status.value == "enable"
            module_manager.set_status(modul.value, is_enabled)
            msg = (
                f"✅ Modul **{modul.name}** telah **diaktifkan**."
                if is_enabled
                else f"❌ Modul **{modul.name}** telah **dinonaktifkan**."
            )
            await interaction.response.send_message(msg, ephemeral=True)

        tree.add_command(module_group)