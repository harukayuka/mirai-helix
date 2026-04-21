# ai/time.py - Utility untuk waktu WIB
"""
Utility untuk mendapatkan waktu dan tanggal dalam zona WIB (Asia/Jakarta).
Digunakan untuk memberikan konteks waktu kepada AI model.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

def get_wib_time() -> str:
    """
    Mengembalikan string waktu dan tanggal dalam zona WIB (Asia/Jakarta).
    
    Returns:
        str: Formatted time string, e.g., "Hari ini adalah Senin, 6 Maret 2026, pukul 14:30 WIB"
    """
    now = datetime.now(ZoneInfo('Asia/Jakarta'))

    # Nama hari dan bulan dalam Bahasa Indonesia
    days_ind = {
        'Monday': 'Senin', 'Tuesday': 'Selasa', 'Wednesday': 'Rabu',
        'Thursday': 'Kamis', 'Friday': 'Jumat', 'Saturday': 'Sabtu',
        'Sunday': 'Minggu'
    }
    months_ind = {
        'January': 'Januari', 'February': 'Februari', 'March': 'Maret',
        'April': 'April', 'May': 'Mei', 'June': 'Juni',
        'July': 'Juli', 'August': 'Agustus', 'September': 'September',
        'October': 'Oktober', 'November': 'November', 'December': 'Desember'
    }

    hari_en = now.strftime('%A')
    bulan_en = now.strftime('%B')
    hari = days_ind.get(hari_en, hari_en)
    bulan = months_ind.get(bulan_en, bulan_en)

    tanggal = now.strftime('%d')
    tahun = now.strftime('%Y')
    jam = now.strftime('%H:%M')

    return f"Hari ini adalah {hari}, {tanggal} {bulan} {tahun}, pukul {jam} WIB."
