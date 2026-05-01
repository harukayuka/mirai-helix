from typing import Optional
import discord
from discord import app_commands
from commands.base import BaseCommand
from utils.logger import setup_logging
from pathlib import Path

logger = setup_logging()

class GeneralCommands(BaseCommand):
    def register(self, tree: app_commands.CommandTree):
        @tree.command(name="report", description="Lihat laporan batch processing terbaru")
        @app_commands.describe(
            channel="Channel tujuan upload laporan (opsional, default: channel ini)"
        )
        async def report(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
            """Upload laporan batch processing terbaru ke channel."""
            await interaction.response.defer(ephemeral=True)
            target = channel or interaction.channel
            if not target or not hasattr(target, "send"):
                await interaction.followup.send("❌ Channel tidak valid.", ephemeral=True)
                return

            # Cari file laporan terbaru
            ds_dir = Path("data/deepseek_results")
            qw_dir = Path("data/qwen_results")
            ds_files = list(ds_dir.glob("*.txt")) if ds_dir.exists() else []
            qw_files = list(qw_dir.glob("*.txt")) if qw_dir.exists() else []
            all_files = ds_files + qw_files

            if not all_files:
                await interaction.followup.send("ℹ️ Belum ada laporan batch tersimpan.", ephemeral=True)
                return

            latest = max(all_files, key=lambda f: f.stat().st_mtime)
            content = latest.read_text(encoding="utf-8")

            # Kirim ke channel
            try:
                from core import qwen_batch
                header = f"📊 **Laporan Batch Terbaru** — `{latest.name}`\n\n"
                for chunk in qwen_batch.split_for_discord(header + content):
                    await target.send(chunk)
                await interaction.followup.send(f"✅ Laporan dikirim ke {target.mention}", ephemeral=True)
            except Exception as e:
                logger.error(f"[Report] Error: {e}")
                await interaction.followup.send(f"❌ Gagal mengirim laporan: {str(e)[:100]}", ephemeral=True)
