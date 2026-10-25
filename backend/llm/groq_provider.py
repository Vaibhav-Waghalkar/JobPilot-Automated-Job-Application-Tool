import httpx
from typing import Optional
from backend.llm.base import LLMProvider, LLMResponse

class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "openai/gpt-oss-20b"):
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.2) -> LLMResponse:
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not configured")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2048,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self.endpoint, json=payload, headers=headers)
            if resp.status_code == 429:
                raise RuntimeError("GROQ_RATE_LIMITED")
            resp.raise_for_status()
            data = resp.json()
            try:
                text = data["choices"][0]["message"]["content"]
                return LLMResponse(text=text, provider="groq", model=self.model, raw_response=data)
            except (KeyError, IndexError) as e:
                raise RuntimeError(f"Unexpected Groq response structure: {e}")
