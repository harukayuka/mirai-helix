# Mirai Helix 🤖✨

Discord bot pintar dengan kepribadian "Mirai" yang bijaksana, kritis, namun tetap keibuan. Dibangun menggunakan `discord.py` dengan integrasi **Multi-Provider AI** (Gemini, Groq, DeepSeek V4 Pro/Flash) untuk analisis percakapan mendalam, pembuatan laporan otomatis, dan memori jangka panjang (Micro-RAG).

## ✨ Fitur Utama

- **💬 Gaya Bicara Natural**: Bahasa Indonesia semi-informal dengan partikel alami (*nggak, kok, sih*), micro-ekspresi, dan teknik *echo* untuk empati maksimal.
- **🧠 Micro-RAG Memory**: Profiling user jangka panjang dengan **TTL 3 hari** dan **thread-safe** di `data/user_profiles.json`.
- **📄 Laporan Batch Otomatis**: Analisis percakapan harian via DeepSeek V4 Pro/Flash, dikirim sebagai file TXT.
- **⏰ Jadwal Auto-Run Fleksibel**: Atur jam eksekusi batch secara custom (0-23 WIB) via slash command tanpa restart.
- **📍 Channel Hasil Terpusat**: Tentukan channel khusus untuk laporan agar chat tidak berantakan.
- **📂 Attachment Processing**: Membaca teks dari PDF, DOCX, XLSX, PPTX, dan TXT.
- **🔄 Multi-Provider AI**: Gemini, Groq, DeepSeek V4 Pro, DeepSeek V4 Flash dengan mekanisme fallback.
- **⚡ Module Manager**: Kontrol modul aktif/nonaktif dinamis tanpa restart.
- **🌤️ Integrasi BMKG**: Data cuaca real-time dari BMKG.
- **💻 Slash Commands Lengkap**: Modular, terorganisir per fitur.

## 🧠 DeepSeek Model Selection

Bot mendukung **dua model DeepSeek V4** yang bisa dipilih langsung dari Discord:

| Model | ID | Cocok Untuk |
|-------|----|-------------|
| **DeepSeek V4 Pro** | `deepseek-ai/deepseek-v4-pro` | Analisis batch mendalam, butuh akurasi tinggi |
| **DeepSeek V4 Flash** | `deepseek-ai/deepseek-v4-flash` | Test cepat, butuh respons lebih ringan |

Gunakan perintah `/deepseek model` untuk melihat dan mengganti model aktif.

## 🛠️ Teknologi

- **Bahasa**: Python 3.11+
- **Core**: `discord.py`, `aiohttp`
- **AI & LLM**:
  - Google Gemini API (Gemini 2.5 Flash)
  - Groq API (Llama 3.1)
  - NVIDIA NIM API (DeepSeek V4 Pro / V4 Flash)
- **File Parsing**: `pdfplumber`, `python-docx`, `openpyxl`, `python-pptx`
- **Data Persistence**: `json` dengan **Atomic Write** & **Thread Locking**

## 📋 Prasyarat

- Python 3.11+
- Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))
- API Keys: Google Gemini, Groq, NVIDIA (DeepSeek)

## ⚙️ Instalasi & Setup

### 1. Clone Repository
```bash
git clone https://github.com/your-username/mirai-helix.git
cd mirai-helix
```

### 2. Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Konfigurasi Environment
Buat file `.env`:
```env
DISCORD_TOKEN=your_discord_bot_token
GEMINI_KEYS=your_gemini_key_1,your_gemini_key_2
GROQ_API_KEY=your_groq_key
NVIDIA_API_KEY=your_nvidia_key_here
```

### 5. Jalankan Bot
```bash
python main.py
```

## 📖 Slash Commands

### Informasi & Utilitas
| Command | Deskripsi |
|---------|-----------|
| `/ask` | Tanya Mirai (kesehatan/curhat) |
| `/ping` | Cek latency bot |
| `/info` | Info tentang Mirai |
| `/status` | Status bot (history, model, latency) |
| `/clear` | Hapus riwayat percakapan (admin) |
| `/cuaca` | Cek prakiraan cuaca BMKG |
| `/report` | Upload laporan batch terbaru |

