"""
ai/deepseek_client.py
─────────────────────
Async client untuk DeepSeek-V4 via NVIDIA NIM API.
Mendukung dua model:
  - deepseek-ai/deepseek-v4-pro    (1.6T params, 49B active, 1M context)
  - deepseek-ai/deepseek-v4-flash  (versi lebih ringan & cepat)

Endpoint: https://integrate.api.nvidia.com/v1/chat/completions
Auth    : NVIDIA_API_KEY (env var)
Docs    : https://docs.api.nvidia.com/nim/reference/deepseek-ai-deepseek-v4-pro-infer
"""

import os
import re
import random
import json
import aiohttp
import asyncio
from pathlib import Path
from utils.logger import setup_logging

logger = setup_logging()

# ─── Konfigurasi ──────────────────────────────────────────────────────────────
API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
API_KEY = os.getenv("NVIDIA_API_KEY")

# Model identifiers
MODEL_PRO   = "deepseek-ai/deepseek-v4-pro"
MODEL_FLASH = "deepseek-ai/deepseek-v4-flash"

# Default model (bisa diubah via /deepseek model)
_DEFAULT_MODEL = MODEL_PRO

# Path config untuk menyimpan pilihan model
_CONFIG_PATH = Path(__file__).parents[1] / "data" / "deepseek_config.json"

# Thinking modes — dipass lewat extra_body["chat_template_kwargs"]
THINK_MODE_NONE = "non-think"   # cepat, no reasoning
THINK_MODE_HIGH = "think-high"  # analytical reasoning
THINK_MODE_MAX  = "think-max"   # full reasoning (paling lambat, paling akurat)

# ─── Model selection (persistent config) ──────────────────────────────────────
_MODEL_CACHE: str | None = None  # cache agar tidak baca file setiap kali


def get_active_model() -> str:
    """Ambil model yang sedang aktif dari config file."""
    global _MODEL_CACHE
    if _MODEL_CACHE:
        return _MODEL_CACHE
    try:
        if _CONFIG_PATH.exists():
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            model = data.get("model", _DEFAULT_MODEL)
        else:
            model = _DEFAULT_MODEL
    except Exception:
        model = _DEFAULT_MODEL
    _MODEL_CACHE = model
    return model


def set_active_model(model_id: str) -> bool:
    """Set model aktif dan simpan ke config file. Validasi otomatis."""
    global _MODEL_CACHE
    valid = {MODEL_PRO, MODEL_FLASH}
    if model_id not in valid:
        return False
    try:
        data = {}
        if _CONFIG_PATH.exists():
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        data["model"] = model_id
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        _MODEL_CACHE = model_id
        return True
    except Exception as e:
        logger.error("[DeepSeek] Gagal simpan model config: %s", e)
        return False


def get_model_display_name(model_id: str) -> str:
    """Human-readable nama model."""
    names = {
        MODEL_PRO:   "DeepSeek V4 Pro",
        MODEL_FLASH: "DeepSeek V4 Flash",
    }
    return names.get(model_id, model_id)


if not API_KEY:
    logger.warning("[DeepSeek] NVIDIA_API_KEY tidak ditemukan di environment variables!")


def _build_headers() -> dict:
    """Build header saat runtime, bukan saat module load (hindari 'Bearer None')."""
    if not API_KEY:
        raise RuntimeError("[DeepSeek] NVIDIA_API_KEY tidak ditemukan!")
    return {
        "accept":        "application/json",
        "authorization": f"Bearer {API_KEY}",
        "content-type":  "application/json",
    }


