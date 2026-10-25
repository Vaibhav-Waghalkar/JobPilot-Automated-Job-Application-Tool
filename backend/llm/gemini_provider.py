import httpx
from typing import Optional
from backend.llm.base import LLMProvider, LLMResponse

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-3.5-flash-lite"):
        self.api_key = api_key
        self.model = model
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.2) -> LLMResponse:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured")

        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"SYSTEM INSTRUCTIONS:\n{system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will strictly follow these instructions."}]})

        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 2048,
            }
        }

        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self.endpoint, json=payload, headers=headers)
            if resp.status_code == 429:
                raise RuntimeError("GEMINI_RATE_LIMITED")
            resp.raise_for_status()
            data = resp.json()
            try:
                candidate = data["candidates"][0]
                text = candidate["content"]["parts"][0]["text"]
                return LLMResponse(text=text, provider="gemini", model=self.model, raw_response=data)
            except (KeyError, IndexError) as e:
                raise RuntimeError(f"Unexpected Gemini response structure: {e}")
