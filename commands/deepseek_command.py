"""
commands/deepseek_command.py
────────────────────────────
Slash command group untuk /deepseek (manajemen batch & model DeepSeek).
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


class DeepSeekCommands(BaseCommand):
    def register(self, tree: app_commands.CommandTree):
        deepseek_group = app_commands.Group(
            name="deepseek", description="Manajemen batch DeepSeek V4 Pro / Flash"
        )

        # ── add ─────────────────────────────────────────────────────────────
        @deepseek_group.command(name="add", description="Tambah channel untuk pemrosesan batch")
        @app_commands.describe(channel="Channel yang ingin ditambahkan")
        @app_commands.default_permissions(administrator=True)
        async def deepseek_add(interaction: discord.Interaction, channel: discord.TextChannel):
            await interaction.response.defer(ephemeral=True)
            if await qwen_batch.add_channel(channel.id):
                await interaction.followup.send(f"✅ Channel {channel.mention} berhasil ditambahkan.", ephemeral=True)
            else:
                await interaction.followup.send(f"ℹ️ Channel {channel.mention} sudah ada dalam daftar.", ephemeral=True)

        # ── remove ──────────────────────────────────────────────────────────
        @deepseek_group.command(name="remove", description="Hapus channel dari pemrosesan batch")
        @app_commands.describe(channel="Channel yang ingin dihapus")
        @app_commands.default_permissions(administrator=True)
        async def deepseek_remove(interaction: discord.Interaction, channel: discord.TextChannel):
            await interaction.response.defer(ephemeral=True)
            if await qwen_batch.remove_channel(channel.id):
                await interaction.followup.send(f"✅ Channel {channel.mention} berhasil dihapus.", ephemeral=True)
            else:
                await interaction.followup.send(f"ℹ️ Channel {channel.mention} tidak ditemukan.", ephemeral=True)

        # ── status ──────────────────────────────────────────────────────────
        @deepseek_group.command(name="status", description="Cek status modul DeepSeek dan daftar channel")
        async def deepseek_status(interaction: discord.Interaction):
            await interaction.response.defer()
            from ai.deepseek_client import get_active_model, get_model_display_name

            is_enabled = module_manager.is_enabled("deepseek")
            channels = qwen_batch.config.get("enabled_channels", [])
            last_run = qwen_batch.config.get("last_run", "Belum pernah")
            auto_cfg = qwen_batch.get_auto_run_config()
            schedule_text = (
                f"Setiap hari jam {auto_cfg['hour']:02d}:{auto_cfg['minute']:02d} WIB"
                if auto_cfg.get("enabled") else "Auto-run belum aktif"
            )
            channel_mentions = [f"<#{cid}>" for cid in channels] if channels else ["Tidak ada"]
            current_model = get_active_model()
            model_name = get_model_display_name(current_model)

            embed = discord.Embed(title="🤖 Status DeepSeek Batch Processing", color=0x00aaff)
            embed.add_field(name="Modul Aktif", value="✅ Ya" if is_enabled else "❌ Tidak", inline=True)
            embed.add_field(name="Model Aktif", value=f"**{model_name}**", inline=True)
            embed.add_field(name="Terakhir Berjalan", value=last_run, inline=False)
            embed.add_field(name="Channel Terdaftar", value=", ".join(channel_mentions), inline=False)
            embed.set_footer(text=f"Jadwal auto-run: {schedule_text}")
            await interaction.followup.send(embed=embed)

        # ── toggle ──────────────────────────────────────────────────────────
        @deepseek_group.command(name="toggle", description="Aktifkan/nonaktifkan modul DeepSeek")
        @app_commands.describe(status="Status aktif (True/False)")
        @app_commands.default_permissions(administrator=True)
        async def deepseek_toggle(interaction: discord.Interaction, status: bool):
            await interaction.response.defer(ephemeral=True)
            module_manager.set_status("deepseek", status)
            await interaction.followup.send(
                f"✅ Modul DeepSeek telah {'diaktifkan' if status else 'dinonaktifkan'}.", ephemeral=True
            )

        # ── run ─────────────────────────────────────────────────────────────
        @deepseek_group.command(name="run", description="Jalankan batch DeepSeek sekarang juga")
        @app_commands.describe(channel="Channel tujuan hasil (akan di-override jika Channel Paksa aktif)")
        @app_commands.default_permissions(administrator=True)
        async def deepseek_run(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
            await interaction.response.defer(ephemeral=True)
            forced_channel_id = qwen_batch.config.get("forced_delivery_channel_id")
            forced_channel_mention = None
            if forced_channel_id and interaction.guild:
                ch = interaction.guild.get_channel(forced_channel_id)
                if ch:
                    forced_channel_mention = ch.mention
            target_channel = channel or interaction.channel
            if not target_channel or not hasattr(target_channel, "id"):
                await interaction.followup.send("❌ Channel tujuan tidak valid.", ephemeral=True)
                return

            result = await qwen_batch.process_batch(self.bot)
            status = result.get("status")
            if status == "completed":
                msg = (
                    f"✅ Batch DeepSeek selesai.\n"
                    f"👥 Total: {result.get('total_users', 0)}\n"
                    f"✅ Diproses: {result.get('processed_users', 0)}\n"
                    f"🧹 Kosong: {result.get('skipped_empty_users', 0)}"
                )
                if result.get("result_file"):
                    msg += f"\n📁 `{result['result_file']}`"
                msg += f"\n📨 Dikirim ke: {forced_channel_mention or target_channel.mention}"
                await interaction.followup.send(msg, ephemeral=True)
            else:
                msgs = {
                    "disabled": "⚠️ Modul dinonaktifkan. Aktifkan dengan `/deepseek toggle`.",
                    "empty": "ℹ️ Tidak ada data chat.",
                }
                await interaction.followup.send(msgs.get(status, f"❌ {result.get('message', 'Error')}"), ephemeral=True)

        # ── autorun ─────────────────────────────────────────────────────────
        @deepseek_group.command(name="autorun", description="Atur auto-run DeepSeek (jam dan channel)")
        @app_commands.describe(hour="Jam (0-23)", minute="Menit (0-59)", channel="Channel tujuan (opsional)")
        @app_commands.default_permissions(administrator=True)
        async def deepseek_autorun(interaction: discord.Interaction, hour: int, minute: int, channel: Optional[discord.TextChannel] = None):
            await interaction.response.defer(ephemeral=True)
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                await interaction.followup.send("❌ Format waktu tidak valid.", ephemeral=True)
                return
            try:
                qwen_batch.set_auto_run(hour, minute, channel.id if channel else None)
            except Exception as e:
                await interaction.followup.send(f"❌ {str(e)[:100]}", ephemeral=True)
                return
            if not qwen_batch._auto_run_task or qwen_batch._auto_run_task.done():
                qwen_batch.start_auto_run(self.bot)
            await interaction.followup.send(
                f"✅ Auto-run DeepSeek: **{hour:02d}:{minute:02d}** → {channel.mention if channel else 'default'}",
                ephemeral=True
            )

        # ── autorun_status ──────────────────────────────────────────────────
        @deepseek_group.command(name="autorun_status", description="Cek status auto-run DeepSeek")
        async def deepseek_autorun_status(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            cfg = qwen_batch.get_auto_run_config()
            embed = discord.Embed(title="⏰ Status Auto-Run DeepSeek", color=0x00aaff)
            if cfg.get("enabled"):
                embed.add_field(name="Status", value="✅ Aktif", inline=True)
                embed.add_field(name="Waktu", value=f"**{cfg['hour']:02d}:{cfg['minute']:02d}** WIB", inline=True)
            else:
                embed.add_field(name="Status", value="❌ Tidak aktif", inline=True)
            await interaction.followup.send(embed=embed, ephemeral=True)

        # ── forced_channel ──────────────────────────────────────────────────
        @deepseek_group.command(name="forced_channel", description="Set channel paksa hasil DeepSeek")
        @app_commands.describe(action="set atau remove", channel="Channel tujuan (wajib untuk set)")
        @app_commands.default_permissions(administrator=True)
        async def deepseek_forced_channel(interaction: discord.Interaction, action: str, channel: Optional[discord.TextChannel] = None):
            await interaction.response.defer(ephemeral=True)
            if action.lower() == "set":
                if not channel:
                    await interaction.followup.send("❌ Parameter channel diperlukan.", ephemeral=True)
                    return
                qwen_batch.set_forced_channel(channel.id)
                await interaction.followup.send(f"✅ Channel paksa → {channel.mention}", ephemeral=True)
            elif action.lower() == "remove":
                qwen_batch.remove_forced_channel()
                await interaction.followup.send("🗑️ Channel paksa dihapus.", ephemeral=True)
            else:
                await interaction.followup.send("❌ Aksi: 'set' atau 'remove'.", ephemeral=True)

        # ── test ────────────────────────────────────────────────────────────
        @deepseek_group.command(name="test", description="Tes prompt ke DeepSeek")
        @app_commands.describe(prompt="Prompt untuk diuji", private="Hanya kamu? (default: True)")
        @app_commands.default_permissions(administrator=True)
        async def deepseek_test(interaction: discord.Interaction, prompt: str, private: bool = True):
            await interaction.response.defer(ephemeral=private)
            result = await qwen_batch.run_test_prompt(prompt)
            if result.get("status") == "completed":
                chunks = qwen_batch.split_for_discord(result["response"])
                await interaction.followup.send(f"🧪 **DeepSeek Response**\n{chunks[0]}", ephemeral=private)
                for c in chunks[1:]:
                    await interaction.followup.send(c, ephemeral=private)
            else:
                await interaction.followup.send(f"❌ {result.get('message', 'Gagal')}", ephemeral=private)

        # ── model ───────────────────────────────────────────────────────────
        @deepseek_group.command(name="model", description="Lihat atau ganti model DeepSeek yang aktif (Pro / Flash)")
        @app_commands.describe(
            model="Pilih model DeepSeek (kosongkan untuk lihat model saat ini)",
            private="Hanya kamu yang bisa lihat? (default: True)"
        )
        @app_commands.choices(model=[
            app_commands.Choice(name="DeepSeek V4 Pro (default, lebih akurat)", value="deepseek-ai/deepseek-v4-pro"),
            app_commands.Choice(name="DeepSeek V4 Flash (lebih cepat, lebih ringan)", value="deepseek-ai/deepseek-v4-flash"),
        ])
        @app_commands.default_permissions(administrator=True)
        async def deepseek_model(
            interaction: discord.Interaction,
            model: Optional[app_commands.Choice[str]] = None,
            private: bool = True
        ):
            await interaction.response.defer(ephemeral=private)
            from ai.deepseek_client import (
                get_active_model, set_active_model,
                get_model_display_name, MODEL_PRO, MODEL_FLASH,
            )

            if model:
                model_id = model.value
                success = set_active_model(model_id)
                if success:
                    name = get_model_display_name(model_id)
                    await interaction.followup.send(
                        f"✅ Model DeepSeek berhasil diganti ke **{name}**\n"
                        f"📋 ID: `{model_id}`\n"
                        f"🔄 Berlaku untuk semua pemanggilan batch & test berikutnya.",
                        ephemeral=private
                    )
                else:
                    await interaction.followup.send("❌ Gagal mengganti model. ID model tidak valid.", ephemeral=private)
            else:
                current = get_active_model()
                name = get_model_display_name(current)
                embed = discord.Embed(title="🧠 Model DeepSeek Saat Ini", color=0x00aaff)
                embed.add_field(name="Nama", value=name, inline=True)
                embed.add_field(name="ID Model", value=f"`{current}`", inline=False)
                embed.add_field(
                    name="Pilihan Model",
                    value=(
                        f"1️⃣ **DeepSeek V4 Pro** `{MODEL_PRO}`\n"
                        f"   → Akurasi tinggi, cocok untuk analisis batch\n"
                        f"2️⃣ **DeepSeek V4 Flash** `{MODEL_FLASH}`\n"
                        f"   → Lebih cepat & ringan, cocok untuk test cepat"
                    ),
                    inline=False
                )
                embed.set_footer(text="Gunakan /deepseek model <nama> untuk mengganti")
                await interaction.followup.send(embed=embed, ephemeral=private)

        tree.add_command(deepseek_group)