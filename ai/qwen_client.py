import os
import random
import aiohttp
import asyncio
from utils.logger import setup_logging

logger = setup_logging()

API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
API_KEY = os.getenv("NVIDIA_API_KEY")

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
    """Call Qwen API with exponential backoff retry."""
    if not API_KEY:
        raise RuntimeError("NVIDIA_API_KEY tidak ditemukan!")
    
    payload = DEFAULT_PAYLOAD.copy()
    payload["messages"] = [{"role": "user", "content": user_message}]
    
    max_retries = 3
    base_delay = 1.0
    timeout = aiohttp.ClientTimeout(total=30)
    
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(API_URL, headers=HEADERS, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if "choices" not in data or not data["choices"]:
                            raise RuntimeError("Invalid response format")
                        return data["choices"][0]["message"]["content"]
                    elif resp.status >= 500 and attempt < max_retries - 1:
                        txt = await resp.text()
                        logger.warning(
                            f"Qwen API error {resp.status} (attempt {attempt + 1}/{max_retries}), retrying..."
                        )
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                        await asyncio.sleep(delay)
                        continue
                    else:
                        txt = await resp.text()
                        logger.error(f"Qwen API error {resp.status}: {txt}")
                        raise RuntimeError(f"Qwen API error {resp.status}: {txt}")
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                logger.warning(f"Qwen API timeout (attempt {attempt + 1}/{max_retries}), retrying...")
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
                continue
            raise RuntimeError("Qwen API timeout after 3 attempts")
        except aiohttp.ClientError as e:
            if attempt < max_retries - 1:
                logger.warning(
                    f"Qwen API connection error (attempt {attempt + 1}/{max_retries}): {e}, retrying..."
                )
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
                continue
            raise RuntimeError(f"Qwen API connection error: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error calling Qwen: {e}")
            raise
    raise RuntimeError("Failed to get response from Qwen API")

