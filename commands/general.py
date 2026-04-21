import discord
from discord import app_commands
from commands.base import BaseCommand
from memory import get_history

class GeneralCommands(BaseCommand):
    def register(self, tree: app_commands.CommandTree):
        @tree.command(name="ping", description="Cek respons bot")
        async def ping(interaction: discord.Interaction):
            latency = round(self.bot.latency * 1000)
            await interaction.response.send_message(f"Pong! 🏓 **{latency}ms**")

        @tree.command(name="info", description="Info tentang Mirai")
        async def info(interaction: discord.Interaction):
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

        @tree.command(name="status", description="Lihat status bot")
        async def status(interaction: discord.Interaction):
            total_history = len(get_history())
            embed = discord.Embed(
                title="📊 **Status Bot**",
                color=0x3498db
            )
            embed.add_field(name="Model AI", value="Gemini 2.5 Flash", inline=True)
            embed.add_field(name="Total Pesan di History", value=str(total_history), inline=True)
            embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
            await interaction.response.send_message(embed=embed)
