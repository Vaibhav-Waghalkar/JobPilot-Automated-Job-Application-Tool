import os
import sys

# Ensure tests run in an isolated test database
os.environ["JOBPILOT_TEST_MODE"] = "1"
os.environ["TEST_DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_jobpilot.db"

import asyncio
import httpx
from backend.vault.database import init_db, AsyncSessionLocal
from backend.vault.importer import ProfileImporter
from backend.vault.vector_store import query_vault_facts
from backend.vault.missing_info import analyze_missing_info
from backend.config import settings
import json

async def run_test():
    print("1. Initializing DB schema...")
    await init_db()
    print("[OK] DB schema initialized.")

    print("2. Importing master profile...")
    data = json.loads(settings.master_profile_path.read_text(encoding="utf-8"))
    async with AsyncSessionLocal() as session:
        stats = await ProfileImporter.import_profile_data(data, session)
        print("[OK] Import stats:", stats)

        print("3. Querying vector store...")
        query_res = query_vault_facts("Python FastAPI microservices", n_results=2)
        print("[OK] Chroma query returned documents:", len(query_res.get("documents", [[]])[0]))

        print("4. Checking missing info...")
        missing = await analyze_missing_info(session)
        print("[OK] Missing info items count:", missing["missing_count"])
        for it in missing["items"]:
            print(f"  - [{it['category']}] {it['label']}: {it['description']}")

    print("\nPhase 1 backend verification test PASSED!")

if __name__ == "__main__":
    asyncio.run(run_test())
