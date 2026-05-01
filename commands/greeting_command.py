"""
commands/greeting_command.py
────────────────────────────
Slash command group untuk /greeting (Welcome & Goodbye).
"""

import discord
from discord import app_commands
from commands.base import BaseCommand


class GreetingCommands(BaseCommand):
    def register(self, tree: app_commands.CommandTree):
        greeting_group = app_commands.Group(
            name="greeting", description="Pengaturan fitur Welcome & Goodbye"
        )

        @greeting_group.command(name="status", description="Cek status fitur greeting di server ini")
        async def greeting_status(interaction: discord.Interaction):
            from core.auto_greeting import auto_greeting

            enabled = auto_greeting.is_enabled(interaction.guild_id)
            config = auto_greeting._load_config()
            guild_cfg = config.get("guilds", {}).get(str(interaction.guild_id), {})
            channel_id = guild_cfg.get("channel_id")
            mention = f"<#{channel_id}>" if channel_id else "Otomatis (System/Default)"

            embed = discord.Embed(title="✨ Pengaturan Greeting", color=discord.Color.blue())
            embed.add_field(name="Status", value="✅ Aktif" if enabled else "❌ Nonaktif", inline=True)
            embed.add_field(name="Channel", value=mention, inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @greeting_group.command(name="toggle", description="Aktifkan atau nonaktifkan fitur greeting")
        @app_commands.describe(status="Pilih status fitur")
        @app_commands.choices(status=[
            app_commands.Choice(name="Aktifkan", value="enable"),
            app_commands.Choice(name="Nonaktifkan", value="disable"),
        ])
        @app_commands.default_permissions(administrator=True)
        async def greeting_toggle(interaction: discord.Interaction, status: app_commands.Choice[str]):
            from core.auto_greeting import auto_greeting

            is_enabled = status.value == "enable"
            auto_greeting.set_enabled(interaction.guild_id, is_enabled)
            msg = "✅ Fitur greeting telah **diaktifkan**." if is_enabled else "❌ Fitur greeting telah **dinonaktifkan**."
            await interaction.response.send_message(msg, ephemeral=True)

        @greeting_group.command(name="setchannel", description="Atur channel khusus untuk pesan greeting")
        @app_commands.describe(channel="Pilih channel untuk pesan greeting")
        @app_commands.default_permissions(administrator=True)
        async def greeting_setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
            from core.auto_greeting import auto_greeting

            auto_greeting.set_channel(interaction.guild_id, channel.id)
            await interaction.response.send_message(f"✅ Channel greeting diatur ke {channel.mention}.", ephemeral=True)

        tree.add_command(greeting_group)