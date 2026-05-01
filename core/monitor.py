"""
Resource Monitor untuk Mirai Bot.
Memantau penggunaan CPU dan RAM menggunakan psutil.
"""
import psutil
import logging
import asyncio
import os

logger = logging.getLogger('mirai-helix.monitor')

class ResourceMonitor:
    """
    Monitor resource usage (CPU & RAM) secara berkala.
    """
    def __init__(self, threshold_ram_mb: int = 800, interval_seconds: int = 300):
        """
        Inisialisasi monitor.
        
        Args:
            threshold_ram_mb: Ambang batas RAM (MB) untuk warning.
            interval_seconds: Interval pengecekan (default 5 menit).
        """
        self.threshold_ram_mb = threshold_ram_mb
        self.interval_seconds = interval_seconds
        self.process = psutil.Process(os.getpid())
        self._task = None

    async def start_monitoring(self):
        """Mulai loop monitoring background."""
        self._task = asyncio.current_task()  # simpan task
        logger.info(f"Resource monitor started. Interval: {self.interval_seconds}s, Threshold: {self.threshold_ram_mb}MB")
        try:
            while True:
                try:
                    await self._check_resources()
                except Exception as e:
                    logger.error(f"Error during resource check: {e}", exc_info=True)
                await asyncio.sleep(self.interval_seconds)
        except asyncio.CancelledError:
            logger.info("Resource monitor stopped.")
            raise

    async def _check_resources(self):
        """Cek CPU dan RAM, log jika ada anomali."""
        try:
            # Cek RAM
            mem_info = self.process.memory_info()
            ram_mb = mem_info.rss / 1024 / 1024  # Konversi ke MB

            # Cek CPU (perlu interval untuk akurasi, jadi kita pakai perkiraan instan)
            cpu_percent = await asyncio.to_thread(self.process.cpu_percent, 0.1)

            status_msg = f"Resource Check - RAM: {ram_mb:.2f}MB | CPU: {cpu_percent}%"

            if ram_mb > self.threshold_ram_mb:
                logger.warning(f"⚠️ HIGH MEMORY USAGE: {status_msg}")
                # Opsional: Trigger cleanup otomatis jika RAM terlalu tinggi
                # await self._emergency_cleanup()
            elif cpu_percent > 80:
                logger.warning(f"⚠️ HIGH CPU USAGE: {status_msg}")
            else:
                logger.debug(status_msg)
        except Exception as e:
            logger.error(f"Error checking resources: {e}")

    async def _emergency_cleanup(self):
        """
        Placeholder untuk fungsi pembersihan darurat jika RAM penuh.
        Dapat dipanggil untuk membersihkan cache atau file sementara.
        """
        logger.critical("Performing emergency cleanup...")
        # Contoh: Panggil fungsi clean_old_profiles atau hapus cache di sini
        # from utils.cleanup import clean_old_reports
        # clean_old_reports()

    def stop_monitoring(self):
        """Hentikan monitoring."""
        if self._task:
            self._task.cancel()
            self._task = None
