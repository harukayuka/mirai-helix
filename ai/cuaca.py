# ai/cuaca.py - Integrasi API BMKG untuk Mirai
"""
Modul untuk mengambil data cuaca dari API Terbuka BMKG.
Mendukung pencarian cuaca berdasarkan nama lokasi (Kota/Kecamatan/Desa).
"""

import requests
import logging
import re
from typing import Dict, Optional, Any, List
from datetime import datetime

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
    """Klien untuk mengambil data cuaca dari BMKG."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "Mirai-V3/1.0 (BMKG Weather Integration)"
        })

    def search_location_code(self, query: str) -> Optional[str]:
        """
        Mencari kode adm4 berdasarkan nama lokasi.
        Karena API Emsifa statis, kita perlu melakukan pencarian bertahap atau menebak.
        Untuk kesederhanaan dan kecepatan, kita akan menggunakan pendekatan pencarian 
        yang lebih cerdas jika memungkinkan, atau fallback ke default.
        """
        query = query.strip().upper()
        if not query:
            return DEFAULT_ADM4

        try:
            # 1. Ambil daftar provinsi
            prov_resp = self.session.get(f"{WILAYAH_API_BASE}/provinces.json", timeout=10)
            prov_resp.raise_for_status()
            provinces = prov_resp.json()
            
            # 2. Cari kabupaten/kota di provinsi yang relevan (opsional, tapi untuk akurasi)
            # Untuk mempercepat, kita coba cari langsung di beberapa kota besar jika query cocok
            # Namun alur yang benar adalah: Prov -> Kab -> Kec -> Desa
            
            # Shortcut: Jika query adalah "Jakarta", return Kemayoran
            if "JAKARTA" in query:
                return DEFAULT_ADM4
                
            # Karena keterbatasan API statis untuk pencarian global "string to ID", 
            # kita akan mengimplementasikan pencarian sederhana untuk beberapa kota besar.
            # Di produksi, sebaiknya ada database lokal untuk mapping ini.
            
            city_map = {
                "BANDUNG": "32.73.01.1001", # Contoh: Sukajadi, Bandung
                "SURABAYA": "35.78.01.1001", # Contoh: Genteng, Surabaya
                "MEDAN": "12.71.01.1001",    # Contoh: Medan Kota
                "MAKASSAR": "73.71.01.1001", # Contoh: Mariso, Makassar
                "YOGYAKARTA": "34.71.01.1001", # Contoh: Danurejan, Yogyakarta
                "BEKASI": "32.75.01.1001",   # Contoh: Bekasi Barat
                "TANGERANG": "36.71.01.1001", # Contoh: Tangerang
                "DEPOK": "32.76.01.1001",    # Contoh: Pancoran Mas, Depok
                "BOGOR": "32.71.01.1001",    # Contoh: Bogor Selatan
                "SEMARANG": "33.74.01.1001", # Contoh: Semarang Tengah
            }
            
            for city, code in city_map.items():
                if city in query:
                    return code
            
            return DEFAULT_ADM4 # Fallback ke Jakarta jika tidak ketemu
            
        except Exception as e:
            logger.error(f"Gagal mencari kode lokasi: {e}")
            return DEFAULT_ADM4

    def get_weather_raw(self, adm4: str = DEFAULT_ADM4) -> Optional[Dict[str, Any]]:
        """
        Mengambil data mentah dari BMKG untuk diproses oleh Gemini.
        """
        try:
            params = {"adm4": adm4}
            response = self.session.get(BMKG_API_URL, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if not data or "data" not in data or not data["data"]:
                return None
                
            location_info = data.get("lokasi", {})
            weather_list = data["data"][0].get("cuaca", [])
            
            if not weather_list or not weather_list[0]:
                return None
                
            # Ambil 3 data prakiraan terdekat (per 3 jam) untuk konteks lebih kaya
            forecasts = weather_list[:3]
            
            return {
                "lokasi": {
                    "desa": location_info.get("desa"),
                    "kecamatan": location_info.get("kecamatan"),
                    "kotkab": location_info.get("kotkab"),
                    "provinsi": location_info.get("provinsi"),
                },
                "prakiraan": forecasts,
                "sumber": "BMKG"
            }
            
        except Exception as e:
            logger.error(f"Gagal mengambil data mentah BMKG: {e}")
            return None

    def extract_location_from_text(self, text: str) -> Optional[str]:
        """
        Mengekstrak nama lokasi dari teks user menggunakan regex sederhana.
        Contoh: "cuaca di Bandung gimana?" -> "Bandung"
        """
        patterns = [
            r"cuaca (?:di|ke|daerah|wilayah) ([a-zA-Z\s]+)",
            r"bagaimana cuaca ([a-zA-Z\s]+)",
            r"cek cuaca ([a-zA-Z\s]+)",
            r"cuaca ([a-zA-Z\s]+) (?:hari ini|besok|gimana)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

if __name__ == "__main__":
    client = BMKGClient()
    loc = client.extract_location_from_text("Gimana cuaca di Bandung hari ini?")
    print(f"Detected location: {loc}")
    if loc:
        code = client.search_location_code(loc)
        print(f"Location code: {code}")
        raw = client.get_weather_raw(code)
        print(f"Raw data: {raw['lokasi'] if raw else 'None'}")
