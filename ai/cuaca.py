# ai/cuaca.py - Integrasi API BMKG untuk Mirai
"""
Modul untuk mengambil data cuaca dari API Terbuka BMKG.
Mendukung pencarian cuaca berdasarkan nama lokasi menggunakan database
wilayah Indonesia (cahyadsn/wilayah) via aiosqlite.

FIXED:
- Ganti Emsifa REST API → lokal SQLite wilayah.db (aiosqlite, non-blocking)
- Hapus logging.basicConfig() — gunakan setup_logging() dari utils
- Tambah _ensure_wilayah_db() untuk setup DB otomatis dari wilayah.sql
- search_location_code() kini query SQLite secara async (LIKE fuzzy search)
"""

import aiohttp
import aiosqlite
import asyncio
import re
import os
from typing import Any, Dict, Optional
from pathlib import Path

from utils.logger import setup_logging

logger = setup_logging()

# ---------------------------------------------------------------------------
# Konstanta
# ---------------------------------------------------------------------------
BMKG_API_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca"

# URL SQL dump wilayah (cahyadsn/wilayah di GitHub)
WILAYAH_SQL_URL = (
    "https://github.com/cahyadsn/wilayah/raw/refs/heads/master/db/wilayah.sql"
)

# Lokasi file DB (relatif ke root project)
_DATA_DIR  = Path(__file__).parent.parent / "data"
DB_PATH    = _DATA_DIR / "wilayah.db"
SQL_PATH   = _DATA_DIR / "wilayah.sql"

# Default kode adm4 (Kemayoran, Jakarta Pusat) — fallback jika lokasi tak ditemukan
DEFAULT_ADM4 = "31.71.03.1001"

# Kode panjang di wilayah DB: "31.71.03.1001" = 4 level (desa/kelurahan)
_ADM4_LEVELS = 4

# Fallback statis untuk kota‑kota populer (dipakai jika DB belum tersedia)
_CITY_FALLBACK: Dict[str, str] = {
    "JAKARTA"    : "31.71.03.1001",
    "BANDUNG"    : "32.73.01.1001",
    "SURABAYA"   : "35.78.01.1001",
    "MEDAN"      : "12.71.01.1001",
    "MAKASSAR"   : "73.71.01.1001",
    "YOGYAKARTA" : "34.71.01.1001",
    "BEKASI"     : "32.75.01.1001",
    "TANGERANG"  : "36.71.01.1001",
    "DEPOK"      : "32.76.01.1001",
    "BOGOR"      : "32.71.01.1001",
    "SEMARANG"   : "33.74.01.1001",
    "PALEMBANG"  : "16.71.01.1001",
    "BALIKPAPAN" : "64.71.01.1001",
    "DENPASAR"   : "51.71.01.1001",
    "PADANG"     : "13.71.01.1001",
    "MANADO"     : "71.71.01.1001",
}

# ---------------------------------------------------------------------------
# Setup database wilayah (download sekali, simpan lokal)
# ---------------------------------------------------------------------------

