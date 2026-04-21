# Mirai Helix 🤖✨

Discord bot pintar dengan kepribadian "Mirai" yang bijaksana, kritis, namun tetap keibuan. Dibangun menggunakan `discord.py` dengan integrasi **Multi-Provider AI** (Gemini, Groq, Qwen, DeepSeek) untuk analisis percakapan mendalam, pembuatan laporan PDF/TXT otomatis, dan memori jangka panjang (Micro-RAG).

## ✨ Fitur Utama

- **💬 Gaya Bicara Natural**: Menggunakan bahasa Indonesia semi-informal dengan partikel alami (*nggak, kok, sih*), micro-ekspresi, dan teknik *echo* untuk empati maksimal.
- **🧠 Micro-RAG Memory**: Sistem profiling user jangka panjang dengan **TTL 3 hari** dan **thread-safe** yang menyimpan data kepribadian, minat, dan mood di `data/user_profiles.json`.
- **📄 Laporan PDF & TXT Otomatis**: Generasi laporan refleksi harian dalam format **PDF** (rapi, siap cetak) dan **TXT** (ringkas) yang dikirim sebagai attachment.
- **⏰ Jadwal Auto-Run Fleksibel**: Atur jam eksekusi batch analisis secara custom (0-23 WIB) via slash command tanpa perlu restart bot.
- **📍 Channel Hasil Terpusat**: Tentukan channel khusus untuk menerima laporan agar chat tidak berantakan ("buyar").
- **📂 Attachment Processing**: Kemampuan membaca dan menganalisis teks dari file PDF, DOCX, XLSX, PPTX, dan TXT.
- **🔄 Multi-Provider AI**: Dukungan fleksibel untuk Google Gemini, Groq, NVIDIA Qwen, dan DeepSeek dengan mekanisme fallback otomatis.
- **⚡ Module Manager**: Kontrol modul aktif/nonaktif secara dinamis tanpa perlu restart bot.
- **🌤️ Integrasi BMKG**: Data cuaca real-time dari BMKG.
- **💻 Slash Commands Lengkap**: Command manajemen canggih (`/qwen_set_time`, `/qwen_set_channel`, `/qwen_run_now`, `/qwen_status`).

## ✨ Fitur Baru (v2.5.0 – 2026-04-21)

### Channel Paksa (Forced Delivery Channel)
- Admin dapat menetapkan **satu channel khusus** untuk semua laporan Qwen menggunakan command `/setforcedchannel`.
- Prioritas pengiriman menjadi: **Paksa > Channel yang dipilih user > Channel default**.
- Channel paksa dapat diubah atau dihapus kapan saja tanpa restart bot.

### Scheduler Dinamis
- Bot membaca konfigurasi jadwal secara real‑time; perubahan jam atau channel berlaku langsung setelah perintah `/qwen_set_time` atau `/setforcedchannel`.
- Mengurangi kebutuhan restart dan meningkatkan responsivitas.

### Perbaikan Bug & Validasi
- Menangani `AttributeError` pada command handler ketika channel tidak valid.
- Validasi tambahan untuk ID channel yang tidak ada atau bot tidak memiliki permission.

## 🛠️ Teknologi

- **Bahasa**: Python 3.11+
- **Core**: `discord.py`, `aiohttp`
- **AI & LLM**:
  - Google Gemini API (Gemini 2.5 Flash)
  - Groq API (Llama 3.1 untuk peringkasan & profiling)
  - NVIDIA Qwen API (Qwen 3.5 122B untuk analisis refleksi mendalam)
  - DeepSeek API (Alternatif analisis)
- **PDF Generation**: `fpdf2` (Header/Footer kustom, support UTF-8 fallback)
- **File Parsing**: `pdfplumber`, `python-docx`, `openpyxl`, `python-pptx`
- **Data Persistence**: `json` dengan **Atomic Write** & **Thread Locking** untuk keamanan data

## 📋 Prasyarat

