# core/groq_client.py - Klien Groq API untuk Fallback
"""
GroqClient untuk komunikasi dengan Groq API (Llama 3).
Digunakan sebagai cadangan jika Gemini API mengalami error 400/500.
"""
import os
import aiohttp
from typing import List, Dict
from dotenv import load_dotenv
from utils.logger import setup_logging

load_dotenv()
logger = setup_logging()

class GroqClient:
    """Client khusus untuk Groq API (Llama 3)."""
    
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            logger.warning("[GroqClient] GROQ_API_KEY tidak ditemukan di environment variables.")
            # Tidak raise error agar bot tetap bisa jalan, hanya fitur fallback yang mati
            self.enabled = False
        else:
            self.enabled = True
            self.base_url = "https://api.groq.com/openai/v1/chat/completions"
            # Menggunakan Llama 3.1 70B untuk keseimbangan kecepatan dan kualitas
            self.model = "llama3-70b-8192"
        
        # System prompt yang sama agar gaya bicara konsisten
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Load system prompt yang sama dengan Gemini untuk konsistensi."""
        from pathlib import Path
        prompt_path = Path(__file__).parent.parent / "ai" / "prompts" / "mirai_system_prompt.txt"
        if prompt_path.exists():
            try:
                return prompt_path.read_text(encoding="utf-8").strip()
            except Exception as e:
                logger.error(f"[GroqClient] Gagal baca prompt: {e}")
        return "Kamu adalah Mirai, asisten yang ramah dan helpful."

    async def generate_completion(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """
        Mengirim request ke Groq dengan pola payload standar.
        Mirip dengan struktur yang digunakan di micro_rag untuk konsistensi data.
        """
        if not self.enabled:
            raise RuntimeError("GroqClient tidak aktif (API Key missing).")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Tambahkan system prompt jika pesan pertama bukan system
        final_messages = messages
        if not messages or messages[0].get("role") != "system":
            final_messages = [{"role": "system", "content": self.system_prompt}] + messages

        # Pola payload distandarisasi
        payload = {
            "model": self.model,
            "messages": final_messages,
            "temperature": temperature,
            "max_tokens": 1024,
            "top_p": 1,
            "stream": False
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, json=payload, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[GroqClient] API Error {response.status}: {error_text}")
                    # Raise error spesifik agar handler tahu ini error server/client
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"Groq API Error: {error_text}"
                    )
                
                data = await response.json()
                if not data.get("choices"):
                    raise RuntimeError("Groq API returned no choices.")
                    
                return data['choices'][0]['message']['content']
