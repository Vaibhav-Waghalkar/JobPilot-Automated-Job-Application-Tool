from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    raw_response: Optional[Dict[str, Any]] = None

class LLMProvider:
    """Base class for LLM providers."""
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.2) -> LLMResponse:
        raise NotImplementedError
