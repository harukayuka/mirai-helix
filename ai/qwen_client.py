import os
import aiohttp
from utils.logger import setup_logging

logger = setup_logging()

API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
API_KEY = os.getenv("NVIDIA_API_KEY")  # set environment variable pada server

if not API_KEY:
    logger.warning("NVIDIA_API_KEY tidak ditemukan di environment variables!")

HEADERS = {
    "accept": "application/json",
    "authorization": f"Bearer {API_KEY}",
    "content-type": "application/json",
}

DEFAULT_PAYLOAD = {
    "model": "qwen/qwen3.5-122b-a10b",
    "max_tokens": 16384,
    "stream": False,
    "temperature": 0.6,
    "top_p": 0.95,
    "top_k": 20,
    "presence_penalty": 0,
}

async def ask_qwen(user_message: str) -> str:
    """Kirim *user_message* ke Qwen dan kembalikan isi balasan."""
    if not API_KEY:
        raise RuntimeError("NVIDIA_API_KEY tidak ditemukan di environment variables!")
    
    payload = DEFAULT_PAYLOAD.copy()
    payload["messages"] = [{"role": "user", "content": user_message}]
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, headers=HEADERS, json=payload) as resp:
                if resp.status != 200:
                    txt = await resp.text()
                    logger.error("Qwen API error %s: %s", resp.status, txt)
                    raise RuntimeError(f"Qwen API error {resp.status}: {txt}")
                
                try:
                    data = await resp.json()
                except aiohttp.ContentTypeError as e:
                    logger.error("Gagal parse JSON response dari Qwen: %s", e)
                    raise RuntimeError(f"Invalid JSON response from Qwen: {e}")
                
                if "choices" not in data or not data["choices"]:
                    logger.error("Response Qwen tidak mengandung choices: %s", data)
                    raise RuntimeError("Invalid response format from Qwen API")
                
                return data["choices"][0]["message"]["content"]
    except aiohttp.ClientError as e:
        logger.error("Koneksi ke Qwen API gagal: %s", e)
        raise RuntimeError(f"Qwen API connection error: {e}")
    except Exception as e:
        logger.exception("Error tak terduga saat memanggil Qwen API: %s", e)
        raise