async def _download_wilayah_sql() -> bool:
    """Download wilayah.sql dari GitHub ke data/wilayah.sql."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    timeout = aiohttp.ClientTimeout(total=60)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(WILAYAH_SQL_URL) as resp:
                if resp.status != 200:
                    logger.error(f"[Cuaca] Gagal download wilayah.sql: HTTP {resp.status}")
                    return False
                content = await resp.read()
                SQL_PATH.write_bytes(content)
                logger.info(f"[Cuaca] wilayah.sql berhasil diunduh ({len(content):,} bytes)")
                return True
    except Exception as e:
        logger.error(f"[Cuaca] Error download wilayah.sql: {e}")
        return False


async def _import_sql_to_db() -> bool:
    """
    Parse wilayah.sql dan import ke wilayah.db via aiosqlite.

    Tabel target:
        wilayah(kode TEXT PRIMARY KEY, nama TEXT NOT NULL)
    """
    if not SQL_PATH.exists():
        logger.error("[Cuaca] wilayah.sql tidak ditemukan, tidak bisa import.")
        return False

    sql_text = SQL_PATH.read_text(encoding="utf-8", errors="replace")

    # Ekstrak baris INSERT VALUES dari SQL dump
    # Format: INSERT INTO `wilayah` VALUES ('kode','nama');
    # atau multi‑row: INSERT INTO `wilayah` VALUES (...),(...),...;
    pattern = re.compile(
        r"INSERT\s+INTO\s+`?wilayah`?\s+VALUES\s*(.*?);",
        re.IGNORECASE | re.DOTALL,
    )
    row_pat = re.compile(r"\('([^']+)',\s*'([^']*)'\)")

    rows: list[tuple[str, str]] = []
    for match in pattern.finditer(sql_text):
        for row in row_pat.finditer(match.group(1)):
            rows.append((row.group(1), row.group(2)))

    if not rows:
        logger.error("[Cuaca] Tidak ada baris ditemukan di wilayah.sql.")
        return False

    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS wilayah "
                "(kode TEXT PRIMARY KEY, nama TEXT NOT NULL)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_nama ON wilayah(nama)"
            )
            await db.executemany(
                "INSERT OR REPLACE INTO wilayah(kode, nama) VALUES (?, ?)", rows
            )
            await db.commit()
        logger.info(f"[Cuaca] Import selesai: {len(rows):,} baris ke wilayah.db")
        return True
    except Exception as e:
        logger.error(f"[Cuaca] Error import ke DB: {e}")
        DB_PATH.unlink(missing_ok=True)
        return False


async def ensure_wilayah_db() -> bool:
    """
    Pastikan wilayah.db tersedia dan terisi.
    Download + import otomatis jika belum ada.
    Dipanggil sekali saat startup atau saat pertama kali dibutuhkan.
    """
    if DB_PATH.exists() and DB_PATH.stat().st_size > 0:
        return True

    logger.info("[Cuaca] wilayah.db belum ada, memulai setup...")

    if not SQL_PATH.exists():
        ok = await _download_wilayah_sql()
        if not ok:
            return False

    return await _import_sql_to_db()


# ---------------------------------------------------------------------------
# Pencarian wilayah via aiosqlite
# ---------------------------------------------------------------------------

def _count_dots(kode: str) -> int:
    """Hitung level hirarki berdasarkan jumlah titik di kode."""
    return kode.count(".")


async def _search_db(query: str) -> Optional[str]:
    """
    Cari kode adm4 (desa/kelurahan, 3 titik) di wilayah.db berdasarkan nama.

    Strategi:
    1. Exact match (case-insensitive) → prioritas tertinggi
    2. LIKE '%query%' → ambil yang paling spesifik (level tertinggi)

    Mengembalikan kode adm4 (4-level) atau None jika tidak ditemukan.
    """
    if not DB_PATH.exists():
        return None

    q_upper = query.upper()

    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row

            # 1) Exact match di level desa (3 titik = adm4)
            async with db.execute(
                "SELECT kode FROM wilayah "
                "WHERE UPPER(nama) = ? AND LENGTH(kode) - LENGTH(REPLACE(kode,'.','')) = 3 "
                "LIMIT 1",
                (q_upper,),
            ) as cur:
                row = await cur.fetchone()
                if row:
                    return row["kode"]

            # 2) Fuzzy LIKE di semua level → pilih yang paling dalam (adm4 dulu)
            async with db.execute(
                "SELECT kode, nama FROM wilayah "
                "WHERE UPPER(nama) LIKE ? "
                "ORDER BY LENGTH(kode) DESC "
                "LIMIT 20",
                (f"%{q_upper}%",),
            ) as cur:
                rows = await cur.fetchall()

            if not rows:
                return None

            # Pilih yang paling spesifik (kode terpanjang = level terendah)
            # Prioritaskan adm4 (3 titik), lalu adm3 (2 titik), dst.
            best = max(rows, key=lambda r: _count_dots(r["kode"]))
            kode = best["kode"]

            # Jika hanya sampai adm3 (kecamatan), cari satu desa di bawahnya
            if _count_dots(kode) == 2:
                async with db.execute(
                    "SELECT kode FROM wilayah "
                    "WHERE kode LIKE ? AND LENGTH(kode) - LENGTH(REPLACE(kode,'.','')) = 3 "
                    "LIMIT 1",
                    (f"{kode}.%",),
                ) as cur:
                    child = await cur.fetchone()
                    if child:
                        kode = child["kode"]

            return kode if _count_dots(kode) >= 2 else None

    except Exception as e:
        logger.error(f"[Cuaca] Error query wilayah.db: {e}")
        return None


# ---------------------------------------------------------------------------
# BMKGClient
# ---------------------------------------------------------------------------

class BMKGClient:
    """Klien async untuk mengambil data cuaca dari API BMKG."""

    def __init__(self):
        self._db_ready: Optional[bool] = None   # None = belum dicek

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_db(self) -> bool:
        """Pastikan wilayah.db siap (lazy init)."""
        if self._db_ready is None:
            self._db_ready = await ensure_wilayah_db()
        return self._db_ready

    async def _get_json(self, url: str, **kwargs) -> Optional[Dict]:
        """GET JSON via aiohttp dengan timeout."""
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, **kwargs) as resp:
                    if resp.status != 200:
                        logger.error(f"[BMKG] HTTP {resp.status} untuk {url}")
                        return None
                    return await resp.json()
        except asyncio.TimeoutError:
            logger.error(f"[BMKG] Timeout saat akses {url}")
            return None
        except Exception as e:
            logger.error(f"[BMKG] Error GET {url}: {e}")
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search_location_code(self, query: str) -> Optional[str]:
        """
        Mencari kode adm4 BMKG berdasarkan nama lokasi.

        Urutan prioritas:
        1. Fallback statis (_CITY_FALLBACK) untuk kota populer → cepat
        2. Query ke wilayah.db via aiosqlite → akurat & lengkap
        3. DEFAULT_ADM4 (Jakarta Pusat) jika semua gagal
        """
        if not query:
            return DEFAULT_ADM4

        q_upper = query.strip().upper()

        # 1) Cek fallback statis dulu (O(n) tapi n kecil)
        for city, code in _CITY_FALLBACK.items():
            if city in q_upper:
                logger.debug(f"[Cuaca] Fallback statis: {city} → {code}")
                return code

        # 2) Query DB
        await self._ensure_db()
        if self._db_ready:
            code = await _search_db(q_upper)
            if code:
                logger.info(f"[Cuaca] DB match: '{query}' → {code}")
                return code

        # 3) Default
        logger.warning(f"[Cuaca] Lokasi '{query}' tidak ditemukan, pakai default.")
        return DEFAULT_ADM4

    async def get_weather_raw(self, adm4: str = DEFAULT_ADM4) -> Optional[Dict[str, Any]]:
        """Mengambil data mentah prakiraan cuaca dari BMKG."""
        data = await self._get_json(BMKG_API_URL, params={"adm4": adm4})
        if not data or "data" not in data or not data["data"]:
            return None

        location_info = data.get("lokasi", {})
        weather_list  = data["data"][0].get("cuaca", [])
        if not weather_list:
            return None

        # Ambil 3 slot prakiraan terdekat (tiap slot = list, ambil elemen pertama)
        forecasts: list = []
        for slot in weather_list[:3]:
            if isinstance(slot, list) and slot:
                forecasts.append(slot[0])
            elif isinstance(slot, dict):
                forecasts.append(slot)

        if not forecasts:
            return None

        return {
            "lokasi": {
                "desa"      : location_info.get("desa"),
                "kecamatan" : location_info.get("kecamatan"),
                "kotkab"    : location_info.get("kotkab"),
                "provinsi"  : location_info.get("provinsi"),
            },
            "prakiraan": forecasts,
            "sumber"   : "BMKG",
        }

    def extract_location_from_text(self, text: str) -> Optional[str]:
        """Ekstrak nama lokasi dari teks natural language."""
        patterns = [
            r"cuaca\s+(?:di|ke|daerah|wilayah)\s+([a-zA-Z\s]+?)(?:\s+(?:hari ini|besok|gimana|dong|yuk))?$",
            r"bagaimana\s+cuaca\s+(?:di\s+)?([a-zA-Z\s]+?)(?:\s+(?:hari ini|besok))?$",
            r"cek\s+cuaca\s+(?:di\s+)?([a-zA-Z\s]+)",
            r"prakiraan\s+cuaca\s+(?:di\s+)?([a-zA-Z\s]+)",
            r"cuaca\s+([a-zA-Z\s]+?)\s+(?:hari ini|besok|gimana)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    async def _main():
        client = BMKGClient()
        queries = [
            "Gimana cuaca di Bandung hari ini?",
            "cuaca di Kemayoran",
            "cek cuaca Surabaya",
        ]
        for q in queries:
            loc = client.extract_location_from_text(q)
            print(f"\nQuery   : {q}")
            print(f"Lokasi  : {loc}")
            if loc:
                code = await client.search_location_code(loc)
                print(f"Kode ADM: {code}")
                raw = await client.get_weather_raw(code)
                print(f"Lokasi  : {raw['lokasi'] if raw else 'None'}")

    asyncio.run(_main())
