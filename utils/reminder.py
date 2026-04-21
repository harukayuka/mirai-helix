import asyncio
import datetime
import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai.bedtime_prompt import generate_bedtime_message

class ReminderManager:
    def __init__(self, bot):
        self.bot = bot
        self.reminders = {}
        self.reminder_file = 'data/reminders.json'
        self._load_reminders()

    def _load_reminders(self):
        if os.path.exists(self.reminder_file):
            with open(self.reminder_file, 'r') as f:
                self.reminders = json.load(f)
        else:
            self.reminders = {}

    def _save_reminders(self):
        with open(self.reminder_file, 'w') as f:
                json.dump(self.reminders, f, indent=4)

    async def start_reminder(self, guild_id, channel_id):
        guild_id_str = str(guild_id)
        self.reminders[guild_id_str] = {'channel_id': channel_id, 'active': True}
        self._save_reminders()
        await self._schedule_next_reminder(guild_id)

    async def stop_reminder(self, guild_id):
        guild_id_str = str(guild_id)
        if guild_id_str in self.reminders:
            self.reminders[guild_id_str]['active'] = False
            self._save_reminders()
            # Cancel any pending tasks for this guild
            for task in asyncio.all_tasks():
                if task.get_name() == f'bedtime_reminder_{guild_id}':
                    task.cancel()
            return True
        return False

    async def get_reminder_status(self, guild_id):
        guild_id_str = str(guild_id)
        if guild_id_str in self.reminders:
            return self.reminders[guild_id_str]
        return {'active': False, 'channel_id': None}

    async def _schedule_next_reminder(self, guild_id):
        guild_id_str = str(guild_id)
        if not self.reminders.get(guild_id_str, {}).get('active'):
            return

        now = datetime.datetime.now()
        target_time = now.replace(hour=21, minute=0, second=0, microsecond=0)

        if now >= target_time:
            # If it's already past 9 PM, schedule for tomorrow
            target_time += datetime.timedelta(days=1)

        delay = (target_time - now).total_seconds()

        asyncio.create_task(self._send_reminder_after_delay(guild_id, delay), name=f'bedtime_reminder_{guild_id}')

    async def _send_reminder_after_delay(self, guild_id, delay):
        guild_id_str = str(guild_id)
        try:
            await asyncio.sleep(delay)
            if not self.reminders.get(guild_id_str, {}).get('active'):
                return

            channel_id = self.reminders[guild_id_str]['channel_id']
            channel = self.bot.get_channel(channel_id)
            if channel:
                bedtime_message = await generate_bedtime_message()
                await channel.send(bedtime_message)
            else:
                print(f"[Reminder] Channel {channel_id} not found for guild {guild_id}")

        except asyncio.CancelledError:
            print(f"[Reminder] Bedtime reminder for guild {guild_id} was cancelled.")
        finally:
            # Schedule the next reminder immediately after the current one finishes
            if self.reminders.get(guild_id_str, {}).get('active'):
                await self._schedule_next_reminder(guild_id)

    async def initialize_all_reminders(self):
        for guild_id_str, reminder_data in self.reminders.items():
            if reminder_data.get('active'):
                await self._schedule_next_reminder(int(guild_id_str))
