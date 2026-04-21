import asyncio
import json
import os
import discord

class OnlineCounterManager:
    def __init__(self, bot):
        self.bot = bot
        self.counters = {}
        self.counter_file = 'data/online_counters.json'
        self._load_counters()

    def _load_counters(self):
        if os.path.exists(self.counter_file):
            with open(self.counter_file, 'r') as f:
                self.counters = json.load(f)
        else:
            self.counters = {}

    def _save_counters(self):
        with open(self.counter_file, 'w') as f:
            json.dump(self.counters, f, indent=4)

    async def start_counter(self, guild_id, channel_id):
        guild_id_str = str(guild_id)
        self.counters[guild_id_str] = {'channel_id': channel_id, 'active': True}
        self._save_counters()
        await self._schedule_next_update(guild_id)

    async def stop_counter(self, guild_id):
        guild_id_str = str(guild_id)
        if guild_id_str in self.counters:
            self.counters[guild_id_str]['active'] = False
            self._save_counters()
            # Cancel any pending tasks for this guild
            for task in asyncio.all_tasks():
                if task.get_name() == f'online_counter_{guild_id}':
                    task.cancel()
            return True
        return False

    async def get_counter_status(self, guild_id):
        guild_id_str = str(guild_id)
        if guild_id_str in self.counters:
            return self.counters[guild_id_str]
        return {'active': False, 'channel_id': None}

    async def _schedule_next_update(self, guild_id):
        guild_id_str = str(guild_id)
        if not self.counters.get(guild_id_str, {}).get('active'):
            return

        # Schedule for 20 minutes (1200 seconds)
        delay = 1200 

        asyncio.create_task(self._update_channel_after_delay(guild_id, delay), name=f'online_counter_{guild_id}')

    async def _update_channel_after_delay(self, guild_id, delay):
        guild_id_str = str(guild_id)
        try:
            await asyncio.sleep(delay)
            if not self.counters.get(guild_id_str, {}).get('active'):
                return

            channel_id = self.counters[guild_id_str]['channel_id']
            channel = self.bot.get_channel(channel_id)
            if channel and isinstance(channel, discord.VoiceChannel):
                online_members = [member for member in channel.guild.members if member.status != discord.Status.offline and not member.bot]
                online_count = len(online_members)
                new_name = f"Online: {online_count}"
                try:
                    await channel.edit(name=new_name)
                    print(f"[OnlineCounter] Updated voice channel {channel.name} to {new_name} in guild {guild_id}")
                except discord.Forbidden:
                    print(f"[OnlineCounter] Bot does not have permissions to edit channel name in guild {guild_id}")
                except Exception as e:
                    print(f"[OnlineCounter] Error updating channel name: {e}")
            else:
                print(f"[OnlineCounter] Channel {channel_id} not found or not a voice channel for guild {guild_id}")

        except asyncio.CancelledError:
            print(f"[OnlineCounter] Online counter for guild {guild_id} was cancelled.")
        finally:
            # Schedule the next update immediately after the current one finishes
            if self.counters.get(guild_id_str, {}).get('active'):
                await self._schedule_next_update(guild_id)

    async def initialize_all_counters(self):
        for guild_id_str, counter_data in self.counters.items():
            if counter_data.get('active'):
                await self._schedule_next_update(int(guild_id_str))
