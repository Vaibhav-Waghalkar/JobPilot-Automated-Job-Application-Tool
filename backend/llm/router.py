import logging
from typing import Optional
from backend.config import settings
from backend.llm.base import LLMResponse
from backend.llm.gemini_provider import GeminiProvider
from backend.llm.groq_provider import GroqProvider
from backend.llm.ollama_provider import OllamaProvider

logger = logging.getLogger("jobpilot.llm_router")

class MockFallbackProvider:
    """Deterministic fallback for tests or when no external API keys are configured."""
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.2) -> LLMResponse:
        return LLMResponse(
            text="[UNKNOWN] No API keys configured or all providers rate limited.",
            provider="mock_fallback",
            model="deterministic-fallback"
        )

class LLMRouter:
    """
    Automatic fallback router:
    1. Gemini (primary for reasoning/long context)
    2. Groq (fast fallback)
    3. Ollama (offline local)
    4. Mock/Safe deterministic fallback
    """
    def __init__(self):
        self.gemini = GeminiProvider(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL) if settings.GEMINI_API_KEY else None
        self.groq = GroqProvider(api_key=settings.GROQ_API_KEY, model=settings.GROQ_MODEL) if settings.GROQ_API_KEY else None
        self.ollama = OllamaProvider(base_url=settings.OLLAMA_BASE_URL, model=settings.OLLAMA_MODEL)
        self.mock_fallback = MockFallbackProvider()

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.2) -> LLMResponse:
        # Try Gemini
        if self.gemini:
            try:
                return await self.gemini.generate(prompt, system_prompt, temperature)
            except Exception as e:
                logger.warning(f"Gemini provider failed/rate-limited: {e}. Falling back to Groq...")

        # Try Groq
        if self.groq:
            try:
                return await self.groq.generate(prompt, system_prompt, temperature)
            except Exception as e:
                logger.warning(f"Groq provider failed/rate-limited: {e}. Falling back to Ollama...")

        # Try Ollama
        try:
            return await self.ollama.generate(prompt, system_prompt, temperature)
        except Exception as e:
            logger.warning(f"Ollama local provider unavailable: {e}. Using deterministic fallback.")

        return await self.mock_fallback.generate(prompt, system_prompt, temperature)

llm_router = LLMRouter()
