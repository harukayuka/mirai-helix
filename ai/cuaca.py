# ai/cuaca.py - Integrasi API BMKG untuk Mirai
"""
Modul untuk mengambil data cuaca dari API Terbuka BMKG.
Mendukung pencarian cuaca berdasarkan nama lokasi (Kota/Kecamatan/Desa).
"""

import aiohttp
import logging
import re
import json
from typing import Dict, Optional, Any, List
import asyncio
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base URL API BMKG
BMKG_API_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca"
# API Wilayah Indonesia (Emsifa)
WILAYAH_API_BASE = "https://emsifa.github.io/api-wilayah-indonesia/api"

# Default kode wilayah (Kemayoran, Jakarta Pusat)
DEFAULT_ADM4 = "31.71.03.1001"

class BMKGClient:
    """Klien untuk mengambil data cuaca dari BMKG menggunakan aiohttp (async)."""

    def __init__(self):
        # Load ADM4 mapping (kota -> kode) dari file JSON jika ada
        self._adm4_map: Dict[str, str] = {}
        try:
            adm4_path = Path(__file__).parent.parent / "data" / "adm4_codes.json"
            if adm4_path.exists():
                self._adm4_map = json.loads(adm4_path.read_text(encoding="utf-8"))
                # Pastikan semua key uppercase untuk pencocokan mudah
                self._adm4_map = {k.upper(): v for k, v in self._adm4_map.items()}
        except Exception as e:
            logger.error(f"[BMKG] Gagal load adm4_codes.json: {e}")
        # No persistent session; created per request to avoid blocking
        pass

    async def _get_json(self, url: str, **kwargs) -> Optional[Dict]:
        """Helper to GET JSON with aiohttp, handling errors and timeouts."""
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, **kwargs) as resp:
                    if resp.status != 200:
                        logger.error(f"HTTP {resp.status} for {url}")
                        return None
                    return await resp.json()
        except asyncio.TimeoutError:
            logger.error(f"Timeout saat mengakses {url}")
            return None
        except Exception as e:
            logger.error(f"Error saat GET {url}: {e}")
            return None

    async def search_location_code(self, query: str) -> Optional[str]:
        """Mencari kode adm4 berdasarkan nama lokasi secara async."""
        query = query.strip().upper()
        if not query:
            return DEFAULT_ADM4
        # Shortcut for Jakarta
        if "JAKARTA" in query:
            return DEFAULT_ADM4
        # Simple city map lookup
        # 1️⃣ Pencarian di mapping yang di‑load dari file JSON (jika tersedia)
        if self._adm4_map:
            for city, code in self._adm4_map.items():
                if city in query:
                    return code
        # 2️⃣ Hard‑coded fallback map (untuk kota‑populer)
        city_map = {
            "BANDUNG": "32.73.01.1001",
            "SURABAYA": "35.78.01.1001",
            "MEDAN": "12.71.01.1001",
            "MAKASSAR": "73.71.01.1001",
            "YOGYAKARTA": "34.71.01.1001",
            "BEKASI": "32.75.01.1001",
            "TANGERANG": "36.71.01.1001",
            "DEPOK": "32.76.01.1001",
            "BOGOR": "32.71.01.1001",
            "SEMARANG": "33.74.01.1001",
        }
        for city, code in city_map.items():
            if city in query:
                return code
        # Fallback: try to fetch provinces (not used further but kept for compatibility)
        await self._get_json(f"{WILAYAH_API_BASE}/provinces.json")
        return DEFAULT_ADM4

    async def get_weather_raw(self, adm4: str = DEFAULT_ADM4) -> Optional[Dict[str, Any]]:
        """Mengambil data mentah cuaca BMKG secara async."""
        params = {"adm4": adm4}
        data = await self._get_json(BMKG_API_URL, params=params)
        if not data or "data" not in data or not data["data"]:
            return None
        location_info = data.get("lokasi", {})
        weather_list = data["data"][0].get("cuaca", [])
        if not weather_list:
            return None
        forecasts = weather_list[:3]
        return {
            "lokasi": {
                "desa": location_info.get("desa"),
                "kecamatan": location_info.get("kecamatan"),
                "kotkab": location_info.get("kotkab"),
                "provinsi": location_info.get("provinsi"),
            },
            "prakiraan": forecasts,
            "sumber": "BMKG",
        }

    def extract_location_from_text(self, text: str) -> Optional[str]:
        """Ekstrak nama lokasi dari teks menggunakan regex sederhana."""
        patterns = [
            r"cuaca (?:di|ke|daerah|wilayah) ([a-zA-Z\s]+)",
            r"bagaimana cuaca ([a-zA-Z\s]+)",
            r"cek cuaca ([a-zA-Z\s]+)",
            r"cuaca ([a-zA-Z\s]+) (?:hari ini|besok|gimana)"
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None

if __name__ == "__main__":
    async def main():
        client = BMKGClient()
        loc = client.extract_location_from_text("Gimana cuaca di Bandung hari ini?")
        print(f"Detected location: {loc}")
        if loc:
            code = await client.search_location_code(loc)
            print(f"Location code: {code}")
            raw = await client.get_weather_raw(code)
            print(f"Raw data: {raw['lokasi'] if raw else 'None'}")
    asyncio.run(main())
