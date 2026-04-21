import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.gemini import GeminiClient
from memory import get_history

gemini_client = GeminiClient()

async def generate_bedtime_message():
    prompt = "Buat pesan pengingat tidur yang singkat, ramah, dan memotivasi untuk istirahat yang cukup. Jangan terlalu formal dan hindari tag atau mention user. Contoh: 'Sudah waktunya tidur, ya! Jangan lupa istirahat yang cukup untuk kesehatanmu. Selamat malam! ✨'"
    
    # Use a fresh history for this specific prompt to avoid context pollution
    # Or, if a specific context is desired, it should be passed here.
    # For a simple bedtime reminder, a direct prompt is sufficient.
    
    try:
        # Generate response using Gemini
        response = await asyncio.to_thread(gemini_client.generate, [{'role': 'user', 'parts': [prompt]}])
        return response
    except Exception as e:
        print(f"[Gemini Bedtime] Error generating message: {e}")
        return "Sudah waktunya tidur, ya! Jangan lupa istirahat yang cukup untuk kesehatanmu. Selamat malam! ✨" #istirahat" # Fallback message
