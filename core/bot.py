import discord
from utils.logger import setup_logging

def create_bot():
    """Initialize and return the Discord bot client."""
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    bot = discord.Client(intents=intents)
    return bot
