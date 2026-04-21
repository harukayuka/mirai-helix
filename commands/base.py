import discord
from discord import app_commands

class BaseCommand:
    def __init__(self, bot):
        self.bot = bot

    def register(self, tree: app_commands.CommandTree):
        raise NotImplementedError("Subclasses must implement register()")
