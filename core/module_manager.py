# core/module_manager.py - Manajemen Modul Mirai
"""
Modul untuk mengelola status aktif/nonaktif dari berbagai fitur Mirai.

Fitur:
- Enable/disable modul seperti calculator, weather, news, greeting, qwen, wellness
- Konfigurasi disimpan di data/module_config.json
- Dapat diakses dari command /module
"""
import json
from pathlib import Path
from utils.logger import setup_logging

logger = setup_logging()
MODULE_CONFIG_PATH = Path("data/module_config.json")

class ModuleManager:
    """
    Kelas untuk mengelola status aktif/nonaktif modul perintah slash.
    Menggunakan cache in-memory + mtime check untuk menghindari disk read berlebihan.
    """
    def __init__(self):
        """
        Inisialisasi ModuleManager.
        
        Note:
            self.modules berisi daftar semua modul yang didukung.
            _config_cache: cache in-memory hasil baca dari JSON.
            _cache_mtime: timestamp modifikasi file terakhir yang sudah di-cache.
        """
        self._ensure_config_exists()
        self.modules = ["calculator", "weather", "news", "greeting", "deepseek", "wellness"]
        # Cache — baca disk hanya jika file berubah
        self._config_cache: dict = {}
        self._cache_mtime: float = 0.0
        self._refresh_cache()

    def _ensure_config_exists(self):
        """
        Memastikan file konfigurasi modul ada.
        
        Jika file tidak ada, buat dengan default config (semua modul aktif).
        """
        if not MODULE_CONFIG_PATH.parent.exists():
            MODULE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        if not MODULE_CONFIG_PATH.exists():
            # Default config: semua modul aktif
            default_config = {
                "calculator": True,
                "weather": True,
                "news": True,
                "greeting": True,
                "deepseek": True,  # Modul DeepSeek batch processing
                "wellness": True  # Modul wellness
            }
            self._save_config(default_config)
            logger.info("[MODULE] Config file dibuat dengan default: semua modul aktif")

    def _load_config(self):
        """
        Membaca konfigurasi modul dari file JSON.
        
        Returns:
            Dict[str, bool]: Konfigurasi modul. Jika error, return default (semua aktif).
        """
        try:
            with open(MODULE_CONFIG_PATH, 'r') as f:
                config = json.load(f)
                # Pastikan semua modul ada di config (untuk kasus update versi)
                for module in self.modules:
                    if module not in config:
                        config[module] = True
                        logger.info("[MODULE] Modul '%s' ditambahkan ke config dengan default True", module)
                return config
        except Exception as e:
            logger.error(f"[MODULE] Error loading config: {e}")
            # Return default config jika ada error
            return {m: True for m in self.modules}

    def _refresh_cache(self):
        """Refresh cache dari disk hanya jika file termodifikasi."""
        try:
            mtime = MODULE_CONFIG_PATH.stat().st_mtime
            if mtime != self._cache_mtime:
                self._config_cache = self._load_config()
                self._cache_mtime = mtime
        except Exception:
            pass

    def _save_config(self, config):
        """Menyimpan konfigurasi modul ke file JSON."""
        try:
            with open(MODULE_CONFIG_PATH, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            logger.error(f"[MODULE] Error saving config: {e}")

    def is_enabled(self, module_name: str) -> bool:
        """Cek apakah modul tertentu aktif. Gunakan cache — hanya baca disk jika file berubah."""
        self._refresh_cache()
        return self._config_cache.get(module_name, True)

    def set_status(self, module_name: str, status: bool):
        """Mengatur status aktif/nonaktif modul. Update cache setelah write."""
        config = self._load_config()
        config[module_name] = status
        self._save_config(config)
        # Update cache langsung — hindari disk read berikutnya
        self._config_cache = config
        try:
            self._cache_mtime = MODULE_CONFIG_PATH.stat().st_mtime
        except Exception:
            pass

    def get_all_status(self):
        """Mendapatkan status semua modul."""
        return self._load_config()

# Instance global untuk kemudahan akses
module_manager = ModuleManager()
