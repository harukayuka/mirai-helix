# main.py - Mirai Discord Bot Main Entry Point
import asyncio
import os
import discord
import random
import time
import math
from dotenv import load_dotenv
from memory import add_message, get_history
from ai.gemini import GeminiClient
from ai.news_summary import run_summary
from core import CommandGroup
from core.file_reading import build_attachment_context
from utils.logger import setup_logging
from config import (
    COOLDOWN_SECONDS, COOLDOWN_REPLY_DELAY, RPC_UPDATE_INTERVAL,
    TEMPERATURE, MAX_OUTPUT_TOKENS, MAX_HISTORY, NEWS_REFRESH_SECONDS
)

load_dotenv()
logger = setup_logging()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

if not DISCORD_TOKEN:
    raise ValueError("❌ DISCORD_TOKEN tidak ditemukan di .env!")

gemini = GeminiClient()
BYPASS_CHANNEL_IDS = {
    int(channel_id.strip())
    for channel_id in os.getenv("BYPASS_CHANNEL_IDS", "").split(",")
    if channel_id.strip().isdigit()
}
last_reply_timestamp_by_channel = {}
background_tasks_started = False

async def delete_after_delay(msg: discord.Message, delay_seconds: int = COOLDOWN_REPLY_DELAY):
    """Hapus pesan setelah delay tertentu."""
    await asyncio.sleep(delay_seconds)
    try:
        await msg.delete()
    except discord.Forbidden:
        logger.warning("[Cooldown] Gagal hapus pesan: izin tidak cukup (Forbidden).")
    except discord.NotFound:
        pass
    except discord.HTTPException as err:
        logger.exception("[Cooldown] Gagal hapus pesan: %s", err)

async def send_long_message(destination, content, reply_to=None, mention_author=False, limit=2000):
    """Kirim pesan panjang dengan split otomatis."""
    if len(content) <= limit:
        if reply_to:
            await reply_to.reply(content, mention_author=mention_author)
        else:
            await destination.send(content)
        return

    parts = [content[i:i+limit] for i in range(0, len(content), limit)]

    if reply_to:
        await reply_to.reply(parts[0], mention_author=mention_author)
        channel = reply_to.channel
        for part in parts[1:]:
            await channel.send(part)
            await asyncio.sleep(0.5)
    else:
        for part in parts:
            await destination.send(part)
            await asyncio.sleep(0.5)

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

command_group = CommandGroup(bot)

RPC_STATUSES = [
    {"type": "playing", "text": "Mirai Health Assistant"},
    {"type": "watching", "text": "over Helix members"},
    {"type": "listening", "text": "cerita kesehatanmu"},
    {"type": "playing", "text": "dengan algoritma empati"},
    {"type": "watching", "text": "tumbuh kembang server"},
]

async def schedule_news_summary():
    """Jalankan ringkasan berita secara berkala sesuai interval config."""
    await bot.wait_until_ready()
    try:
        await asyncio.to_thread(run_summary)
    except Exception as err:
        logger.exception("[NEWS] Gagal menjalankan ringkasan awal: %s", err)
    while not bot.is_closed():
        delay = NEWS_REFRESH_SECONDS
        logger.info("[NEWS] Next summary run in %.0f seconds", delay)
        await asyncio.sleep(delay)
        try:
            await asyncio.to_thread(run_summary)
        except Exception as err:
            logger.exception("[NEWS] Gagal menjalankan ringkasan: %s", err)

