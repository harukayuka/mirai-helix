import asyncio
import discord
from zoneinfo import ZoneInfo
from utils.logger import setup_logging
from utils.sentiment import analyze_sentiment, get_mood_emoji
from utils.wellness import get_wellness_reminder, should_give_reminder
from core.file_reading import build_attachment_context
import core.qwen_batch as qwen_batch
from config import COOLDOWN_REPLY_DELAY

logger = setup_logging()
WIB = ZoneInfo("Asia/Jakarta")

class MessageHandler:
    def __init__(self, bot, ai_service, cooldown_manager):
        self.bot = bot
        self.ai = ai_service
        self.cooldown = cooldown_manager

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

    async def handle(self, message: discord.Message):
        if message.author.bot:
            return

        try:
            cleaned = self.clean_message(message.content)
            user_name, role_name = self.format_user_identity(message)
            user_id = message.author.id
            channel_id = message.channel.id
            channel_name = getattr(message.channel, "name", "DM")
            server_name = message.guild.name if message.guild else None
            server_id = message.guild.id if message.guild else None

            attachment_context = ""
            if hasattr(qwen_batch, 'is_channel_enabled') and qwen_batch.is_channel_enabled(channel_id) and message.attachments:
                attachment_context = await build_attachment_context(message.attachments)
            
            if hasattr(qwen_batch, 'collect_message'):
                qwen_batch.collect_message(
                    user_id, user_name, cleaned, channel_id,
                    channel_name=channel_name,
                    server_name=server_name,
                    server_id=server_id,
                    attachment_context=attachment_context,
                    timestamp=message.created_at,
                )

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

            can_proceed, wait_time = await self.cooldown.check_and_update(channel_id)
            if not can_proceed:
                msg = await message.reply(f"⚠️ Tenang dulu ya... Aku lagi istirahat sebentar. Coba lagi dalam {math.ceil(wait_time)} detik.")
                asyncio.create_task(self._delete_after_delay(msg))
                return

            async with message.channel.typing():
                user_msg = f"{user_name} ({role_name}): {cleaned}"
                if attachment_context:
                    user_msg += f"\n\n[Attachments Context]\n{attachment_context}"
                
                self.ai.add_to_history("user", user_msg)
                history = self.ai.get_history()
                
                reply = await self.ai.generate_reply(history)
                
                # Sentiment & Wellness
                sentiment = analyze_sentiment(cleaned)
                mood_emoji = get_mood_emoji(sentiment)
                if mood_emoji:
                    reply = f"{mood_emoji} {reply}"
                
                if should_give_reminder():
                    wellness = get_wellness_reminder()
                    reply = f"{reply}\n\n---\n💡 *Mirai Wellness:* {wellness}"
                
                self.ai.add_to_history("assistant", reply)
                await self._send_long_message(message.channel, reply, reply_to=message)

        except Exception as e:
            logger.exception("Error in on_message: %s", e)

    async def _delete_after_delay(self, msg: discord.Message, delay_seconds: int = COOLDOWN_REPLY_DELAY):
        await asyncio.sleep(delay_seconds)
        try:
            await msg.delete()
        except:
            pass

    async def _send_long_message(self, destination, content, reply_to=None, limit=2000):
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
