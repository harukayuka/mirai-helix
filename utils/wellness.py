# utils/wellness.py - Health & Wellness Reminders untuk Mirai
import random
from datetime import datetime
import pytz

def get_wellness_reminder() -> str:
    """
    Memberikan pengingat kesehatan acak berdasarkan waktu saat ini (WIB).
    """
    wib = pytz.timezone('Asia/Jakarta')
    now = datetime.now(wib)
    hour = now.hour

    reminders = {
        "pagi": [
            "Sudah minum air putih pagi ini? Jangan lupa hidrasi tubuhmu ya! 💧",
            "Sarapan itu penting untuk energi otakmu hari ini. Jangan dilewatkan ya! 🍳",
            "Coba peregangan ringan selama 5 menit agar badan lebih segar. 🧘‍♀️"
        ],
        "siang": [
            "Jangan lupa istirahatkan matamu sejenak dari layar (aturan 20-20-20). 👀",
            "Sudah makan siang? Pastikan ada sayur di piringmu ya! 🥗",
            "Kalau merasa ngantuk, coba jalan kaki sebentar atau minum air dingin. 🚶‍♂️"
        ],
        "sore": [
            "Sore hari waktu yang baik untuk camilan sehat seperti buah. 🍎",
            "Jangan lupa selesaikan pekerjaanmu pelan-pelan agar tidak stres di malam hari. ✨",
            "Mungkin ini waktu yang tepat untuk secangkir teh hangat tanpa gula. 🍵"
        ],
        "malam": [
            "Sudah malam, kurangi paparan blue light agar tidurmu lebih nyenyak. 🌙",
            "Pastikan kamu tidur cukup malam ini, minimal 7-8 jam ya. 😴",
            "Coba tuliskan 3 hal yang kamu syukuri hari ini sebelum tidur. 📝"
        ]
    }

    if 5 <= hour < 11:
        category = "pagi"
    elif 11 <= hour < 15:
        category = "siang"
    elif 15 <= hour < 19:
        category = "sore"
    else:
        category = "malam"

    return random.choice(reminders[category])

def should_give_reminder(probability: float = 0.3) -> bool:
    """
    Menentukan apakah Mirai harus memberikan pengingat (default 30% peluang).
    """
    return random.random() < probability
