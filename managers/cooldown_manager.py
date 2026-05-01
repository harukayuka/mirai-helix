import time
import os
from config import COOLDOWN_SECONDS

class CooldownManager:
    def __init__(self):
        self.last_reply_timestamp_by_channel = {}
        self.bypass_channel_ids = {
            int(channel_id.strip())
            for channel_id in os.getenv("BYPASS_CHANNEL_IDS", "").split(",")
            if channel_id.strip().isdigit()
        }

    async def check(self, channel_id: int) -> tuple[bool, float]:
        """
        Hanya cek apakah channel sedang cooldown, TANPA mengubah state.
        Returns (can_proceed, wait_time).
        """
        if channel_id in self.bypass_channel_ids:
            return True, 0

        now = time.monotonic()
        last_reply_at = self.last_reply_timestamp_by_channel.get(channel_id)
        
        if last_reply_at is not None:
            elapsed = now - last_reply_at
            if elapsed < COOLDOWN_SECONDS:
                return False, COOLDOWN_SECONDS - elapsed
        
        return True, 0

    def mark_replied(self, channel_id: int):
        """
        Tandai channel sudah mendapat reply SUKSES.
        Panggil SETELAH reply berhasil dikirim — bukan sebelumnya.
        """
        self.last_reply_timestamp_by_channel[channel_id] = time.monotonic()
