# ai/time.py - Utility untuk waktu WIB
"""
Utility untuk mendapatkan waktu dan tanggal dalam zona WIB (Asia/Jakarta).
Digunakan untuk memberikan konteks waktu kepada AI model.

FIXED:
- get_wib_time() sekarang mengembalikan objek datetime (bukan str),
  sehingga pemanggil dapat menggunakan .strftime(), .hour, .minute, dll.
- get_wib_time_str() mengembalikan string terformat Bahasa Indonesia
  untuk dipakai di system prompt / konteks.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

_WIB = ZoneInfo("Asia/Jakarta")

_DAYS_ID = {
    "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu",
    "Thursday": "Kamis", "Friday": "Jumat", "Saturday": "Sabtu",
    "Sunday": "Minggu",
}

_MONTHS_ID = {
    "January": "Januari", "February": "Februari", "March": "Maret",
    "April": "April", "May": "Mei", "June": "Juni",
    "July": "Juli", "August": "Agustus", "September": "September",
    "October": "Oktober", "November": "November", "December": "Desember",
}


def get_wib_time() -> datetime:
    """
    Mengembalikan objek datetime saat ini dalam zona WIB (Asia/Jakarta).

    Pemanggil bebas menggunakan .strftime(), .hour, .minute, .date(), dsb.

    Contoh:
        now = get_wib_time()
        now.strftime('%H:%M')       # '14:30'
        now.strftime('%d-%m-%Y')    # '06-03-2026'
    """
    return datetime.now(_WIB)


def get_wib_time_str() -> str:
    """
    Mengembalikan string waktu terformat Bahasa Indonesia untuk dipakai
    sebagai konteks di system prompt.

    Contoh hasil:
        "Hari ini adalah Senin, 6 Maret 2026, pukul 14:30 WIB."
    """
    now = get_wib_time()

    hari   = _DAYS_ID.get(now.strftime("%A"), now.strftime("%A"))
    bulan  = _MONTHS_ID.get(now.strftime("%B"), now.strftime("%B"))
    tanggal = now.strftime("%d")
    tahun   = now.strftime("%Y")
    jam     = now.strftime("%H:%M")

    return f"Hari ini adalah {hari}, {tanggal} {bulan} {tahun}, pukul {jam} WIB."
