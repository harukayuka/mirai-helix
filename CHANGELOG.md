# Changelog - Mirai Helix

### Changelog - Mirai Helix

## [2.5.0] - 2026-04-21
### ✨ Added
- **Channel Paksa (Forced Delivery Channel)**: Admin dapat menetapkan satu channel khusus untuk semua laporan Qwen dengan command `/setforcedchannel`.  
- **Scheduler Dinamis**: Bot membaca konfigurasi jadwal secara real‑time; perubahan jam atau channel berlaku langsung setelah perintah `/qwen_set_time` atau `/setforcedchannel`.

### 🐛 Fixed
- Menangani `AttributeError` pada command handler ketika channel tidak valid.  
- Validasi tambahan untuk ID channel yang tidak ada atau bot tidak memiliki permission.

### 🔄 Changed
- Prioritas pengiriman laporan kini: **Paksa > Channel yang dipilih user > Channel default**
- Menghilangkan emoji di awal respons AI (Gemini & Groq) untuk tampilan lebih kaku dan profesional.

## [2.4.0] - 2026-04-20
### ✨ Added
- **Voice Online Counter**: Fitur penghitung user aktif di channel voice yang mengupdate nama channel setiap 20 menit via `/online_counter_on`.  
- **Robust Message Cleanup**: Mekanisme auto‑hapus pesan balasan (cooldown/reply) dengan penanganan error yang aman terhadap `Forbidden` dan `NotFound`.  
- **Smart Channel Fallback**: Logika prioritas pengiriman laporan Qwen: (1) Channel khusus user, (2) Channel default global.

<!-- ... entri sebelumnya tetap tidak berubah ... --> [2.5.0] - 2026-04-21
### ✨ Added
- **Channel Paksa (Forced Delivery Channel)**: Admin dapat menetapkan satu channel khusus untuk semua laporan Qwen dengan command `/setforcedchannel`.
- **Scheduler Dinamis**: Bot membaca konfigurasi jadwal secara real‑time; perubahan jam atau channel berlaku langsung setelah perintah `/qwen_set_time` atau `/setforcedchannel`.

### 🐛 Fixed
- Menangani `AttributeError` pada command handler ketika channel tidak valid.
- Validasi tambahan untuk ID channel yang tidak ada atau bot tidak memiliki permission.

### 🔄 Changed
- Prioritas pengiriman laporan kini: Paksa > Channel yang dipilih user > Channel default.

Semua perubahan signifikan pada proyek ini akan didokumentasikan di file ini.

## [2.4.0] - 2026-04-20
### ✨ Added
- **Voice Online Counter**: Fitur penghitung user aktif di channel voice yang mengupdate nama channel setiap 20 menit via `/online_counter_on`.
- **Robust Message Cleanup**: Mekanisme auto-hapus pesan balasan (cooldown/reply) dengan penanganan error yang aman terhadap `Forbidden` dan `NotFound`.
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
- **Qwen Batch Processor**: Integrasi NVIDIA Qwen API (`qwen/qwen3.5-122b-a10b`) untuk analisis refleksi harian user yang mendalam.
- **PDF Report Generation**: Otomatisasi pembuatan laporan PDF refleksi harian menggunakan library `fpdf2` dengan header dan footer kustom.
- **Multi-File Attachment Support**: Ekstensi pada `core/file_reading.py` untuk ekstraksi teks dari format PDF, DOCX, XLSX, PPTX, dan TXT.
- **DeepSeek Batch Processor**: Alternatif analisis percakapan menggunakan DeepSeek API untuk diversifikasi provider.
- **Micro-RAG Integration**: Sistem profiling user jangka panjang yang menyimpan data kepribadian, minat, dan mood di `data/user_profiles.json`.
- **Module Manager Enhancement**: Dukungan modul `qwen` dan `deepseek` untuk kontrol aktif/nonaktif dinamis via slash command.
- **RPM Rate Limiting**: Mekanisme pembatasan request per menit (40 RPM) untuk mencegah throttling API provider.
- **Persistent Chat Storage**: Penyimpanan riwayat percakapan per user di direktori `data/user_chats/` dengan format terstruktur (JSON).
### 🔄 Changed
- **API Provider Diversifikasi**: Meningkatkan fleksibilitas sistem dengan dukungan multi-provider (Google Gemini, Groq, NVIDIA Qwen, DeepSeek) dan mekanisme fallback otomatis.
- **Linguistic Style Update**: Penyesuaian prompt sistem (`ai/prompts/mirai_system_prompt.txt`) untuk gaya bicara semi-informal, penggunaan partikel natural, dan teknik *echo* agar lebih manusiawi.
### 🐛 Fixed
- Perbaikan error pada ekstraksi teks PDF untuk dokumen dengan layout kompleks.
- Stabilisasi koneksi API saat rate limit tercapai.

## [2.1.0] - 2026-03-15
### Added
- Integrasi awal BMKG API untuk data cuaca.
- Dasar struktur `core/file_reading.py`.
### Changed
- Migrasi dari command prefix ke Slash Commands penuh.

---
*Catatan: Format Changelog mengikuti standar [Keep a Changelog](https://keepachangelog.com/).*

