import asyncio
import logging
from fastapi import APIRouter
from backend.config import settings
from backend.llm.gemini_provider import GeminiProvider
from backend.llm.groq_provider import GroqProvider
from backend.llm.ollama_provider import OllamaProvider

router = APIRouter(prefix="/api/llm", tags=["LLM Health & Providers"])
logger = logging.getLogger("jobpilot.llm_api")

def mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return "Not Configured" if not key else "****"
    return f"{key[:4]}...{key[-4:]}"

@router.get("/health")
async def check_llm_health():
    """
    Checks health of Gemini, Groq, and Ollama providers with tiny test prompts.
    Masks all API keys in response.
    """
    results = {}

    # 1. Gemini
    if settings.GEMINI_API_KEY:
        try:
            gemini = GeminiProvider(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)
            # 10s timeout on test prompt
            resp = await asyncio.wait_for(gemini.generate("Say OK"), timeout=15.0)
            results["gemini"] = {
                "status": "OK",
                "model": settings.GEMINI_MODEL,
                "masked_key": mask_key(settings.GEMINI_API_KEY),
                "response": resp.text.strip().replace("\n", " ")[:60],
                "error": None
            }
        except Exception as e:
            results["gemini"] = {
                "status": "FAILED",
                "model": settings.GEMINI_MODEL,
                "masked_key": mask_key(settings.GEMINI_API_KEY),
                "response": None,
                "error": str(e)
            }
    else:
        results["gemini"] = {
            "status": "NOT_CONFIGURED",
            "model": settings.GEMINI_MODEL,
            "masked_key": "None",
            "response": None,
            "error": "GEMINI_API_KEY is not set in .env"
        }

    # 2. Groq
    if settings.GROQ_API_KEY:
        try:
            groq = GroqProvider(api_key=settings.GROQ_API_KEY, model=settings.GROQ_MODEL)
            resp = await asyncio.wait_for(groq.generate("Say OK"), timeout=15.0)
            results["groq"] = {
                "status": "OK",
                "model": settings.GROQ_MODEL,
                "masked_key": mask_key(settings.GROQ_API_KEY),
                "response": resp.text.strip().replace("\n", " ")[:60],
                "error": None
            }
        except Exception as e:
            results["groq"] = {
                "status": "FAILED",
                "model": settings.GROQ_MODEL,
                "masked_key": mask_key(settings.GROQ_API_KEY),
                "response": None,
                "error": str(e)
            }
    else:
        results["groq"] = {
            "status": "NOT_CONFIGURED",
            "model": settings.GROQ_MODEL,
            "masked_key": "None",
            "response": None,
            "error": "GROQ_API_KEY is not set in .env"
        }

    # 3. Ollama
    try:
        ollama = OllamaProvider(base_url=settings.OLLAMA_BASE_URL, model=settings.OLLAMA_MODEL)
        resp = await asyncio.wait_for(ollama.generate("Say OK"), timeout=20.0)
        results["ollama"] = {
            "status": "OK",
            "model": settings.OLLAMA_MODEL,
            "base_url": settings.OLLAMA_BASE_URL,
            "response": resp.text.strip().replace("\n", " ")[:60],
            "error": None
        }
    except Exception as e:
        results["ollama"] = {
            "status": "FAILED",
            "model": settings.OLLAMA_MODEL,
            "base_url": settings.OLLAMA_BASE_URL,
            "response": None,
            "error": str(e)
        }

    all_ok = all(results[k]["status"] == "OK" for k in results)
    return {
        "all_healthy": all_ok,
        "providers": results
    }
