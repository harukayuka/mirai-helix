# Changelog - Mirai Helix

## [3.1.0] - 2026-05-02
### ✨ Added
- **`.env.example`**: File template konfigurasi environment dengan dokumentasi lengkap untuk semua variabel yang dibutuhkan.

### ⚡ Improved
- **`ai/cuaca.py`**: Auto-download database wilayah dari GitHub (cahyadsn/wilayah), parse SQL dump, dan simpan ke SQLite via `aiosqlite` (async, non-blocking).
  - Download otomatis `wilayah.sql` (2.9 MB) saat pertama kali dibutuhkan.
  - Import 91.162 baris data wilayah ke `data/wilayah.db`.
  - File SQL otomatis dihapus setelah import berhasil (hemat disk).
  - Pencarian lokasi menggunakan `aiosqlite` dengan prioritas: Kota → Kabupaten → Kecamatan → Desa.
  - Lazy initialization: DB hanya di-download saat pertama kali cuaca diminta.
- **`README.md`**: Ditambahkan informasi tentang `.env.example` dan database wilayah otomatis.
- **`ai/cuaca.py -- BMKGClient.search_location_code()`**: Strategi pencarian ditingkatkan — "Bandung" sekarang mengarah ke **Kota Bandung** (32.73), bukan desa Bandung di Tulungagung.

### 🧹 Cleanup
- File SQL sementara (`wilayah.sql`) otomatis dihapus setelah di-import ke DB.

## [3.0.0] - 2026-05-01
### ✨ Added
- **Model DeepSeek V4 Flash**: Dukungan model `deepseek-ai/deepseek-v4-flash` sebagai alternatif lebih ringan & cepat dari `deepseek-v4-pro`.
- **Command `/deepseek model`**: Admin dapat mengganti model DeepSeek aktif (Pro / Flash) langsung dari Discord tanpa restart bot. Pilihan tersimpan di `data/deepseek_config.json`.
- **Refactor Slash Commands**: Seluruh command dipisah dari `core/command.py` (monolitik ~1000 baris) menjadi file-file terpisah di `commands/`:
  - `info_command.py` → `/ask`, `/ping`, `/info`, `/clear`, `/status`, `/cuaca`
  - `health_command.py` → `/bmi`, `/water`
  - `deepseek_command.py` → `/deepseek` (add, remove, status, toggle, run, autorun, forced_channel, test, model)
  - `qwen_command.py` → `/qwen` (add, remove, status, toggle, run, autorun, forced_channel, test, result)
  - `module_command.py` → `/module` (status, toggle)
  - `greeting_command.py` → `/greeting` (status, toggle, setchannel)
  - `bedtime_command.py` → `/bedtime` (on, off, status)
  - `online_counter_command.py` → `/online_counter` (on, off, status)
  - `general.py` → `/report` (sudah ada sebelumnya)
- **`core/command.py` sebagai loader**: File utama hanya menjadi entry point yang mengimpor dan mendaftarkan semua command dari folder `commands/`.

### 🔄 Changed
- **`core/command.py`**: Dari ~1000 baris menjadi ~80 baris (loader murni).
- **`ai/deepseek_client.py`**: Model tidak lagi hardcode. Menggunakan `get_active_model()` yang membaca dari config. Fungsi baru `set_active_model()`, `get_model_display_name()`.

### 🧹 Cleanup
- Hapus direktori duplikat `ref-deepseek-v4-pro/`.
- Hapus semua `__pycache__` dan file `.pyc`.
- Hapus file migrasi (`CLONING_*_TO_DEEPSEEK.md`).
- Hapus file hasil batch lama (`data/qwen_results/`, `data/deepseek_results/`).
- Hapus archive `mirai-fix.tar.gz` dan `mirai_deepseek_migration_report.pdf`.

## [2.5.0] - 2026-04-21
### ✨ Added
- **Channel Paksa (Forced Delivery Channel)**: Admin dapat menetapkan satu channel khusus untuk semua laporan Qwen dengan command `/setforcedchannel`.
- **Scheduler Dinamis**: Bot membaca konfigurasi jadwal secara real‑time; perubahan jam atau channel berlaku langsung setelah perintah `/qwen_set_time` atau `/setforcedchannel`.

### 🐛 Fixed
- Menangani `AttributeError` pada command handler ketika channel tidak valid.
- Validasi tambahan untuk ID channel yang tidak ada atau bot tidak memiliki permission.

### 🔄 Changed
- Prioritas pengiriman laporan kini: **Paksa > Channel yang dipilih user > Channel default**
- Menghilangkan emoji di awal respons AI (Gemini & Groq) untuk tampilan lebih kaku dan profesional.