### Kesehatan
| Command | Deskripsi |
|---------|-----------|
| `/bmi` | Hitung Body Mass Index |
| `/water` | Hitung kebutuhan air harian |

### DeepSeek Batch Processing
| Command | Deskripsi |
|---------|-----------|
| `/deepseek status` | Status modul & model aktif |
| `/deepseek model` | Lihat/ganti model (Pro/Flash) |
| `/deepseek toggle` | Aktifkan/nonaktifkan modul |
| `/deepseek add` | Tambah channel batch |
| `/deepseek remove` | Hapus channel batch |
| `/deepseek run` | Jalankan batch manual |
| `/deepseek test` | Tes prompt ke model |
| `/deepseek autorun` | Atur jadwal auto-run |
| `/deepseek forced_channel` | Set channel paksa hasil |

> `/qwen` grup commands juga tersedia dengan fungsi yang sama (backward compatibility).

### Pengaturan Server
| Command | Deskripsi |
|---------|-----------|
| `/module status` | Status semua modul |
| `/module toggle` | Aktifkan/nonaktifkan modul |
| `/greeting status` | Status welcome/goodbye |
| `/greeting toggle` | Aktifkan/nonaktifkan greeting |
| `/greeting setchannel` | Set channel greeting |
| `/bedtime on/off/status` | Pengingat waktu tidur |
| `/online_counter on/off/status` | Penghitung user voice |

## 📄 Struktur Direktori

```
mirai-helix/
├── ai/
│   ├── deepseek_client.py   # Client DeepSeek V4 Pro/Flash (NVIDIA NIM)
│   ├── gemini.py            # Client Google Gemini
│   ├── groq_client.py       # Client Groq
│   └── prompts/             # System prompt Mirai
├── commands/                # Slash commands (modular)
│   ├── info_command.py      # /ask, /ping, /info, /clear, /status, /cuaca
│   ├── health_command.py    # /bmi, /water
│   ├── deepseek_command.py  # /deepseek (manajemen batch & model)
│   ├── qwen_command.py      # /qwen (backward compat batch)
│   ├── module_command.py    # /module
│   ├── greeting_command.py  # /greeting
│   ├── bedtime_command.py   # /bedtime
│   ├── online_counter_command.py # /online_counter
│   └── general.py           # /report
├── core/
│   ├── command.py           # Loader commands (memanggil semua file di commands/)
│   ├── qwen_batch.py        # Logika batch processing
│   ├── module_manager.py    # Manajemen modul dinamis
│   └── file_reading.py      # Ekstraksi teks dari file
├── data/
│   ├── deepseek_config.json # Konfigurasi model & batch DeepSeek
│   ├── deepseek_user/       # Riwayat chat per user
│   ├── user_profiles.json   # Profil user (Micro-RAG)
│   └── module_config.json   # Status aktif/nonaktif modul
├── utils/
│   ├── rag_utils.py         # Manajemen profil & TTL
│   └── logger.py            # Setup logging
├── .env                     # Konfigurasi sensitif (JANGAN di-commit)
├── requirements.txt         # Dependencies
├── main.py                  # Entry point
├── README.md
└── CHANGELOG.md
```

## 🔄 Alur Kerja Batch

1. **Aktifkan modul**: `/deepseek toggle true`
2. **Setup channel**: `/deepseek add #channel`
3. **Pilih model** (opsional): `/deepseek model` → pilih Pro atau Flash
4. **Atur jadwal** (opsional): `/deepseek autorun 11 59`
5. **Atur channel paksa** (opsional): `/deepseek forced_channel set #channel`
6. **User diskusi** → pesan tersimpan otomatis
7. **Eksekusi**: otomatis sesuai jadwal, atau manual via `/deepseek run`
8. **Laporan**: file TXT dikirim ke channel tujuan

## 📝 Changelog
Lihat [CHANGELOG.md](CHANGELOG.md) untuk detail perubahan versi.

## 📜 Lisensi
MIT License

---
*Dibuat dengan ❤️ untuk komunitas kesehatan mental.*
*Asisten: Mirai (Perawat Muda & Pendamping Emosional)*