async def update_presence():
    """Update status Rich Presence secara berkala."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        status = random.choice(RPC_STATUSES)
        rpc_type = status["type"]
        rpc_text = status["text"]
        
        if rpc_type == "playing":
            activity = discord.Game(name=rpc_text)
        elif rpc_type == "watching":
            activity = discord.Activity(type=discord.ActivityType.watching, name=rpc_text)
        elif rpc_type == "listening":
            activity = discord.Activity(type=discord.ActivityType.listening, name=rpc_text)
        else:
            activity = discord.Game(name=rpc_text)
        
        await bot.change_presence(activity=activity)
        logger.info("[RPC] Status: %s %s", rpc_type, rpc_text)
        await asyncio.sleep(RPC_UPDATE_INTERVAL)

def clean_message(content, bot_user):
    """Bersihkan pesan dari mention bot."""
    return content.replace(f"<@{bot_user.id}>", "")\
                  .replace(f"<@!{bot_user.id}>", "")\
                  .strip()

def format_user_identity(message: discord.Message) -> tuple[str, str]:
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

def format_channel_context(message: discord.Message) -> str:
    """Format konteks channel."""
    channel_name = getattr(message.channel, "name", None)
    if not channel_name:
        channel_name = type(message.channel).__name__
    return f"{channel_name}/{message.channel.id}"

@bot.event
async def on_ready():
    """Event saat bot siap."""
    logger.info("✅ Bot connected as %s", bot.user)
    
    if GUILD_ID:
        await command_group.sync_commands(guild_id=int(GUILD_ID))
    else:
        await command_group.sync_commands()
    
    if not getattr(bot, "_mirai_background_started", False):
        bot._mirai_background_started = True
        bot.loop.create_task(update_presence())
        bot.loop.create_task(schedule_news_summary())

@bot.event
async def on_message(message):
    """Event saat menerima pesan."""
    if message.author.bot:
        return

    should_reply = False
    if bot.user.mentioned_in(message):
        should_reply = True
    if message.reference:
        try:
            ref = await message.channel.fetch_message(message.reference.message_id)
            if ref.author == bot.user:
                should_reply = True
        except:
            pass

    if not should_reply:
        return

    # Cooldown check
    if message.channel.id not in BYPASS_CHANNEL_IDS:
        now = time.monotonic()
        last_reply_at = last_reply_timestamp_by_channel.get(message.channel.id)
        if last_reply_at and now - last_reply_at < COOLDOWN_SECONDS:
            remaining = math.ceil(COOLDOWN_SECONDS - (now - last_reply_at))
            cooldown_notice = await message.reply(
                f"Silakan tunggu ya, cooldown masih {remaining} detik.",
                mention_author=False
            )
            asyncio.create_task(delete_after_delay(cooldown_notice, COOLDOWN_REPLY_DELAY))
            return
        last_reply_timestamp_by_channel[message.channel.id] = now

    async with message.channel.typing():
        try:
            cleaned = clean_message(message.content, bot.user)
            user_name, role_name = format_user_identity(message)
            user_id = message.author.id
            channel_name = getattr(message.channel, "name", "DM")
            channel_id = message.channel.id
            timestamp = message.created_at.isoformat()

            # Format server info
            if message.guild:
                server_name = message.guild.name
                server_id = message.guild.id
                server_part = f"[server: {server_name} | {server_id}]"
            else:
                server_part = "[server: DM]"

            user_message_with_name = (
                f"{user_name} ({user_id}): {cleaned} [channel: {channel_name} | {channel_id}] {server_part} {timestamp}"
            )
            
            # Process attachments if present
            attachment_context = ""
            if message.attachments:
                attachment_context = await build_attachment_context(message.attachments)
            
            # Combine message content and attachment context
            full_user_content = user_message_with_name
            if attachment_context:
                full_user_content += f"\n\n{attachment_context}"
            
            # Save to memory
            add_message("user", full_user_content)
            
            # Get history
            history = get_history()
            
            # Generate response
            reply = await asyncio.to_thread(
                gemini.generate,
                history,
                temperature=TEMPERATURE,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            )
            
            # Save response to memory
            add_message("assistant", reply)

        except Exception as e:
            logger.exception("[ERROR] on_message: %s", e)
            reply = "⚠️ Maaf, ada error saat memproses pesanmu. Coba lagi ya! 🙏"

    await send_long_message(message, reply, reply_to=message, mention_author=False)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    """Event untuk slash commands."""
    pass

if __name__ == "__main__":
    logger.info("[INFO] Starting Mirai Discord Bot...")
    logger.info("[INFO] Using model: Gemini 2.5 Flash")
    logger.info("[INFO] Cooldown: %ss", COOLDOWN_SECONDS)
    logger.info("[INFO] Max history: %s messages", MAX_HISTORY)
    bot.run(DISCORD_TOKEN)
