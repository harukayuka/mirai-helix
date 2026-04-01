# Mirai - Discord Health Assistant Bot

Mirai adalah Discord bot yang berfungsi sebagai asisten kesehatan dan pendamping emosional di server Helix. Bot ini dirancang untuk memberikan dukungan emosional, edukasi kesehatan, dan mengarahkan pengguna ke profesional medis ketika diperlukan.

## Fitur Utama

- **Konseling Ringan**: Mendengarkan dan memvalidasi perasaan pengguna dengan empati
- **Edukasi Kesehatan**: Memberikan informasi umum tentang kesehatan fisik dan mental
- **Attachment Processing**: Membaca dan memproses file (PDF, DOCX, XLSX, PPTX, TXT)
- **Slash Commands**: `/ask`, `/ping`, `/info`, `/clear`, `/status`
- **Rich Presence**: Status bot yang berubah-ubah secara dinamis
- **Cooldown Management**: Sistem cooldown untuk mencegah spam
- **Multi-key Rotation**: Mendukung multiple Gemini API keys dengan automatic rotation

## Teknologi

- **Discord.py**: Library untuk integrasi Discord
- **Google Gemini API**: Model AI untuk generate respons
- **Python 3.11+**: Runtime environment

## Setup

### 1. Clone atau Extract Project

```bash
cd mirai_v2
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Konfigurasi Environment

Salin `.env.example` ke `.env` dan isi dengan konfigurasi Anda:

```bash
cp .env.example .env
```

Edit `.env` dan isi:
- `DISCORD_TOKEN`: Token bot dari Discord Developer Portal
- `GEMINI_KEYS`: API key(s) dari Google AI Studio
- `GUILD_ID`: (Opsional) Guild ID untuk sinkronisasi commands
- `BYPASS_CHANNEL_IDS`: Channel IDs yang tidak terkena cooldown

### 4. Jalankan Bot

```bash
python main.py
```

## Struktur Proyek

```
mirai_v2/
├── main.py                 # Entry point utama bot
├── memory.py              # Sistem penyimpanan history percakapan
├── config.py              # Konfigurasi (dapat diisi sesuai kebutuhan)
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (jangan commit!)
├── .env.example          # Template environment variables
├── .gitignore            # Git ignore rules
├── history.json          # File penyimpanan history (auto-generated)
│
├── ai/                    # Module AI/Gemini
│   ├── __init__.py
│   ├── gemini.py         # GeminiClient untuk API calls
│   ├── time.py           # Utility untuk waktu WIB
│   └── prompts/
│       └── mirai_system_prompt.txt  # System prompt Mirai
│
├── core/                  # Module core bot
│   ├── __init__.py
│   ├── command.py        # Slash commands
│   └── file_reading.py   # File attachment processing
│
└── utils/                 # Utility functions
    ├── __init__.py
    └── helper.py         # Helper functions
```

## Slash Commands

### `/ask <pertanyaan> [private]`
Tanya Mirai tentang kesehatan atau ceritakan keluhanmu.
- `pertanyaan`: Pertanyaan atau keluhan Anda
- `private`: Jika true, hanya Anda yang bisa lihat respons

### `/ping`
Cek respons bot dan latency.

### `/info`
Lihat informasi tentang Mirai dan cara menggunakannya.

### `/clear` (Admin only)
Hapus riwayat percakapan global.

### `/status` (Admin only)
Lihat status bot, model AI, dan statistik.

## Mention & Reply

Bot akan merespons jika:
1. Anda mention bot di pesan
2. Anda reply ke pesan bot sebelumnya

## File Processing

Bot dapat membaca dan mengekstrak teks dari:
- `.pdf` - PDF documents
- `.docx` - Microsoft Word documents
- `.xlsx` - Microsoft Excel spreadsheets
- `.pptx` - Microsoft PowerPoint presentations
- `.txt` - Plain text files

Batasan:
- Maksimal 5 file per pesan
- Maksimal 10MB per file
- Maksimal 8000 karakter per file
- Maksimal 20000 karakter total

## Cooldown System

- Default cooldown: 30 detik per channel
- Channel yang di-bypass: Tidak terkena cooldown
- Konfigurasi di `.env` dengan `BYPASS_CHANNEL_IDS`

## Memory Management

- Menyimpan hingga 20 pesan terakhir di history
- History disimpan di `history.json`
- Otomatis load saat bot start
- Dapat dihapus dengan command `/clear`

## Troubleshooting

### Bot tidak merespons
1. Cek apakah token Discord valid
2. Cek apakah bot memiliki permission di channel
3. Lihat console untuk error messages

### API Key Error (429)
- Bot akan otomatis rotate ke API key berikutnya
- Jika semua key limit, tunggu 60 detik
- Tambahkan lebih banyak API keys di `.env`

### File tidak bisa dibaca
- Pastikan format file didukung
- Cek ukuran file (max 10MB)
- Lihat console untuk detail error

## Pengembangan

### Menambah Command Baru

Edit `core/command.py` dan tambahkan di method `setup_commands()`:

```python
@self.tree.command(name="nama_command", description="Deskripsi")
async def nama_command(interaction: discord.Interaction):
    await interaction.response.send_message("Respons")
```

### Mengubah System Prompt

Edit file `ai/prompts/mirai_system_prompt.txt` untuk mengubah kepribadian dan perilaku bot.

## Security Notes

⚠️ **PENTING:**
- Jangan commit `.env` ke repository
- Gunakan `.env.example` sebagai template
- Rotate API keys secara berkala
- Jangan share token Discord atau API keys

## License

Proprietary - Helix Server

## Support

Untuk masalah atau saran, hubungi admin server Helix.