- Python 3.11 atau lebih tinggi
- Discord Bot Token (dari [Discord Developer Portal](https://discord.com/developers/applications))
- API Keys untuk:
  - Google Gemini
  - Groq
  - NVIDIA (untuk Qwen)
  - DeepSeek (Opsional)
  - BMKG (Opsional)

## ⚙️ Instalasi & Setup

### 1. Clone Repository
```bash
git clone https://github.com/your-username/mirai-helix.git
cd mirai-helix
```

### 2. Buat Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Konfigurasi Environment Variables
Buat file `.env` di root direktori dengan isi berikut:
```env
DISCORD_TOKEN=your_discord_bot_token_here
GEMINI_KEYS=your_gemini_key_1,your_gemini_key_2
GROQ_API_KEY=your_groq_key_here
QWEN_API_KEY=your_nvidia_key_here
DEEPSEEK_API_KEY=your_deepseek_key_here
BMKG_API_KEY=your_bmkg_key_here
```
> **Catatan**: Pastikan `QWEN_API_KEY` diisi dengan API Key NVIDIA jika ingin menggunakan modul Qwen.

### 5. Jalankan Bot
```bash
python main.py
```
Bot akan otomatis menyinkronkan slash commands saat pertama kali online.

## 📖 Cara Penggunaan

### Slash Commands Qwen (Batch Analysis)

| Command | Deskripsi | Contoh Penggunaan |
| :--- | :--- | :--- |
| `/qwen_status` | Cek status modul, jam auto-run, dan channel tujuan saat ini. | `/qwen_status` |
| `/qwen_set_time` | Atur jam eksekusi auto-run (format 24 jam). | `/qwen_set_time hour:14` (Jam 2 siang) |
| `/qwen_set_channel` | Tetapkan channel khusus untuk laporan. Gunakan `reset` untuk default. | `/qwen_set_channel channel:<#123456789>` |
| `/qwen_run_now` | Jalankan analisis batch secara manual segera. | `/qwen_run_now` |

### Alur Kerja Sistem
1. **Aktifkan Modul**: Gunakan `/module_manager enable qwen` untuk mengaktifkan analisis.
2. **Setup Channel**: Tambahkan channel diskusi ke daftar channel aktif (otomatis atau via command).
3. **Atur Tujuan**: Gunakan `/qwen_set_channel` untuk menentukan di mana laporan akan dikirim.
4. **Diskusi User**: User berdiskusi di channel yang terdaftar. Pesan akan disimpan secara otomatis.
5. **Eksekusi**:
   - **Otomatis**: Bot akan menjalankan analisis setiap hari pada jam yang ditentukan (default 12:00 WIB).
   - **Manual**: Admin bisa memicu proses kapan saja dengan `/qwen_run_now`.
6. **Laporan**: Bot akan menghasilkan file **PDF** dan **TXT** yang berisi analisis mendalam (perspektif CBT/DBT) dan mengirimkannya sebagai attachment ke channel tujuan.

## 🛠️ Troubleshooting

### Bot tidak start
- **Error: `DISCORD_TOKEN tidak ditemukan`**: Pastikan file `.env` ada di root dan `DISCORD_TOKEN` sudah diisi dengan benar.
- **Error: `ModuleNotFoundError`**: Pastikan semua dependencies terinstall (`pip install -r requirements.txt`).

### Laporan tidak terkirim
- **Channel tidak ditemukan**: Pastikan Bot memiliki permission `Read Messages` dan `Send Messages` di channel tujuan.
- **API Key Invalid**: Cek apakah `QWEN_API_KEY` valid dan memiliki kuota API yang cukup.

### Data Profil Korup atau Hilang
- Sistem menggunakan **Atomic Write** untuk mencegah korupsi file. Jika `data/user_profiles.json` rusak, bot akan otomatis membuat file baru kosong saat start.
- Profil user yang tidak aktif lebih dari **3 hari** akan otomatis dibersihkan (TTL) untuk menghemat storage.

## 📄 Struktur Direktori

```
mirai-helix/
├── ai/
│   └── prompts/              # System prompt Mirai
├── core/
│   ├── command.py            # Slash commands (Qwen, Module Manager)
│   ├── qwen_batch.py         # Logika batch processing & PDF generation
│   ├── module_manager.py     # Manajemen modul dinamis
│   └── file_reading.py       # Ekstraksi teks dari file attachment
├── data/
│   ├── user_chats/           # Riwayat chat per user (sementara)
│   ├── user_profiles.json    # Profil user (Micro-RAG)
│   ├── qwen_config.json      # Konfigurasi Qwen (jam, channel, dll)
│   └── qwen_results/         # Hasil laporan PDF/TXT yang digenerate
├── utils/
│   ├── rag_utils.py          # Manajemen profil & TTL (Thread-safe)
│   └── logger.py             # Setup logging
├── .env                      # Konfigurasi sensitif (JANGAN di-commit)
├── requirements.txt          # Dependencies Python
├── main.py                   # Entry point aplikasi
├── README.md                 # Dokumentasi ini
└── CHANGELOG.md              # Riwayat perubahan versi
```

## 📝 Changelog
Lihat [CHANGELOG.md](CHANGELOG.md) untuk detail perubahan versi terbaru (v2.3.0).

## 📜 Lisensi
Proyek ini dilisensikan di bawah MIT License.

## 👥 Kontribusi
Kontribusi sangat diterima! Silakan buka issue atau pull request untuk perbaikan bug, penambahan fitur, atau perbaikan dokumentasi.

---
*Dibuat dengan ❤️ untuk komunitas kesehatan mental di Helix.*
*Asisten: Mirai (Persona: 23-27 tahun, Perawat Muda & Pendamping Emosional)*