## [2.4.0] - 2026-04-20
### ✨ Added
- **Voice Online Counter**: Fitur penghitung user aktif di channel voice yang mengupdate nama channel setiap 20 menit via `/online_counter_on`.
- **Robust Message Cleanup**: Mekanisme auto‑hapus pesan balasan (cooldown/reply) dengan penanganan error yang aman terhadap `Forbidden` dan `NotFound`.
- **Smart Channel Fallback**: Logika prioritas pengiriman laporan Qwen: (1) Channel khusus user, (2) Channel default global.
- **Config Auto-Repair**: Modul manager otomatis menambahkan modul baru ke file config JSON dengan default `True` saat update versi.

### 🐛 Fixed
- **Graceful Config Failure**: Sistem modul sekarang tetap berjalan (semua aktif) jika file config JSON rusak atau hilang, mencegah bot crash saat startup.
- **Channel Validation**: Memastikan channel fallback yang dipilih masih dalam daftar `enabled_channels` sebelum digunakan.

## [2.3.0] - 2026-04-19
### ✨ Added
- **Custom Auto-Run Scheduler**: Fitur untuk mengatur jam eksekusi batch analisis secara custom via `/qwen_set_time` (format 24 jam).
- **Dedicated Result Channel**: Fitur untuk menentukan channel khusus penerimaan laporan via `/qwen_set_channel` agar hasil tidak menyebar di chat.
- **Dual Format Export**: Laporan batch sekarang digenerate dalam format **PDF** (rapi, siap cetak) dan **TXT** (ringkas, mudah dibaca) sekaligus.
- **Manual Batch Trigger**: Slash command `/qwen_run_now` untuk menjalankan analisis batch secara instan tanpa menunggu jadwal.
- **Thread-Safe RAG**: Implementasi `threading.Lock` pada `utils/rag_utils.py` untuk mencegah race condition saat banyak user berinteraksi.
- **Atomic File Writes**: Mekanisme penulisan file JSON yang aman (write-to-temp-then-move) untuk mencegah korupsi data jika bot crash.
- **TTL Auto-Cleanup**: Sistem pembersihan otomatis profil user yang tidak aktif > 3 hari untuk menghemat storage.

### 🔄 Changed
- **Qwen Batch Logic**: Migrasi dari pengiriman teks panjang di chat menjadi pengiriman file attachment (PDF/TXT) dengan embed ringkasan.
- **Scheduler Robustness**: Perbaikan logika scheduler agar tidak melewatkan waktu eksekusi (menggunakan `timedelta` dan pengecekan tanggal).
- **RAG Performance**: Optimasi fungsi `update_profile` dan `clean_old_profiles` dengan penguncian data yang lebih efisien.
- **Error Handling**: Penambahan validasi channel ID dan penanganan error yang lebih detail pada command Qwen.

### 🐛 Fixed
- **Race Condition**: Memperbaiki potensi data hilang saat dua pesan user diproses bersamaan.
- **Scheduler Miss**: Memperbaiki bug di mana auto-run bisa terlewat jika bot sedang sibuk saat jam target tiba.
- **File Corruption**: Mencegah file `user_profiles.json` rusak akibat penulisan yang terputus mendadak.
- **Channel Validation**: Menambahkan validasi agar command tidak crash jika channel tujuan tidak ditemukan.

## [2.2.0] - 2026-04-18
### ✨ Added
- **Qwen Batch Processor**: Integrasi NVIDIA Qwen API untuk analisis refleksi harian user yang mendalam.
- **PDF Report Generation**: Otomatisasi pembuatan laporan PDF refleksi harian menggunakan library `fpdf2`.
- **Multi-File Attachment Support**: Ekstraksi teks dari PDF, DOCX, XLSX, PPTX, dan TXT.
- **DeepSeek Batch Processor**: Alternatif analisis percakapan menggunakan DeepSeek API.
- **Micro-RAG Integration**: Sistem profiling user jangka panjang di `data/user_profiles.json`.
- **Module Manager Enhancement**: Dukungan modul `qwen` dan `deepseek`.
- **Persistent Chat Storage**: Penyimpanan riwayat percakapan per user.

### 🔄 Changed
- **API Provider Diversifikasi**: Multi-provider (Gemini, Groq, NVIDIA Qwen, DeepSeek) dengan fallback otomatis.
- **Linguistic Style Update**: Gaya bicara semi-informal, partikel natural, teknik *echo*.

## [2.1.0] - 2026-03-15
### Added
- Integrasi awal BMKG API untuk data cuaca.
- Dasar struktur `core/file_reading.py`.

### Changed
- Migrasi dari command prefix ke Slash Commands penuh.

---
*Catatan: Format Changelog mengikuti standar [Keep a Changelog](https://keepachangelog.com/).*