import asyncio
import math
import json
import discord
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from utils.logger import setup_logging
from utils.sentiment import analyze_sentiment, get_mood_emoji
from utils.wellness import get_wellness_reminder, should_give_reminder
from core.file_reading import build_attachment_context
import core.qwen_batch as qwen_batch
from config import COOLDOWN_REPLY_DELAY
from core.module_manager import module_manager

logger = setup_logging()
WIB = ZoneInfo("Asia/Jakarta")

class MessageHandler:
    def __init__(self, bot, ai_service, cooldown_manager, micro_rag):
        self.bot = bot
        self.ai = ai_service
        self.cooldown = cooldown_manager
        self.micro_rag = micro_rag

    def clean_message(self, content):
        """Bersihkan pesan dari mention bot."""
        return content.replace(f"<@{self.bot.user.id}>", "")\
                      .replace(f"<@!{self.bot.user.id}>", "")\
                      .strip()

    def format_user_identity(self, message: discord.Message) -> tuple[str, str]:
        """Format identitas user dengan nama dan role."""
        author = message.author
        role_name = "DM"
        if isinstance(author, discord.Member):
            if author.global_name and author.global_name != author.display_name:
                name = f"{author.global_name} / {author.display_name}"
            else:
                name = author.display_name
            guild_roles = [role for role in author.roles if role.name != "@everyone"]
            if guild_roles:
                role_name = guild_roles[-1].name
            else:
                role_name = "Member"
        else:
            name = author.display_name
        return name, role_name

    # ========== HELPER FUNCTIONS (Pisah dari main logic) ==========
    
    async def _get_attachment_context(self, attachments: list) -> str:
        """
        Ambil context dari attachment jika ada.
        PERBAIKAN: SELALU cek attachment, bukan conditional qwen_batch.
        """
        if not attachments:
            return ""
        
        # Cek jika channel memiliki fitur attachment processing
        if hasattr(qwen_batch, 'is_channel_enabled'):
            return await build_attachment_context(attachments)
        
        return ""

    def _build_gemini_context(
        self,
        user_name: str,
        user_id: int,
        channel_name: str,
        channel_id: int,
        cleaned_message: str,
        timestamp: str,
        server_name: str | None = None,
        server_id: int | None = None,
        attachment_context: str = ""
    ) -> str:
        """
        Build structured context untuk Gemini.
        PERBAIKAN: Format yang jelas dan konsisten sesuai requirements.
        """
        context = (
            f"Display Name: {user_name}\n"
            f"User ID: {user_id}\n"
            f"Channel: {channel_name}\n"
            f"Channel ID: {channel_id}\n"
            f"Timestamp: {timestamp}\n"
            f"Message: {cleaned_message}"
        )
        if server_name:
            context += f"\nServer: {server_name}"
        if server_id:
            context += f"\nServer ID: {server_id}"
        
        if attachment_context:
            context += f"\n\n[Attachment Context]\n{attachment_context}"
        # Instruksi eksplisit agar Gemini menyebutkan nama pengguna dan tidak menyebutkan ID
        context += "\n\nInstruksi: Selalu gunakan nama Display Name di atas saat menyapa pengguna. Jangan menyebutkan atau menanyakan ID pengguna dalam balasan."
        return context

    async def _save_to_history(
        self,
        user_name: str,
        user_id: int,
        channel_name: str,
        channel_id: int,
        message: str,
        response: str,
        timestamp: str
    ) -> None:
        """
        Simpan ke history.json dengan format yang benar.
        PERBAIKAN: Sesuai dengan requirements format.
        
        Format:
        {
            "timestamp": "ISO format",
            "user": "name | id",
            "channel": "name | id",
            "message": "pesan user",
            "response": "respon bot",
            "response_timestamp": "ISO format"
        }
        """
        try:
            history_path = Path(__file__).parent.parent / "history.json"
            
            # Load existing data
            if history_path.exists():
                with open(history_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = []
            
            # Create entry dengan format yang benar
            entry = {
                "timestamp": timestamp,
                "user": f"{user_name} | {user_id}",
                "channel": f"{channel_name} | {channel_id}",
                "message": message,
                "response": response,
                "response_timestamp": datetime.utcnow().isoformat()
            }
            
            # Append entry
            data.append(entry)
            
            # Save dengan format yang rapi
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"[History] Saved: {user_name} in {channel_name}")
            
        except Exception as e:
            logger.exception("Gagal save history: %s", e)

    # ========== MAIN HANDLER ==========

    async def handle(self, message: discord.Message):
        if message.author.bot:
            return

        try:
            # STEP 1: Extract basic info
            cleaned = self.clean_message(message.content)
            user_name, role_name = self.format_user_identity(message)
            user_id = message.author.id
            channel_id = message.channel.id
            channel_name = getattr(message.channel, "name", "DM")
            server_name = message.guild.name if message.guild else None
            server_id = message.guild.id if message.guild else None

            # STEP 2: Get attachment context (PERBAIKAN: Always check if exists)
            attachment_context = await self._get_attachment_context(message.attachments)
            
            # STEP 3: Collect message untuk qwen jika diperlukan
            if hasattr(qwen_batch, 'collect_message'):
                await qwen_batch.collect_message(
                    user_id, user_name, cleaned, channel_id,
                    channel_name=channel_name,
                    server_name=server_name,
                    server_id=server_id,
                    attachment_context=attachment_context,
                    timestamp=message.created_at,
                )

            # STEP 4: Check if bot should reply (mention atau reply)
            should_reply = False
            if self.bot.user.mentioned_in(message):
                should_reply = True
            if message.reference:
                try:
                    ref = await message.channel.fetch_message(message.reference.message_id)
                    if ref.author == self.bot.user:
                        should_reply = True
                except:
                    pass

            if not should_reply:
                return

            # STEP 5: Check cooldown
            can_proceed, wait_time = await self.cooldown.check_and_update(channel_id)
            if not can_proceed:
                msg = await message.reply(
                    f"⚠️ Tenang dulu ya... Aku lagi istirahat sebentar. "
                    f"Coba lagi dalam {math.ceil(wait_time)} detik."
                )
                asyncio.create_task(self._delete_after_delay(msg))
                return

            # STEP 6: Generate reply dengan context yang benar
            async with message.channel.typing():
                # Build user message untuk history
                # Buat pesan user yang lengkap dengan semua info yang dibutuhkan
                user_msg = (
                    f"{user_name} ({role_name}) | ID: {user_id}\n"
                    f"Channel: {channel_name} (ID: {channel_id})\n"
                    f"Server: {server_name or 'DM'} (ID: {server_id or 'N/A'})\n"
                    f"Timestamp: {message.created_at.isoformat()}\n"
                    f"Message: {cleaned}"
                )
                if attachment_context:
                    user_msg += f"\n\n[Attachments Context]\n{attachment_context}"
                
                await self.ai.add_to_history("user", user_msg)
                history = self.ai.get_history()
                
                # Build context untuk Gemini (PERBAIKAN: structured format)
                user_context = self._build_gemini_context(
                    user_name=user_name,
                    user_id=user_id,
                    channel_name=channel_name,
                    channel_id=channel_id,
                    cleaned_message=cleaned,
                    timestamp=message.created_at.isoformat(),
                    server_name=server_name,
                    server_id=server_id,
                    attachment_context=attachment_context
                )
                # Tambahkan konteks profil user dari Micro‑RAG (personality, interests, mood, dll.)
                rag_context = self.micro_rag.get_user_context(str(user_id))
                if rag_context:
                    user_context += rag_context
                
                # Generate reply dari Gemini
                reply = await self.ai.generate_reply(history, user_context=user_context)

                # Add sentiment & wellness
                # sentiment = analyze_sentiment(cleaned)
                # mood_emoji = get_mood_emoji(sentiment)
                # if mood_emoji:
                #    reply = f"{mood_emoji} {reply}"

                # Tambahkan wellness hanya bila belum ada dalam balasan
                # Cek apakah wellness diaktifkan di module manager
                if should_give_reminder() and module_manager.is_enabled("wellness"):
                    wellness = get_wellness_reminder()
                    # Cek apakah wellness sudah ada (case‑insensitive) untuk menghindari duplikasi
                    if wellness and wellness.lower() not in reply.lower():
                        reply = f"{reply}\n\n---\n💡 *Mirai Wellness:* {wellness}"

                await self.ai.add_to_history("assistant", reply)
                
                # Send response ke user (no mention)
                await self._send_long_message(message.channel, reply, reply_to=message)
            
            # STEP 7: Save to history.json (PERBAIKAN: format yang benar)
            await self._save_to_history(
                user_name=user_name,
                user_id=user_id,
                channel_name=channel_name,
                channel_id=channel_id,
                message=cleaned,
                response=reply,
                timestamp=message.created_at.isoformat()
            )

        except Exception as e:
            logger.exception("Error in on_message: %s", e)

    async def _delete_after_delay(self, msg: discord.Message, delay_seconds: int = COOLDOWN_REPLY_DELAY):
        await asyncio.sleep(delay_seconds)
        try:
            await msg.delete()
        except:
            pass

    async def _send_long_message(self, destination, content, reply_to=None, limit=2000):
        """Send long message with splitting if needed."""
        if len(content) <= limit:
            if reply_to:
                await reply_to.reply(content)
            else:
                await destination.send(content)
            return
        
        parts = [content[i:i+limit] for i in range(0, len(content), limit)]
        if reply_to:
            await reply_to.reply(parts[0])
            for part in parts[1:]:
                await destination.send(part)
                await asyncio.sleep(0.5)
        else:
            for part in parts:
                await destination.send(part)
                await asyncio.sleep(0.5)
