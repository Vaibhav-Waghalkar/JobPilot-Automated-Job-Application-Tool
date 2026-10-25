from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    OLLAMA_MODEL: str = "qwen2.5:7b-instruct"

    DATA_DIR: str = "./data"
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/jobpilot.db"
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"
    BROWSER_PROFILE_DIR: str = "./data/browser_profile"

    DEFAULT_MATCH_THRESHOLD: int = 70
    HUMAN_ALERT_TIMEOUT_SECONDS: int = 300
    DAILY_APPLICATION_CAP_DEFAULT: int = 25
    APPLICATION_MODE: str = "DRY_RUN"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def data_path(self) -> Path:
        p = Path(self.DATA_DIR).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def resumes_path(self) -> Path:
        p = self.data_path / "resumes"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def documents_path(self) -> Path:
        p = self.data_path / "documents"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def master_profile_path(self) -> Path:
        return self.data_path / "master_profile.json"

settings = Settings()
