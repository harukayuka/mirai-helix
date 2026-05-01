"""
commands/qwen_command.py
────────────────────────
Slash command group untuk /qwen (manajemen batch processing).
Backend-nya sama dengan /deepseek (qwen_batch).
"""

import asyncio
from typing import Optional
import discord
from discord import app_commands
from commands.base import BaseCommand
from core.module_manager import module_manager
import core.qwen_batch as qwen_batch
from utils.logger import setup_logging

logger = setup_logging()


async def send_chunks(
    interaction: discord.Interaction,
    text: str,
    *,
    ephemeral: bool,
    prefix: Optional[str] = None,
):
    """Split panjang teks & kirim dalam beberapa followup."""
    chunk_limit = 1700 if prefix else 1900
    chunks = qwen_batch.split_for_discord(text, limit=chunk_limit)
    first = f"{prefix}\n{chunks[0]}" if prefix else chunks[0]
    await interaction.followup.send(first, ephemeral=ephemeral)
    for c in chunks[1:]:
        await interaction.followup.send(c, ephemeral=ephemeral)


class QwenCommands(BaseCommand):
    def register(self, tree: app_commands.CommandTree):
        qwen_group = app_commands.Group(
            name="qwen", description="Manajemen pemrosesan batch (DeepSeek backend)"
        )

        # ── add ─────────────────────────────────────────────────────────────
        @qwen_group.command(name="add", description="Tambah channel untuk pemrosesan batch")
        @app_commands.describe(channel="Channel yang ingin ditambahkan")
        @app_commands.default_permissions(administrator=True)
        async def qwen_add(interaction: discord.Interaction, channel: discord.TextChannel):
            await interaction.response.defer(ephemeral=True)
            if await qwen_batch.add_channel(channel.id):
                await interaction.followup.send(f"✅ Channel {channel.mention} berhasil ditambahkan.", ephemeral=True)
            else:
                await interaction.followup.send(f"ℹ️ Channel {channel.mention} sudah ada dalam daftar.", ephemeral=True)

        # ── remove ──────────────────────────────────────────────────────────
        @qwen_group.command(name="remove", description="Hapus channel dari pemrosesan batch")
        @app_commands.describe(channel="Channel yang ingin dihapus")
        @app_commands.default_permissions(administrator=True)
        async def qwen_remove(interaction: discord.Interaction, channel: discord.TextChannel):
            await interaction.response.defer(ephemeral=True)
            if await qwen_batch.remove_channel(channel.id):
                await interaction.followup.send(f"✅ Channel {channel.mention} berhasil dihapus.", ephemeral=True)
            else:
                await interaction.followup.send(f"ℹ️ Channel {channel.mention} tidak ditemukan.", ephemeral=True)

        # ── status ──────────────────────────────────────────────────────────
        @qwen_group.command(name="status", description="Cek status modul batch dan daftar channel")
        async def qwen_status(interaction: discord.Interaction):
            await interaction.response.defer()
            from ai.deepseek_client import get_active_model, get_model_display_name

            is_enabled = module_manager.is_enabled("deepseek")
            channels = qwen_batch.config.get("enabled_channels", [])
            last_run = qwen_batch.config.get("last_run", "Belum pernah")
            auto_cfg = qwen_batch.get_auto_run_config()

            if auto_cfg.get("enabled"):
                h, m = auto_cfg.get("hour", 0), auto_cfg.get("minute", 0)
                schedule_text = f"Setiap hari jam {h:02d}:{m:02d} WIB"
            else:
                schedule_text = "Auto-run belum aktif"

            channel_mentions = [f"<#{cid}>" for cid in channels] if channels else ["Tidak ada"]
            model_name = get_model_display_name(get_active_model())

            embed = discord.Embed(title="🤖 Status Batch Processing", color=0x7f77dd)
            embed.add_field(name="Modul Aktif", value="✅ Ya" if is_enabled else "❌ Tidak", inline=True)
            embed.add_field(name="Model Aktif", value=f"**{model_name}**", inline=True)
            embed.add_field(name="Terakhir Berjalan", value=last_run, inline=True)
            embed.add_field(name="Channel Terdaftar", value=", ".join(channel_mentions), inline=False)
            embed.set_footer(text=f"Jadwal auto-run: {schedule_text}")
            await interaction.followup.send(embed=embed)

        # ── toggle ──────────────────────────────────────────────────────────
        @qwen_group.command(name="toggle", description="Aktifkan/nonaktifkan modul batch")
        @app_commands.describe(status="Status aktif (True/False)")
        @app_commands.default_permissions(administrator=True)
        async def qwen_toggle(interaction: discord.Interaction, status: bool):
            await interaction.response.defer(ephemeral=True)
            module_manager.set_status("deepseek", status)
            await interaction.followup.send(
                f"✅ Modul batch telah {'diaktifkan' if status else 'dinonaktifkan'}.", ephemeral=True
            )

        # ── run ─────────────────────────────────────────────────────────────
        @qwen_group.command(name="run", description="Jalankan batch processing sekarang juga")
        @app_commands.describe(channel="Channel tujuan hasil (akan di-override jika Channel Paksa aktif)")
        @app_commands.default_permissions(administrator=True)
        async def qwen_run(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
            await interaction.response.defer(ephemeral=True)
            forced_channel_id = qwen_batch.config.get("forced_delivery_channel_id")
            forced_channel_mention = None
            if forced_channel_id and interaction.guild:
                ch = interaction.guild.get_channel(forced_channel_id)
                if ch:
                    forced_channel_mention = ch.mention

            target = channel or interaction.channel
            if not target or not hasattr(target, "id"):
                await interaction.followup.send("❌ Channel tujuan tidak valid.", ephemeral=True)
                return

            result = await qwen_batch.process_batch(self.bot)
            status = result.get("status")

            if status == "completed":
                msg = (
                    f"✅ Batch selesai dijalankan.\n"
                    f"👥 Total antrean: {result.get('total_users', 0)}\n"
                    f"✅ Berhasil diproses: {result.get('processed_users', 0)}\n"
                    f"🧹 File kosong dibersihkan: {result.get('skipped_empty_users', 0)}"
                )
                if result.get("result_file"):
                    msg += f"\n📁 Hasil tersimpan: `{result['result_file']}`"
                if forced_channel_mention:
                    msg += f"\n🚨 **Channel Paksa Aktif**: Hasil dikirim ke {forced_channel_mention}."
                else:
                    msg += f"\n📨 Hasil dikirim ke: {target.mention}."
                await interaction.followup.send(msg, ephemeral=True)
                return

            status_msgs = {
                "busy": "ℹ️ Batch sedang berjalan. Tunggu sebentar lalu coba lagi.",
                "client_unavailable": f"❌ {result.get('message', 'Client belum siap.')}",
                "disabled": "⚠️ Modul batch sedang dinonaktifkan. Aktifkan dulu dengan `/qwen toggle`.",
                "empty": "ℹ️ Tidak ada data chat yang menunggu untuk diproses.",
            }
            await interaction.followup.send(
                status_msgs.get(status, f"❌ Gagal: {result.get('message', 'Unknown error')}"),
                ephemeral=True,
            )

        # ── autorun ─────────────────────────────────────────────────────────
        @qwen_group.command(name="autorun", description="Atur auto-run batch (jam dan channel)")
        @app_commands.describe(
            hour="Jam (0-23)",
            minute="Menit (0-59)",
            channel="Channel tujuan (opsional)",
        )
        @app_commands.default_permissions(administrator=True)
        async def qwen_autorun_set(interaction: discord.Interaction, hour: int, minute: int, channel: Optional[discord.TextChannel] = None):
            await interaction.response.defer(ephemeral=True)
            if not (0 <= hour <= 23):
                await interaction.followup.send("❌ Jam tidak valid (0-23).", ephemeral=True)
                return
            if not (0 <= minute <= 59):
                await interaction.followup.send("❌ Menit tidak valid (0-59).", ephemeral=True)
                return

            delivery_id = channel.id if channel else None
            try:
                success = qwen_batch.set_auto_run(hour, minute, delivery_id)
            except Exception as e:
                await interaction.followup.send(f"❌ Error: {str(e)[:100]}", ephemeral=True)
                return

            if success:
                if not qwen_batch._auto_run_task or qwen_batch._auto_run_task.done():
                    qwen_batch.start_auto_run(self.bot)
                info = channel.mention if channel else "Channel pertama di enabled_channels"
                await interaction.followup.send(
                    f"✅ Auto-run berhasil disetel!\n"
                    f"🕐 Waktu: **{hour:02d}:{minute:02d}** setiap hari\n"
                    f"📨 Hasil dikirim ke: {info}\n"
                    f"🔄 Scheduler telah dimulai.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send("❌ Gagal mengatur auto-run.", ephemeral=True)

        # ── autorun_status ──────────────────────────────────────────────────
        @qwen_group.command(name="autorun_status", description="Cek status auto-run batch")
        async def qwen_autorun_status(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            cfg = qwen_batch.get_auto_run_config()
            if cfg.get("enabled"):
                hour, minute = cfg["hour"], cfg["minute"]
                channel_id = cfg.get("delivery_channel_id")
                info = f"<#{channel_id}>" if channel_id else "Channel pertama di enabled_channels"
                embed = discord.Embed(title="⏰ Status Auto-Run", color=0x7f77dd)
                embed.add_field(name="Status", value="✅ Aktif", inline=True)
                embed.add_field(name="Waktu", value=f"**{hour:02d}:{minute:02d}** WIB", inline=True)
                embed.add_field(name="Channel Tujuan", value=info, inline=False)
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(title="⏰ Status Auto-Run", color=0xff6b6b)
                embed.add_field(name="Status", value="❌ Tidak aktif", inline=True)
                embed.add_field(name="Cara Aktifkan", value="Gunakan `/qwen autorun`", inline=False)
                await interaction.followup.send(embed=embed, ephemeral=True)

        # ── forced_channel ──────────────────────────────────────────────────
        @qwen_group.command(name="forced_channel", description="Set channel paksa untuk hasil analisis")
        @app_commands.describe(action="Aksi: set atau remove", channel="Channel tujuan (wajib untuk set)")
        @app_commands.default_permissions(administrator=True)
        async def qwen_forced_channel(interaction: discord.Interaction, action: str, channel: Optional[discord.TextChannel] = None):
            await interaction.response.defer(ephemeral=True)
            if action.lower() == "set":
                if not channel:
                    await interaction.followup.send("❌ Parameter channel diperlukan.", ephemeral=True)
                    return
                qwen_batch.set_forced_channel(channel.id)
                await interaction.followup.send(f"✅ Channel paksa → {channel.mention}", ephemeral=True)
                logger.info("[Admin] %s set forced channel ke %s", interaction.user.name, channel.id)
            elif action.lower() == "remove":
                qwen_batch.remove_forced_channel()
                await interaction.followup.send("🗑️ Channel paksa dihapus.", ephemeral=True)
                logger.info("[Admin] %s remove forced channel", interaction.user.name)
            else:
                await interaction.followup.send("❌ Aksi: 'set' atau 'remove'.", ephemeral=True)

        # ── forced_channel_status ───────────────────────────────────────────
        @qwen_group.command(name="forced_channel_status", description="Cek status channel paksa")
        @app_commands.default_permissions(administrator=True)
        async def qwen_forced_channel_status(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            forced_id = qwen_batch.config.get("forced_delivery_channel_id")
            if forced_id:
                ch = interaction.guild.get_channel(forced_id) if interaction.guild else None
                mention = ch.mention if ch else f"<#{forced_id}> (tidak ditemukan)"
                await interaction.followup.send(f"📍 **Channel Paksa Aktif**\nChannel: {mention}", ephemeral=True)
            else:
                await interaction.followup.send("ℹ️ **Tidak Ada Channel Paksa** — Mode normal.", ephemeral=True)

        # ── test ────────────────────────────────────────────────────────────
        @qwen_group.command(name="test", description="Tes prompt ke model DeepSeek")
        @app_commands.describe(prompt="Prompt yang ingin dikirim", private="Hasil hanya kamu? (default: True)")
        @app_commands.default_permissions(administrator=True)
        async def qwen_test(interaction: discord.Interaction, prompt: str, private: bool = True):
            await interaction.response.defer(ephemeral=private)
            result = await qwen_batch.run_test_prompt(prompt)
            status = result.get("status")
            if status != "completed":
                errors = {
                    "invalid": "⚠️ Prompt tidak valid.",
                    "client_unavailable": f"❌ {result.get('message', 'Client belum siap.')}",
                    "empty": "⚠️ Model merespons tanpa teks.",
                }
                await interaction.followup.send(errors.get(status, f"❌ {result.get('message', 'Error')}"), ephemeral=private)
                return
            await send_chunks(interaction, result["response"], ephemeral=private, prefix="🧪 **DeepSeek Response**")

        # ── result ──────────────────────────────────────────────────────────
        @qwen_group.command(name="result", description="Upload hasil analisis batch ke channel tertentu")
        @app_commands.describe(channel="Channel tujuan untuk upload hasil")
        @app_commands.default_permissions(administrator=True)
        async def qwen_result(interaction: discord.Interaction, channel: discord.TextChannel):
            await interaction.response.defer(ephemeral=True)
            try:
                from pathlib import Path
                import json

                ds_dir = Path("data/deepseek_results")
                qw_dir = Path("data/qwen_results")
                ds_files = list(ds_dir.glob("*.txt")) if ds_dir.exists() else []
                qw_files = list(qw_dir.glob("*.json")) if qw_dir.exists() else []

                if not ds_files and not qw_files:
                    await interaction.followup.send("❌ Tidak ada file hasil analisis.", ephemeral=True)
                    return

                if ds_files:
                    latest = max(ds_files, key=lambda f: f.stat().st_mtime)
                    content = latest.read_text(encoding="utf-8")
                    header = f"📊 **Hasil Analisis Batch**\n📁 `{latest.name}`\n\n"
                    for chunk in qwen_batch.split_for_discord(header + content):
                        await channel.send(chunk)
                        await asyncio.sleep(0.5)
                else:
                    latest = max(qw_files, key=lambda f: f.stat().st_mtime)
                    results = json.loads(latest.read_text(encoding="utf-8"))
                    ts = results.get("timestamp", "Unknown")
                    total = results.get("total_users", 0)
                    await channel.send(f"📊 **Hasil Analisis Batch**\n🕒 {ts}\n👥 Total User: {total}\n\n")
                    for ur in results.get("results", []):
                        uid = ur.get("user_id", "Unknown")
                        analysis = ur.get("analysis", "Tidak ada analisis")
                        for chunk in qwen_batch.split_for_discord(f"**User ID:** <@{uid}>\n{analysis}"):
                            await channel.send(chunk)
                            await asyncio.sleep(0.5)

                await interaction.followup.send(f"✅ Hasil berhasil diupload ke {channel.mention}", ephemeral=True)
            except Exception as e:
                logger.error(f"[Batch] Error upload results: {e}")
                await interaction.followup.send(f"❌ Gagal upload: {str(e)[:100]}", ephemeral=True)

        tree.add_command(qwen_group)