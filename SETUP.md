# Setup Guide - Mirai Discord Bot

Panduan lengkap untuk setup dan menjalankan Mirai Discord Bot.

## Prerequisites

- Python 3.11 atau lebih tinggi
- pip (Python package manager)
- Discord Bot Token (dari Discord Developer Portal)
- Google Gemini API Keys (dari Google AI Studio)

## Step 1: Persiapan

### 1.1 Clone atau Extract Project

```bash
cd mirai_v2
```

### 1.2 Buat Virtual Environment (Opsional tapi Recommended)

```bash
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

## Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

Atau jika menggunakan pip3:

```bash
pip3 install -r requirements.txt
```

## Step 3: Setup Environment Variables

### 3.1 Salin Template

```bash
cp .env.example .env
```

### 3.2 Edit `.env`

Buka file `.env` dengan text editor favorit Anda dan isi:

```env
# Discord Bot Token
DISCORD_TOKEN=your_discord_token_here

# Guild ID (opsional)
GUILD_ID=

# Gemini API Keys (pisahkan dengan koma jika multiple)
GEMINI_KEYS=your_api_key_1, your_api_key_2

# Channel IDs untuk bypass cooldown
BYPASS_CHANNEL_IDS=1476551441265983603

# API Version (default: v1beta)
GEMINI_API_VERSION=v1beta
```

## Step 4: Dapatkan Credentials

### 4.1 Discord Bot Token

1. Buka [Discord Developer Portal](https://discord.com/developers/applications)
2. Klik "New Application" dan beri nama
3. Pergi ke tab "Bot"
4. Klik "Add Bot"
5. Di bawah "TOKEN", klik "Copy"
6. Paste ke `.env` sebagai `DISCORD_TOKEN`

### 4.2 Gemini API Keys

1. Buka [Google AI Studio](https://aistudio.google.com/apikey)
2. Klik "Create API Key"
3. Pilih atau buat project baru
4. Copy API key yang dihasilkan
5. Paste ke `.env` sebagai `GEMINI_KEYS`
6. Bisa tambahkan multiple keys dengan separator koma

### 4.3 Discord Guild ID (Opsional)

Jika ingin commands hanya di guild tertentu:
1. Enable Developer Mode di Discord (User Settings > Advanced > Developer Mode)
2. Right-click server > Copy Server ID
3. Paste ke `.env` sebagai `GUILD_ID`

## Step 5: Jalankan Bot

### 5.1 Jalankan dengan Python

```bash
python main.py
```

Atau:

```bash
python3 main.py
```

### 5.2 Cek Output

Jika berhasil, akan melihat output seperti:

```
[Memory] Loaded X pesan dari disk
[INFO] Loaded Mirai system prompt dari: ai/prompts/mirai_system_prompt.txt
[INFO] Starting Mirai Discord Bot...
[INFO] Using model: Gemini 2.5 Flash
[INFO] Cooldown: 30s
[INFO] Max history: 20 messages
✅ Bot connected as Mirai#1234
✅ Global commands synced
[RPC] Status: playing Mirai Health Assistant
```

## Step 6: Invite Bot ke Server

1. Buka [Discord Developer Portal](https://discord.com/developers/applications)
2. Pilih aplikasi Mirai
3. Pergi ke tab "OAuth2" > "URL Generator"
4. Pilih scopes: `bot`
5. Pilih permissions:
   - Send Messages
   - Send Messages in Threads
   - Embed Links
   - Attach Files
   - Read Message History
   - Use Slash Commands
6. Copy generated URL dan buka di browser
7. Pilih server untuk invite bot

## Troubleshooting

### Bot tidak start

**Error: `DISCORD_TOKEN tidak ditemukan di .env`**
- Pastikan file `.env` ada di direktori yang sama dengan `main.py`
- Pastikan `DISCORD_TOKEN` diisi dengan benar

**Error: `Tidak ada GEMINI_KEYS di .env`**
- Pastikan `GEMINI_KEYS` diisi dengan minimal 1 API key
- Pastikan format benar (pisahkan dengan koma jika multiple)

### Bot tidak merespons

1. Cek apakah bot online di Discord
2. Cek apakah bot memiliki permission di channel
3. Cek console untuk error messages
4. Cek apakah mention atau reply ke bot

### API Key Error

**Error: `429 Too Many Requests`**
- Bot akan otomatis rotate ke API key berikutnya
- Jika semua key limit, tunggu 60 detik
- Tambahkan lebih banyak API keys di `.env`

**Error: `400 Bad Request`**
- Cek format history di console
- Coba clear history dengan `/clear` command

### File tidak bisa dibaca

- Pastikan format file didukung (.pdf, .docx, .xlsx, .pptx, .txt)
- Pastikan ukuran file < 10MB
- Cek console untuk detail error

## Development

### Menambah Command Baru

Edit `core/command.py` dan tambahkan di method `setup_commands()`:

```python
@self.tree.command(name="nama_command", description="Deskripsi")
async def nama_command(interaction: discord.Interaction):
    await interaction.response.send_message("Respons")
```

### Mengubah System Prompt

Edit `ai/prompts/mirai_system_prompt.txt`

### Mengubah Konfigurasi

Edit `config.py` untuk mengubah default values

## Production Deployment

Untuk production, gunakan process manager seperti:

### Systemd (Linux)

Buat file `/etc/systemd/system/mirai.service`:

```ini
[Unit]
Description=Mirai Discord Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/mirai_v2
ExecStart=/usr/bin/python3 /home/ubuntu/mirai_v2/main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Jalankan:

```bash
sudo systemctl enable mirai
sudo systemctl start mirai
sudo systemctl status mirai
```

### PM2 (Node.js-based)

```bash
npm install -g pm2
pm2 start main.py --name "mirai" --interpreter python3
pm2 save
pm2 startup
```

## Security Checklist

- [ ] `.env` tidak di-commit ke repository
- [ ] Gunakan `.env.example` sebagai template
- [ ] Rotate API keys secara berkala
- [ ] Jangan share token Discord atau API keys
- [ ] Gunakan `.gitignore` untuk exclude sensitive files

## Support

Untuk masalah atau saran, hubungi admin server Helix.
