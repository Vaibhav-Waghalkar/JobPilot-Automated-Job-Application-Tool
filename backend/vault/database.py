import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from backend.config import settings
from backend.vault.models import Base

def get_database_url() -> str:
    # If running in test mode or under pytest, use an isolated test database
    if os.environ.get("JOBPILOT_TEST_MODE") == "1" or "pytest" in sys.modules:
        return os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///./data/test_jobpilot.db")
    return os.environ.get("DATABASE_URL", settings.DATABASE_URL)

engine = create_async_engine(
    get_database_url(),
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

def set_test_database(test_url: str = "sqlite+aiosqlite:///./data/test_jobpilot.db"):
    """Switches database engine to an isolated test database so real data is never affected."""
    global engine, AsyncSessionLocal
    os.environ["JOBPILOT_TEST_MODE"] = "1"
    os.environ["TEST_DATABASE_URL"] = test_url
    engine = create_async_engine(test_url, echo=False, future=True)
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

