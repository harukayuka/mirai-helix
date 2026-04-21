# core/llm_handler.py - Manajer Utama LLM dengan Fallback
"""
LLMHandler: Mengatur request AI dengan mekanisme fallback otomatis.
1. Utama: Google Gemini (via ai/gemini.py)
2. Fallback: Groq (Llama 3) jika Gemini error 400/500.
"""
import os
import time
import aiohttp
from typing import List, Dict, Optional
from dotenv import load_dotenv
from utils.logger import setup_logging

# Import client Groq
from core.groq_client import GroqClient

load_dotenv()
logger = setup_logging()

class LLMHandler:
    """
    Manajer utama untuk menangani request AI dengan mekanisme fallback.
    Menggabungkan GeminiClient (existing) dan GroqClient (new).
    """
    
    def __init__(self, gemini_client):
        """
        Args:
            gemini_client: Instance dari GeminiClient (dari ai.gemini)
        """
        self.gemini_client = gemini_client
        self.groq_client = GroqClient()
        
    def _prepare_messages(self, history: List[Dict], user_context: str = "") -> List[Dict]:
        """
        Mengonversi history format Gemini ke format list of dict standar 
        yang bisa dimengerti Groq (dan provider lain).
        Format: [{"role": "user|assistant|system", "content": "..."}]
        """
        messages = []
        
        # Tambahkan context user jika ada (dari Micro-RAG)
        if user_context:
            messages.append({"role": "system", "content": user_context})
            
        for msg in history:
            role = msg.get("role", "")
            if role not in ["user", "model", "assistant"]:
                continue
                
            # Normalisasi role
            if role == "model":
                role = "assistant"
                
            # Ekstrak teks
            text = ""
            if "parts" in msg and isinstance(msg["parts"], list) and msg["parts"]:
                part = msg["parts"][0]
                if isinstance(part, dict):
                    text = part.get("text", "")
                else:
                    text = str(part)
            elif "content" in msg:
                text = msg["content"]
                
            if text.strip():
                messages.append({"role": role, "content": text.strip()})
                
        return messages

    async def get_response(self, history: List[Dict], temperature: float = 0.7, user_context: str = "") -> str:
        """
        Logika utama:
        1. Coba Google Gemini.
        2. Jika error 400 (Bad Request) atau 500 (Internal Server Error), fallback ke Groq.
        
        Args:
            history: Riwayat chat format Gemini
            temperature: Suhu kreativitas
            user_context: Context tambahan dari Micro-RAG
            
        Returns:
            str: Respons AI
        """
        last_error = None
        
        # --- TAHAP 1: COBA GEMINI (Utama) ---
        try:
            logger.info("[LLMHandler] Mencoba request ke Google Gemini...")
            # Panggil method generate dari GeminiClient yang sudah ada
            # Kita perlu membungkus call synchronous ini jika blocking, 
            # tapi karena gemini.py menggunakan requests (blocking), kita biarkan sync di dalam async context
            # atau gunakan to_thread jika perlu. Di sini kita panggil langsung sesuai pola main.py
            import asyncio
            # Jalankan di thread pool agar tidak blocking event loop
            response = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: self.gemini_client.generate(history, temperature=temperature, user_context=user_context)
            )
            
            # Cek apakah respons adalah error string (fallback manual jika Gemini return string error tertentu)
            if response and "⚠️" in response and "API key" in response:
                 raise RuntimeError("Gemini returned API key error indicator.")
            
            return response
            
        except aiohttp.ClientResponseError as e:
            # Tangkap error HTTP spesifik jika ada (meski gemini.py pakai requests, jadi jarang terjadi di sini)
            logger.warning(f"[LLMHandler] Gemini HTTP Error: {e.status}")
            if e.status in [400, 500]:
                logger.warning("⚠️ Gemini error 400/500. Mengaktifkan fallback ke Groq...")
                last_error = e
            else:
                # Error lain (401, 403) langsung dilempar
                raise e
        except Exception as e:
            # Tangkap error umum dari Gemini (timeout, network, dll)
            error_msg = str(e).lower()
            # Cek apakah ini error yang layak di-fallback (server error, timeout, dll)
            # Kita fallback jika errornya terlihat seperti server issue (500) atau bad request (400)
            # Karena gemini.py menggunakan 'requests', error biasanya Exception biasa.
            # Kita asumsikan jika sampai catch di sini, itu adalah error yang bisa dicoba di fallback
            logger.warning(f"[LLMHandler] Gemini gagal karena exception: {str(e)}. Mencoba fallback...")
            last_error = e

        # --- TAHAP 2: FALLBACK KE GROQ ---
        if last_error:
            if not self.groq_client.enabled:
                logger.error("[LLMHandler] GroqClient tidak aktif. Tidak bisa fallback.")
                raise RuntimeError("Fallback gagal: GroqClient tidak aktif.")
                
            try:
                logger.info("🔄 Menggunakan Groq (Llama 3) sebagai cadangan...")
                
                # Konversi history ke format standar
                messages = self._prepare_messages(history, user_context)
                
                # Panggil Groq
                response = await self.groq_client.generate_completion(messages, temperature=temperature)
                logger.info("[LLMHandler] Berhasil mendapatkan respons dari Groq.")
                return response
                
            except Exception as groq_err:
                # Jika Groq juga gagal, lempar error gabungan
                logger.error(f"[LLMHandler] Groq juga gagal: {str(groq_err)}")
                raise RuntimeError(f"Gagal mendapatkan respons AI. Gemini: {last_error}, Groq: {groq_err}")
        
        return ""
