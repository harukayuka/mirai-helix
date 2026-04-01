# config.py - Konfigurasi default untuk Mirai Bot

# ===== MEMORY CONFIG =====
MAX_HISTORY = 15  # Jumlah maksimal pesan yang disimpan
HISTORY_FILE = "history.json"  # File untuk menyimpan history

# ===== COOLDOWN CONFIG =====
COOLDOWN_SECONDS = 30  # Cooldown antar respons per channel
COOLDOWN_REPLY_DELAY = 3  # Waktu sebelum pesan cooldown dihapus

# ===== API CONFIG =====
GEMINI_MODEL = "gemini-2.5-flash"  # Model Gemini yang digunakan
GEMINI_API_VERSION = "v1beta"  # Versi API Gemini
MAX_RETRIES = 5  # Maksimal retry untuk API calls
REQUEST_TIMEOUT = 45  # Timeout untuk HTTP requests (detik)
GENERATE_DEADLINE = 180  # Deadline untuk generate respons (detik)

# ===== GENERATION CONFIG =====
TEMPERATURE = 0.7  # Kreativitas respons (0.0 - 1.0)
MAX_OUTPUT_TOKENS = 2048  # Maksimal output tokens per respons
TOP_P = 0.95  # Top-p sampling parameter

# ===== FILE PROCESSING CONFIG =====
SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".xlsx", ".pptx", ".txt"}
MAX_ATTACHMENTS = 5  # Maksimal file per pesan
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_TEXT_PER_FILE_CHARS = 8000  # Teks maksimal per file
MAX_TOTAL_CHARS = 20000  # Total teks maksimal dari semua file

# ===== RICH PRESENCE CONFIG =====
RPC_UPDATE_INTERVAL = 1800  # Update presence setiap 30 menit (detik)

# ===== KEY ROTATION CONFIG =====
MAX_KEY_WAIT = 120  # Maksimal tunggu semua key cooldown (detik)
KEY_COOLDOWN_DURATION = 60  # Durasi cooldown per key saat rate limit (detik)

# ===== NEWS SUMMARY CONFIG =====
NEWS_SOURCE_URL = "https://raw.githubusercontent.com/harukayuka2/news-mirai/main/data/berita.json"
NEWS_JSON_PATH = "data/berita.json"
NEWS_SUMMARY_PATH = "data/summary.json"
NEWS_REFRESH_SECONDS = 3600  # Refresh berita dan summary setiap 1 jam
NEWS_MAX_ITEMS = 30  # Batasi jumlah berita yang dirangkum
NEWS_MAX_CHARS = 12000  # Batasi total karakter berita yang dikirim ke AI
