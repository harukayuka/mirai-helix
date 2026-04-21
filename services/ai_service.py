import asyncio
from ai.gemini import GeminiClient
from memory import add_message, get_history

class AIService:
    def __init__(self):
        self.gemini = GeminiClient()

    async def generate_reply(self, history) -> str:
        """Generate AI reply given history."""
        reply = await asyncio.to_thread(self.gemini.generate, history)
        return reply

    def add_to_history(self, role, content):
        add_message(role, content)

    def get_history(self):
        return get_history()