# ─── Fungsi utama ─────────────────────────────────────────────────────────────
async def ask_deepseek(
    user_message: str,
    system_prompt: str | None = None,
    think_mode: str = THINK_MODE_MAX,   # default: fast, no reasoning
    max_tokens: int = 8192,
    temperature: float = 0.6,
    top_p: float = 0.95,
    max_retries: int = 3,
    base_delay: float = 2.0,
    timeout_seconds: int = 120,
) -> str:
    """
    Kirim prompt ke DeepSeek-V4-Pro via NVIDIA NIM dengan exponential-backoff retry.

    Args:
        user_message    : Pesan/prompt yang dikirim.
        system_prompt   : Opsional system prompt.
        think_mode      : Mode reasoning — THINK_MODE_NONE / THINK_MODE_HIGH / THINK_MODE_MAX.
        max_tokens      : Maksimal token output.
        temperature     : Sampling temperature (0.0–1.0).
        top_p           : Nucleus sampling.
        max_retries     : Jumlah maksimal percobaan.
        base_delay      : Delay awal sebelum retry (detik).
        timeout_seconds : Timeout per request.

    Returns:
        Teks respons model (str).

    Raises:
        RuntimeError jika semua retry gagal.
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_message})

    active_model = get_active_model()
    payload = {
        "model":       active_model,
        "messages":    messages,
        "max_tokens":  max_tokens,
        "temperature": temperature,
        "top_p":       top_p,
        "stream":      False,
        # DeepSeek-V4 thinking mode — berbeda dari R1 (tidak pakai <think> tags)
        "extra_body": {
            "chat_template_kwargs": {
                "thinking": think_mode,
            }
        },
    }

    timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    API_URL,
                    headers=_build_headers(),
                    json=payload,
                ) as resp:

                    if resp.status == 200:
                        data = await resp.json()
                        choices = data.get("choices")
                        if not choices:
                            raise RuntimeError("[DeepSeek] Response tidak memiliki 'choices'.")

                        msg = choices[0].get("message", {})

                        # DeepSeek-V4-Pro: reasoning ada di field terpisah "reasoning_content"
                        # Content final ada di "content"
                        content = msg.get("content") or ""

                        if not content.strip():
                            # Fallback: coba reasoning_content kalau content kosong
                            content = msg.get("reasoning_content", "")

                        if not content.strip():
                            raise RuntimeError("[DeepSeek] Model mengembalikan konten kosong.")

                        return content.strip()

                    # 429 Rate Limit → jeda lebih panjang
                    if resp.status == 429:
                        retry_after = int(resp.headers.get("Retry-After", base_delay * (2 ** attempt)))
                        logger.warning(
                            "[DeepSeek] Rate limited (429), retry dalam %ds...", retry_after
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    # 5xx → retry
                    if resp.status >= 500 and attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(
                            "[DeepSeek] Server error %s (attempt %d/%d), retry dalam %.1fs...",
                            resp.status, attempt + 1, max_retries, delay,
                        )
                        await asyncio.sleep(delay)
                        continue

                    # 4xx fatal
                    txt = await resp.text()
                    logger.error("[DeepSeek] API error %s: %s", resp.status, txt)
                    raise RuntimeError(f"[DeepSeek] API error {resp.status}: {txt}")

        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "[DeepSeek] Timeout (attempt %d/%d), retry dalam %.1fs...",
                    attempt + 1, max_retries, delay,
                )
                await asyncio.sleep(delay)
                continue
            raise RuntimeError(f"[DeepSeek] Timeout setelah {max_retries} percobaan.")

        except aiohttp.ClientError as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "[DeepSeek] Connection error (attempt %d/%d): %s, retry...",
                    attempt + 1, max_retries, e,
                )
                await asyncio.sleep(delay)
                continue
            raise RuntimeError(f"[DeepSeek] Connection error: {e}")

        except RuntimeError:
            raise

        except Exception as e:
            logger.exception("[DeepSeek] Unexpected error: %s", e)
            raise

    raise RuntimeError(f"[DeepSeek] Gagal mendapatkan respons setelah {max_retries} percobaan.")


# ─── Backward-compat alias ────────────────────────────────────────────────────
ask_qwen = ask_deepseek
