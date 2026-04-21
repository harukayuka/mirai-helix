# core/command.py - Slash Commands untuk Mirai Bot
"""
Implementasi slash commands untuk Mirai Discord Bot.
Commands: /ask, /ping, /info, /clear, /status
"""
import asyncio
import discord
from discord import app_commands
from typing import Optional
from datetime import datetime
import sys
import os
from utils.logger import setup_logging
from utils.reminder import ReminderManager
from utils.online_counter import OnlineCounterManager

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from memory import get_history, clear_history
from ai.gemini import GeminiClient
from utils.calculator import calculate_bmi, calculate_daily_water_intake
from core.module_manager import module_manager
import core.qwen_batch as qwen_batch

logger = setup_logging()

# Inisialisasi Gemini client (BMKGClient sudah ada di dalam gemini.bmkg)
gemini = GeminiClient()
reminder_manager = None  # Akan diinisialisasi di main.py
online_counter_manager = None  # Akan diinisialisasi di main.py


class CommandGroup:
    """Kelas untuk mengelompokkan semua slash commands Mirai."""

    def __init__(self, bot: discord.Client):
        """
        Initialize CommandGroup.
        Args:
            bot: Discord client instance
        """
        self.bot = bot
        self.tree = app_commands.CommandTree(bot)
        self.setup_commands()

    def set_reminder_manager(self, manager):
        global reminder_manager
        reminder_manager = manager

    def set_online_counter_manager(self, manager):
        global online_counter_manager
        online_counter_manager = manager
    
    def setup_commands(self):
        """Daftarkan semua slash commands."""
        # ===== COMMAND: /ask =====
        @self.tree.command(name="ask", description="Tanya Mirai tentang kesehatan atau ceritakan keluhanmu")
        @app_commands.describe(
            pertanyaan="Apa yang ingin kamu tanyakan atau ceritakan?",
            private="Jawaban hanya kamu yang bisa lihat? (default: False)"
        )
        async def ask_command(
            interaction: discord.Interaction, 
            pertanyaan: str,
            private: bool = False
        ):
            """Slash command untuk bertanya kepada Mirai."""
            await interaction.response.defer(ephemeral=private)
            try:
                # Ambil nama user
                user_name = interaction.user.display_name
                # Format pesan dengan nama user
                user_msg = f"{user_name}: {pertanyaan}"
                # Simpan ke history global
                from memory import add_message
                add_message("user", user_msg)
                # Ambil history
                history = get_history()
                # Generate respons
                reply = await asyncio.to_thread(gemini.generate, history)
                # Simpan respons bot
                add_message("assistant", reply)
                # Kirim balasan
                await interaction.followup.send(reply, ephemeral=private)
            except Exception as e:
                await interaction.followup.send(f"⚠️ Error: {str(e)[:100]}", ephemeral=private)
        
        # ===== COMMAND: /ping =====
        @self.tree.command(name="ping", description="Cek respons bot")
        async def ping_command(interaction: discord.Interaction):
            """Slash command untuk cek latency bot."""
            latency = round(self.bot.latency * 1000)
            await interaction.response.send_message(f"Pong! 🏓 **{latency}ms**")
        
        # ===== COMMAND: /info =====
        @self.tree.command(name="info", description="Info tentang Mirai")
        async def info_command(interaction: discord.Interaction):
            """Slash command untuk lihat informasi Mirai."""
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
        
        # ===== COMMAND: /bmi =====
        @self.tree.command(name="bmi", description="Hitung Body Mass Index (BMI) kamu")
        @app_commands.describe(
            berat_badan="Berat badanmu dalam kilogram (contoh: 65.5)",
            tinggi_badan="Tinggi badanmu dalam centimeter (contoh: 170)"
        )
        async def bmi_command(
            interaction: discord.Interaction,
            berat_badan: float,
            tinggi_badan: float
        ):
            """Slash command untuk menghitung BMI."""
            if not module_manager.is_enabled("calculator"):
                await interaction.response.send_message("⚠️ Modul Kalkulator Kesehatan sedang dinonaktifkan oleh admin.", ephemeral=True)
                return
            await interaction.response.defer()
            try:
                result = calculate_bmi(berat_badan, tinggi_badan)
                embed = discord.Embed(
                    title="📊 Hasil Perhitungan BMI",
                    description=f"Berat badan: {berat_badan} kg\nTinggi badan: {tinggi_badan} cm",
                    color=0x00ff88
                )
                embed.add_field(name="BMI", value=f"{result['bmi']}", inline=True)
                embed.add_field(name="Kategori", value=result['category'], inline=True)
                embed.add_field(name="Saran Mirai", value=result['advice'], inline=False)
                embed.set_footer(text=f"Diminta oleh {interaction.user.display_name}")
                await interaction.followup.send(embed=embed)
            except ValueError as e:
                await interaction.followup.send(f"⚠️ Error: {e}", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"⚠️ Terjadi kesalahan saat menghitung BMI: {str(e)[:100]}", ephemeral=True)

        # ===== COMMAND: /water =====
        @self.tree.command(name="water", description="Hitung perkiraan kebutuhan air harianmu")
        @app_commands.describe(
            berat_badan="Berat badanmu dalam kilogram (contoh: 65.5)"
        )
        async def water_command(
            interaction: discord.Interaction,
            berat_badan: float
        ):
            """Slash command untuk menghitung kebutuhan air harian."""
            if not module_manager.is_enabled("calculator"):
                await interaction.response.send_message("⚠️ Modul Kalkulator Kesehatan sedang dinonaktifkan oleh admin.", ephemeral=True)
                return
            await interaction.response.defer()
            try:
                result = calculate_daily_water_intake(berat_badan)
                embed = discord.Embed(
                    title="💧 Kebutuhan Air Harian",
                    description=f"Berat badan: {berat_badan} kg",
                    color=0x00aaff
                )
                embed.add_field(name="Perkiraan Kebutuhan", value=f"{result['water_liter']} liter", inline=True)
                embed.add_field(name="Saran Mirai", value=result['advice'], inline=False)
                embed.set_footer(text=f"Diminta oleh {interaction.user.display_name}")
                await interaction.followup.send(embed=embed)
            except ValueError as e:
                await interaction.followup.send(f"⚠️ Error: {e}", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"⚠️ Terjadi kesalahan saat menghitung kebutuhan air: {str(e)[:100]}", ephemeral=True)

        # ===== COMMAND: /clear =====
        @self.tree.command(name="clear", description="Hapus riwayat percakapan (hanya admin)")
        @app_commands.default_permissions(administrator=True)
        async def clear_command(interaction: discord.Interaction):
            """Slash command untuk hapus history (admin only)."""
            try:
                from memory import clear_history
                clear_history()
                await interaction.response.send_message(
                    "✅ Riwayat percakapan telah dibersihkan!", 
                    ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(f"❌ Gagal: {e}", ephemeral=True)
        
        # ===== COMMAND: /status =====
        @self.tree.command(name="status", description="Lihat status bot")
        async def status_command(interaction: discord.Interaction):
            """Slash command untuk lihat status bot."""
            total_history = len(get_history())
            embed = discord.Embed(
                title="📊 **Status Bot**",
                color=0x3498db
            )
            embed.add_field(name="Model AI", value="Gemini 2.5 Flash", inline=True)
            embed.add_field(name="Total Pesan di History", value=str(total_history), inline=True)
            embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
            await interaction.response.send_message(embed=embed)

        # ===== COMMAND GROUP: /qwen =====
        qwen_group = app_commands.Group(name="qwen", description="Manajemen pemrosesan batch Qwen-3.5")

        async def send_qwen_followup_chunks(
            interaction: discord.Interaction,
            text: str,
            *,
            ephemeral: bool,
            prefix: Optional[str] = None
        ):
            chunk_limit = 1700 if prefix else 1900
            chunks = qwen_batch.split_for_discord(text, limit=chunk_limit)
            first_message = f"{prefix}\n{chunks[0]}" if prefix else chunks[0]
            await interaction.followup.send(first_message, ephemeral=ephemeral)
            for chunk in chunks[1:]:
                await interaction.followup.send(chunk, ephemeral=ephemeral)

        @qwen_group.command(name="add", description="Tambah channel untuk pemrosesan batch Qwen")
        @app_commands.describe(channel="Channel yang ingin ditambahkan")
        @app_commands.default_permissions(administrator=True)
        async def qwen_add(interaction: discord.Interaction, channel: discord.TextChannel):
            await interaction.response.defer(ephemeral=True)
            if await qwen_batch.add_channel(channel.id):
                await interaction.followup.send(f"✅ Channel {channel.mention} berhasil ditambahkan ke daftar pemrosesan Qwen.", ephemeral=True)
            else:
                await interaction.followup.send(f"ℹ️ Channel {channel.mention} sudah ada dalam daftar.", ephemeral=True)

        @qwen_group.command(name="remove", description="Hapus channel dari pemrosesan batch Qwen")
        @app_commands.describe(channel="Channel yang ingin dihapus")
        @app_commands.default_permissions(administrator=True)
        async def qwen_remove(interaction: discord.Interaction, channel: discord.TextChannel):
            await interaction.response.defer(ephemeral=True)
            if qwen_batch.remove_channel(channel.id):
                await interaction.followup.send(f"✅ Channel {channel.mention} berhasil dihapus dari daftar pemrosesan Qwen.", ephemeral=True)
            else:
                await interaction.followup.send(f"ℹ️ Channel {channel.mention} tidak ditemukan dalam daftar.", ephemeral=True)

        @qwen_group.command(name="status", description="Cek status modul Qwen dan daftar channel")
        async def qwen_status(interaction: discord.Interaction):
            await interaction.response.defer()
            is_enabled = module_manager.is_enabled("qwen")
            channels = qwen_batch.config.get("enabled_channels", [])
            last_run = qwen_batch.config.get("last_run", "Belum pernah")
    
            # PERBAIKAN: Ambil config auto_run untuk footer dinamis
            auto_cfg = qwen_batch.get_auto_run_config()
            if auto_cfg.get("enabled"):
                h = f"{auto_cfg.get('hour', 0):02d}"
                m = f"{auto_cfg.get('minute', 0):02d}"
                schedule_text = f"Setiap hari jam {h}:{m} WIB"
            else:
                schedule_text = "Auto-run belum aktif"
    
            channel_mentions = [f"<#{cid}>" for cid in channels] if channels else ["Tidak ada"]
            embed = discord.Embed(title="🤖 Status Qwen Batch Processing", color=0x7f77dd)
            embed.add_field(name="Modul Aktif", value="✅ Ya" if is_enabled else "❌ Tidak", inline=True)
            embed.add_field(name="Terakhir Berjalan", value=last_run, inline=True)
            embed.add_field(name="Channel Terdaftar", value=", ".join(channel_mentions), inline=False)
            # Footer sekarang dinamis sesuai settingan user
            embed.set_footer(text=f"Jadwal auto-run: {schedule_text}")
            await interaction.followup.send(embed=embed)

        @qwen_group.command(name="toggle", description="Aktifkan/nonaktifkan modul Qwen")
        @app_commands.describe(status="Status aktif (True/False)")
        @app_commands.default_permissions(administrator=True)
        async def qwen_toggle(interaction: discord.Interaction, status: bool):
            await interaction.response.defer(ephemeral=True)
            module_manager.set_status("qwen", status)
            await interaction.followup.send(f"✅ Modul Qwen telah {'diaktifkan' if status else 'dinonaktifkan'}.", ephemeral=True)

        @qwen_group.command(name="run", description="Jalankan batch Qwen sekarang juga")
        @app_commands.describe(channel="Channel tujuan hasil manual run. Default: channel ini (akan di-override jika Channel Paksa aktif)")
        @app_commands.default_permissions(administrator=True)
        async def qwen_run(
            interaction: discord.Interaction,
            channel: Optional[discord.TextChannel] = None
        ):
            await interaction.response.defer(ephemeral=True)
    
            # Cek apakah Channel Paksa aktif
            forced_channel_id = qwen_batch.config.get("forced_delivery_channel_id")
            forced_channel_mention = None
            if forced_channel_id:
                # Coba dapatkan channel object untuk mention
                if interaction.guild:
                    forced_channel = interaction.guild.get_channel(forced_channel_id)
                    if forced_channel:
                        forced_channel_mention = forced_channel.mention
                    else:
                        forced_channel_mention = f"<#{forced_channel_id}> (Channel tidak ditemukan)"
                else:
                    forced_channel_mention = f"<#{forced_channel_id}>"

            # Tentukan channel tujuan yang akan digunakan (untuk info saja, tidak mempengaruhi logika pengiriman)
            target_channel = channel or interaction.channel
    
            # Validasi target_channel (hanya untuk validasi input, tidak dipakai untuk pengiriman jika ada forced channel)
            if target_channel is None:
                await interaction.followup.send(
                    "❌ Channel tujuan tidak ditemukan. Pastikan command dijalankan di channel yang valid.",
                    ephemeral=True
                )
                return
            if not hasattr(target_channel, "id"):
                await interaction.followup.send(
                    "❌ Channel tujuan tidak valid. Jalankan command ini dari channel target atau pilih parameter channel.",
                    ephemeral=True
                )
                return

            # Jalankan batch processing
            result = await qwen_batch.process_batch(self.bot)
            status = result.get("status")
    
            if status == "completed":
                message = (
                    "✅ Batch Qwen selesai dijalankan.\n"
                    f"👥 Total antrean: {result.get('total_users', 0)}\n"
                    f"✅ Berhasil diproses: {result.get('processed_users', 0)}\n"
                    f"♻️ Disimpan untuk retry: {result.get('retained_users', 0)}\n"
                    f"🧹 File kosong dibersihkan: {result.get('skipped_empty_users', 0)}"
                )
                if result.get("result_file"):
                    message += f"\n📁 Hasil tersimpan: `{result['result_file']}`"
        
                # Tambahkan info channel tujuan yang AKTUAL (bukan yang dipilih admin)
                if forced_channel_mention:
                    message += f"\n🚨 **Channel Paksa Aktif**: Hasil dikirim ke {forced_channel_mention} (Parameter channel diabaikan)."
                else:
                    target_label = getattr(target_channel, "mention", f"<#{target_channel.id}>")
                    message += f"\n📨 Hasil dikirim ke: {target_label}."
        
                await interaction.followup.send(message, ephemeral=True)
                return

            status_messages = {
                "busy": "ℹ️ Batch Qwen sedang berjalan. Tunggu sebentar lalu coba lagi.",
                "client_unavailable": f"❌ {result.get('message', 'Client Qwen belum siap.')}",
                "disabled": "⚠️ Modul Qwen sedang dinonaktifkan. Aktifkan dulu dengan `/qwen toggle`.",
                "empty": "ℹ️ Tidak ada data chat yang menunggu untuk diproses.",
            }
            await interaction.followup.send(
                status_messages.get(status, f"❌ Batch Qwen gagal dijalankan: {result.get('message', 'Unknown error')}"),
                ephemeral=True
            )

        @qwen_group.command(name="autorun", description="Atur auto-run batch Qwen (jam dan channel)")
        @app_commands.describe(
            hour="Jam (0-23) untuk menjalankan batch otomatis",
            minute="Menit (0-59) untuk menjalankan batch otomatis",
            channel="Channel tujuan hasil batch (opsional, default: channel pertama di enabled_channels)"
        )
        @app_commands.default_permissions(administrator=True)
        async def qwen_autorun_set(
            interaction: discord.Interaction,
            hour: int,
            minute: int,
            channel: Optional[discord.TextChannel] = None
        ):
            """Setel auto-run batch Qwen dengan jam dan channel tujuan."""
            await interaction.response.defer(ephemeral=True)

            # Validasi input
            if not (0 <= hour <= 23):
                await interaction.followup.send(
                    "❌ Jam tidak valid. Harap masukkan angka 0-23.",
                    ephemeral=True
                )
                return
            if not (0 <= minute <= 59):
                await interaction.followup.send(
                    "❌ Menit tidak valid. Harap masukkan angka 0-59.",
                    ephemeral=True
                )
                return

            # Dapatkan channel ID
            delivery_channel_id = channel.id if channel else None

            # Set auto-run dengan error handling
            try:
                success = qwen_batch.set_auto_run(hour, minute, delivery_channel_id)
            except KeyError as e:
                logger.error("KeyError saat set auto_run: %s. Kemungkinan config bolong.", e)
                await interaction.followup.send(
                    "❌ Error konfigurasi internal. Admin perlu cek file config.",
                    ephemeral=True
                )
                return
            except Exception as e:
                logger.exception("Error tak terduga saat set auto_run: %s", e)
                await interaction.followup.send(
                    f"❌ Error internal: {str(e)[:100]}",
                    ephemeral=True
                )
                return
            if success:
                # Restart scheduler jika belum berjalan
                if not qwen_batch._auto_run_task or qwen_batch._auto_run_task.done():
                    qwen_batch.start_auto_run(self.bot)
                channel_info = channel.mention if channel else "Channel pertama di enabled_channels"
                await interaction.followup.send(
                    f"✅ Auto-run batch Qwen berhasil disetel!\n"
                    f"🕐 Waktu: **{hour:02d}:{minute:02d}** setiap hari\n"
                    f"📨 Hasil dikirim ke: {channel_info}\n"
                    f"🔄 Scheduler telah dimulai.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Gagal mengatur auto-run. Periksa log untuk detail error.",
                    ephemeral=True
                )

        @qwen_group.command(name="autorun_status", description="Cek status auto-run batch Qwen")
        async def qwen_autorun_status(interaction: discord.Interaction):
            """Cek konfigurasi auto-run saat ini."""
            await interaction.response.defer(ephemeral=True)
            config = qwen_batch.get_auto_run_config()
            if config["enabled"]:
                hour = config["hour"]
                minute = config["minute"]
                channel_id = config.get("delivery_channel_id")
                channel_info = f"<#{channel_id}>" if channel_id else "Channel pertama di enabled_channels"
                embed = discord.Embed(
                    title="⏰ Status Auto-Run Qwen",
                    color=0x7f77dd
                )
                embed.add_field(name="Status", value="✅ Aktif", inline=True)
                embed.add_field(name="Waktu", value=f"**{hour:02d}:{minute:02d}** WIB", inline=True)
                embed.add_field(name="Channel Tujuan", value=channel_info, inline=False)
                embed.set_footer(text="Batch akan dijalankan otomatis setiap hari pada waktu ini.")
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="⏰ Status Auto-Run Qwen",
                    color=0xff6b6b
                )
                embed.add_field(name="Status", value="❌ Tidak aktif", inline=True)
                embed.add_field(
                    name="Cara Aktifkan",
                    value="Gunakan `/qwen autorun set hour:JJ minute:MM [channel]`",
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

        # forced_channel command removed, description="Set channel paksa untuk hasil analisis Qwen (Admin only)")
        @app_commands.describe(
            channel="Channel tujuan paksa untuk semua hasil analisis",
            action="Aksi yang ingin dilakukan: set atau remove"
        )
        @app_commands.default_permissions(administrator=True)
        async def qwen_forced_channel(
            interaction: discord.Interaction,
            action: str,
            channel: Optional[discord.TextChannel] = None
        ):
            """
            Slash command untuk mengatur atau menghapus channel paksa.
            Channel paksa akan mengabaikan channel user dan default, memaksa pengiriman ke channel ini.
    
            Usage:
            - /qwen forced_channel action:set channel:<channel>
            - /qwen forced_channel action:remove
            """
            await interaction.response.defer(ephemeral=True)
    
            if action.lower() == "set":
                if not channel:
                    await interaction.followup.send(
                        "❌ Parameter channel diperlukan untuk aksi 'set'.\n"
                        "Contoh: `/qwen forced_channel action:set channel:<#channel>`",
                        ephemeral=True
                    )
                    return
        
                try:
                    qwen_batch.set_forced_channel(channel.id)
                    await interaction.followup.send(
                        f"✅ **Channel Paksa Berhasil Diatur**\n"
                        f"📍 Semua hasil analisis Qwen akan dikirim ke: {channel.mention}",
                        ephemeral=True
                    )
                    logger.info("[Admin] %s mengatur channel paksa ke %s (%s)", 
                               interaction.user.name, channel.name, channel.id)
                except Exception as e:
                    logger.error("[Admin] Gagal mengatur channel paksa: %s", e)
                    await interaction.followup.send(f"❌ Gagal mengatur channel paksa: {str(e)}", ephemeral=True)
    
            elif action.lower() == "remove":
                try:
                    qwen_batch.remove_forced_channel()
                    await interaction.followup.send(
                        "🗑️ **Channel Paksa Dihapus**\n"
                        "Sistem kembali ke mode normal (channel user > channel default).",
                        ephemeral=True
                    )
                    logger.info("[Admin] %s menghapus channel paksa", interaction.user.name)
                except Exception as e:
                    logger.error("[Admin] Gagal menghapus channel paksa: %s", e)
                    await interaction.followup.send(f"❌ Gagal menghapus channel paksa: {str(e)}", ephemeral=True)
    
            else:
                await interaction.followup.send(
                    "❌ Aksi tidak valid. Gunakan 'set' atau 'remove'.\n"
                    "Contoh:\n"
                    "- `/qwen forced_channel action:set channel:<#channel>`\n"
                    "- `/qwen forced_channel action:remove`",
                    ephemeral=True
                )

        @qwen_group.command(name="forced_channel_status", description="Cek status channel paksa saat ini (Admin only)")
        @app_commands.default_permissions(administrator=True)
        async def qwen_forced_channel_status(interaction: discord.Interaction):
            """
            Slash command untuk mengecek apakah ada channel paksa yang aktif.
            """
            await interaction.response.defer(ephemeral=True)
    
            forced_channel_id = qwen_batch.config.get("forced_delivery_channel_id")
            if forced_channel_id:
                channel = interaction.guild.get_channel(forced_channel_id) if interaction.guild else None
                if channel:
                    await interaction.followup.send(
                        f"📍 **Channel Paksa Aktif**\n"
                        f"Channel: {channel.mention} (ID: {forced_channel_id})",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"📍 **Channel Paksa Aktif**\n"
                        f"Channel ID: {forced_channel_id} (Channel tidak ditemukan, mungkin sudah dihapus)",
                        ephemeral=True
                    )
            else:
                await interaction.followup.send(
                    "ℹ️ **Tidak Ada Channel Paksa**\n"
                    "Sistem menggunakan logika normal (channel user > channel default).",
                    ephemeral=True
                )

        @qwen_group.command(name="test", description="Tes prompt langsung ke model Qwen")
        @app_commands.describe(
            prompt="Prompt yang ingin dikirim ke Qwen",
            private="Hasil hanya kamu yang bisa lihat? (default: True)"
        )
        @app_commands.default_permissions(administrator=True)
        async def qwen_test(
            interaction: discord.Interaction, prompt: str, private: bool = True
        ):
            await interaction.response.defer(ephemeral=private)
            result = await qwen_batch.run_test_prompt(prompt)
            status = result.get("status")
            if status != "completed":
                error_messages = {
                    "invalid": f"⚠️ {result.get('message', 'Prompt tidak valid.')}",
                    "client_unavailable": f"❌ {result.get('message', 'Client Qwen belum siap.')}",
                    "empty": "⚠️ Qwen merespons tanpa teks yang bisa ditampilkan.",
                }
                await interaction.followup.send(
                    error_messages.get(status, f"❌ Gagal menjalankan test Qwen: {result.get('message', 'Unknown error')}"),
                    ephemeral=private
                )
                return
            await send_qwen_followup_chunks(
                interaction, result["response"], ephemeral=private, prefix="🧪 **Qwen Test Response**"
            )

        @qwen_group.command(name="result", description="Upload hasil analisis batch Qwen ke channel tertentu")
        @app_commands.describe(channel="Channel tujuan untuk upload hasil")
        @app_commands.default_permissions(administrator=True)
        async def qwen_result(interaction: discord.Interaction, channel: discord.TextChannel):
            await interaction.response.defer(ephemeral=True)
            try:
                # Import di dalam function untuk menghindari circular import
                from pathlib import Path
                import json
                results_dir = Path("data/qwen_results")
                if not results_dir.exists():
                    await interaction.followup.send("❌ Tidak ada hasil analisis yang tersimpan.", ephemeral=True)
                    return
                # Cari file hasil terbaru
                result_files = list(results_dir.glob("*.json"))
                if not result_files:
                    await interaction.followup.send("❌ Tidak ada file hasil analisis.", ephemeral=True)
                    return
                # Sort by modification time, get latest
                latest_file = max(result_files, key=lambda f: f.stat().st_mtime)
                # Baca hasil
                with open(latest_file, 'r', encoding='utf-8') as f:
                    results = json.load(f)
                # Format pesan untuk channel
                timestamp = results.get('timestamp', 'Unknown')
                total_users = results.get('total_users', 0)
                header = f"📊 **Hasil Analisis Batch Qwen**\n"
                header += f"🕒 Timestamp: {timestamp}\n"
                header += f"👥 Total User: {total_users}\n\n"
                # Kirim ke channel yang dipilih
                await channel.send(header)
                # Kirim detail untuk setiap user
                for user_result in results.get('results', []):
                    user_id = user_result.get('user_id', 'Unknown')
                    analysis = user_result.get('analysis', 'Tidak ada analisis')
                    message = f"**User ID:** <@{user_id}>\n{analysis}"
                    for chunk in qwen_batch.split_for_discord(message):
                        await channel.send(chunk)
                        await asyncio.sleep(0.5)  # Hindari rate limit
                await interaction.followup.send(f"✅ Hasil analisis berhasil diupload ke {channel.mention}", ephemeral=True)
            except Exception as e:
                logger.error(f"[Qwen] Error uploading results: {e}")
                await interaction.followup.send(f"❌ Gagal upload hasil: {str(e)[:100]}", ephemeral=True)

        self.tree.add_command(qwen_group)

        # ===== COMMAND GROUP: /greeting =====
        # ===== COMMAND GROUP: /bedtime =====
        bedtime_group = app_commands.Group(name="bedtime", description="Pengaturan pengingat waktu tidur")

        @bedtime_group.command(name="on", description="Aktifkan pengingat waktu tidur")
        @app_commands.describe(
            channel="Channel untuk mengirim pengingat waktu tidur"
        )
        @app_commands.default_permissions(administrator=True)
        async def bedtime_on(interaction: discord.Interaction, channel: discord.TextChannel):
            if not reminder_manager:
                await interaction.response.send_message("⚠️ Reminder manager belum diinisialisasi.", ephemeral=True)
                return
            await reminder_manager.start_reminder(interaction.guild_id, channel.id)
            await interaction.response.send_message(f"✅ Pengingat waktu tidur diaktifkan di {channel.mention} setiap jam 21:00.", ephemeral=True)

        @bedtime_group.command(name="off", description="Nonaktifkan pengingat waktu tidur")
        @app_commands.default_permissions(administrator=True)
        async def bedtime_off(interaction: discord.Interaction):
            if not reminder_manager:
                await interaction.response.send_message("⚠️ Reminder manager belum diinisialisasi.", ephemeral=True)
                return
            if await reminder_manager.stop_reminder(interaction.guild_id):
                await interaction.response.send_message("❌ Pengingat waktu tidur dinonaktifkan.", ephemeral=True)
            else:
                await interaction.response.send_message("ℹ️ Pengingat waktu tidur tidak aktif di server ini.", ephemeral=True)

        @bedtime_group.command(name="status", description="Cek status pengingat waktu tidur")
        async def bedtime_status(interaction: discord.Interaction):
            if not reminder_manager:
                await interaction.response.send_message("⚠️ Reminder manager belum diinisialisasi.", ephemeral=True)
                return
            status = await reminder_manager.get_reminder_status(interaction.guild_id)
            if status["active"]:
                channel_mention = f"<#{status['channel_id']}>" if status['channel_id'] else "Tidak diatur"
                await interaction.response.send_message(f"✅ Pengingat waktu tidur aktif di {channel_mention} setiap jam 21:00.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Pengingat waktu tidur tidak aktif.", ephemeral=True)

        self.tree.add_command(bedtime_group)

        # ===== COMMAND GROUP: /online_counter =====
        online_counter_group = app_commands.Group(name="online_counter", description="Pengaturan penghitung user online")

        @online_counter_group.command(name="on", description="Aktifkan penghitung user online di voice channel")
        @app_commands.describe(
            channel="Voice channel untuk menampilkan jumlah user online"
        )
        @app_commands.default_permissions(administrator=True)
        async def online_counter_on(interaction: discord.Interaction, channel: discord.VoiceChannel):
            if not online_counter_manager:
                await interaction.response.send_message("⚠️ Online counter manager belum diinisialisasi.", ephemeral=True)
                return
            await online_counter_manager.start_counter(interaction.guild_id, channel.id)
            await interaction.response.send_message(f"✅ Penghitung user online diaktifkan di {channel.mention}. Nama channel akan diupdate setiap 20 menit.", ephemeral=True)

        @online_counter_group.command(name="off", description="Nonaktifkan penghitung user online")
        @app_commands.default_permissions(administrator=True)
        async def online_counter_off(interaction: discord.Interaction):
            if not online_counter_manager:
                await interaction.response.send_message("⚠️ Online counter manager belum diinisialisasi.", ephemeral=True)
                return
            if await online_counter_manager.stop_counter(interaction.guild_id):
                await interaction.response.send_message("❌ Penghitung user online dinonaktifkan.", ephemeral=True)
            else:
                await interaction.response.send_message("ℹ️ Penghitung user online tidak aktif di server ini.", ephemeral=True)

        @online_counter_group.command(name="status", description="Cek status penghitung user online")
        async def online_counter_status(interaction: discord.Interaction):
            if not online_counter_manager:
                await interaction.response.send_message("⚠️ Online counter manager belum diinisialisasi.", ephemeral=True)
                return
            status = await online_counter_manager.get_counter_status(interaction.guild_id)
            if status["active"]:
                channel_mention = f"<#{status['channel_id']}>" if status['channel_id'] else "Tidak diatur"
                await interaction.response.send_message(f"✅ Penghitung user online aktif di {channel_mention}.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Penghitung user online tidak aktif.", ephemeral=True)

        self.tree.add_command(online_counter_group)

        # ===== COMMAND GROUP: /greeting =====
        greeting_group = app_commands.Group(name="greeting", description="Pengaturan fitur Welcome & Goodbye")

        @greeting_group.command(name="status", description="Cek status fitur greeting di server ini")
        async def greeting_status(interaction: discord.Interaction):
            from main import auto_greeting
            enabled = auto_greeting.is_enabled(interaction.guild_id)
            config = auto_greeting._load_config()
            guild_config = config.get("guilds", {}).get(str(interaction.guild_id), {})
            channel_id = guild_config.get("channel_id")
            channel_mention = f"<#{channel_id}>" if channel_id else "Otomatis (System/Default)"
            embed = discord.Embed(
                title="✨ Pengaturan Greeting",
                color=discord.Color.blue()
            )
            embed.add_field(name="Status", value="✅ Aktif" if enabled else "❌ Nonaktif", inline=True)
            embed.add_field(name="Channel", value=channel_mention, inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @greeting_group.command(name="toggle", description="Aktifkan atau nonaktifkan fitur greeting")
        @app_commands.describe(status="Pilih status fitur")
        @app_commands.choices(status=[
            app_commands.Choice(name="Aktifkan", value="enable"),
            app_commands.Choice(name="Nonaktifkan", value="disable")
        ])
        @app_commands.default_permissions(administrator=True)
        async def greeting_toggle(interaction: discord.Interaction, status: app_commands.Choice[str]):
            from main import auto_greeting
            is_enabled = status.value == "enable"
            auto_greeting.set_enabled(interaction.guild_id, is_enabled)
            msg = "✅ Fitur greeting telah **diaktifkan**." if is_enabled else "❌ Fitur greeting telah **dinonaktifkan**."
            await interaction.response.send_message(msg, ephemeral=True)

        @greeting_group.command(name="setchannel", description="Atur channel khusus untuk pesan greeting")
        @app_commands.describe(channel="Pilih channel untuk pesan greeting")
        @app_commands.default_permissions(administrator=True)
        async def greeting_setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
            from main import auto_greeting
            auto_greeting.set_channel(interaction.guild_id, channel.id)
            await interaction.response.send_message(f"✅ Channel greeting telah diatur ke {channel.mention}.", ephemeral=True)

        # ===== COMMAND GROUP: /module (Admin Only) =====
        module_group = app_commands.Group(name="module", description="Pengaturan aktif/nonaktif modul bot")

        @module_group.command(name="status", description="Cek status semua modul")
        @app_commands.default_permissions(administrator=True)
        async def module_status(interaction: discord.Interaction):
            status = module_manager.get_all_status()
            embed = discord.Embed(title="🛠️ Status Modul Mirai", color=0x3498db)
            for mod, enabled in status.items():
                embed.add_field(name=mod.capitalize(), value="✅ Aktif" if enabled else "❌ Nonaktif", inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @module_group.command(name="toggle", description="Aktifkan atau nonaktifkan modul")
        @app_commands.describe(
            modul="Pilih modul yang ingin diatur",
            status="Pilih status modul"
        )
        @app_commands.choices(
            modul=[
                app_commands.Choice(name="Calculator", value="calculator"),
                app_commands.Choice(name="Weather", value="weather"),
                app_commands.Choice(name="News", value="news"),
                app_commands.Choice(name="Greeting", value="greeting")
            ],
            status=[
                app_commands.Choice(name="Aktifkan", value="enable"),
                app_commands.Choice(name="Nonaktifkan", value="disable")
            ]
        )
        @app_commands.default_permissions(administrator=True)
        async def module_toggle(interaction: discord.Interaction, modul: app_commands.Choice[str], status: app_commands.Choice[str]):
            is_enabled = status.value == "enable"
            module_manager.set_status(modul.value, is_enabled)
            msg = f"✅ Modul **{modul.name}** telah **diaktifkan**." if is_enabled else f"❌ Modul **{modul.name}** telah **dinonaktifkan**."
            await interaction.response.send_message(msg, ephemeral=True)

        self.tree.add_command(module_group)
        self.tree.add_command(greeting_group)
        
        # ===== COMMAND: /cuaca =====
        @self.tree.command(name="cuaca", description="Cek prakiraan cuaca dari BMKG")
        @app_commands.describe(
            kode_wilayah="Kode wilayah adm4 (Kelurahan/Desa). Default: Kemayoran (31.71.03.1001)"
        )
        async def cuaca_command(
            interaction: discord.Interaction,
            kode_wilayah: Optional[str] = "31.71.03.1001"
        ):
            """Slash command untuk cek cuaca."""
            if not module_manager.is_enabled("weather"):
                await interaction.response.send_message("⚠️ Modul Cuaca sedang dinonaktifkan oleh admin.", ephemeral=True)
                return
            await interaction.response.defer()
            try:
                from ai.cuaca import DEFAULT_ADM4
                adm4 = kode_wilayah if kode_wilayah else DEFAULT_ADM4
                weather_data = gemini.bmkg.get_weather_raw(adm4)
                if not weather_data:
                    await interaction.followup.send("⚠️ Maaf, aku gagal mengambil data cuaca dari BMKG. Coba lagi nanti ya! 🙏")
                    return
                lokasi = weather_data["lokasi"]
                prakiraan = weather_data["prakiraan"]  # list of up to 3 forecasts
                # Ambil prakiraan pertama (terdekat) untuk header embed
                first = prakiraan[0] if prakiraan else {}
                embed = discord.Embed(
                    title=f"🌤️ Prakiraan Cuaca: {lokasi.get('desa', '-')}",
                    description=f"Wilayah: {lokasi.get('kecamatan', '-')}, {lokasi.get('kotkab', '-')}, {lokasi.get('provinsi', '-')}",
                    color=0x3498db,
                    timestamp=datetime.now().astimezone()
                )
                # Field dari prakiraan terdekat
                embed.add_field(name="☁️ Kondisi", value=first.get("weather_desc", "-"), inline=True)
                embed.add_field(name="🌡️ Suhu", value=f"{first.get('t', '-')}°C", inline=True)
                embed.add_field(name="💧 Kelembapan", value=f"{first.get('hu', '-')}%", inline=True)
                embed.add_field(name="💨 Kec. Angin", value=f"{first.get('ws', '-')} km/jam", inline=True)
                embed.add_field(name="🧭 Arah Angin", value=first.get("wd", "-"), inline=True)
                embed.add_field(name="☁️ Tutupan Awan", value=f"{first.get('tcc', '-')}%", inline=True)
                # Jadwal prakiraan berikutnya (jika ada)
                if len(prakiraan) > 1:
                    jadwal_lines = []
                    for f in prakiraan[1:]:
                        dt = f.get("local_datetime", "-")
                        desc = f.get("weather_desc", "-")
                        suhu = f.get("t", "-")
                        jadwal_lines.append(f"`{dt}` — {desc}, {suhu}°C")
                    embed.add_field(
                        name="📅 Prakiraan Berikutnya",
                        value="\n".join(jadwal_lines),
                        inline=False
                    )
                embed.set_footer(text=f"Sumber: {weather_data.get('sumber', 'BMKG')} | Kode wilayah: {adm4}")
                await interaction.followup.send(embed=embed)
            except Exception as e:
                await interaction.followup.send(f"⚠️ Terjadi kesalahan: {str(e)[:100]}")

    async def sync_commands(self, guild_id: Optional[int] = None):
        """
        Sinkronisasi commands ke Discord.
        Args:
            guild_id: Guild ID untuk sinkronisasi (None untuk global)
        """
        if guild_id:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("✅ Commands synced to guild %s", guild_id)
        else:
            await self.tree.sync()
            logger.info("✅ Global commands synced")
