import httpx
from typing import Optional
from backend.llm.base import LLMProvider, LLMResponse

class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen2.5:7b-instruct"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.endpoint = f"{self.base_url}/api/generate"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.2) -> LLMResponse:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self.endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return LLMResponse(
                text=data.get("response", ""),
                provider="ollama",
                model=self.model,
                raw_response=data
            )
