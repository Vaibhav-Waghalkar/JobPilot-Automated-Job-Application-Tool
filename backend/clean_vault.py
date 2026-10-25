import asyncio
import json
import shutil
from pathlib import Path
from backend.vault.database import engine, Base, init_db, AsyncSessionLocal
from backend.vault.models import FixedProfile, VaultFact, Resume, DocumentVault, JobPreference, ImportReviewItem, JobApplication, SavedQuestionAnswer, ActivityLog
from backend.config import settings

async def clean_vault():
    print("Cleaning database and vector store to start with empty vault...")
    
    # 1. Reset SQLite tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # 2. Re-create empty FixedProfile and JobPreference
    async with AsyncSessionLocal() as session:
        empty_prof = FixedProfile(
            full_name=None,
            date_of_birth=None,
            phone=None,
            email=None,
            location=None,
            notice_period_days=None,
            current_ctc=None,
            expected_ctc=None,
            total_experience_years=None,
            links={},
            languages=[]
        )
        empty_prefs = JobPreference(
            target_roles=[],
            min_salary=None,
            max_salary=None,
            preferred_locations=[],
            work_modes=["remote", "hybrid"],
            must_have_skills=[],
            blacklisted_companies=[],
            daily_caps={"internshala": 20, "career_page": 20},
            default_match_threshold=70,
            mode="REVIEW"
        )
        session.add(empty_prof)
        session.add(empty_prefs)
        await session.commit()

    # 3. Reset ChromaDB
    chroma_dir = settings.data_path / "chroma_db"
    if chroma_dir.exists():
        shutil.rmtree(chroma_dir, ignore_errors=True)

    # 4. Clean master_profile.json
    empty_master = {
        "fixed_profile": {
            "full_name": None,
            "date_of_birth": None,
            "phone": None,
            "email": None,
            "location": None,
            "notice_period_days": None,
            "current_ctc": None,
            "expected_ctc": None,
            "total_experience_years": None,
            "links": {},
            "languages": []
        },
        "education": [],
        "experience": [],
        "projects": [],
        "skills": [],
        "star_stories": [],
        "certifications": [],
        "standard_qa": [],
        "job_preferences": {
            "target_roles": [],
            "min_salary": None,
            "max_salary": None,
            "preferred_locations": [],
            "work_modes": ["remote", "hybrid"],
            "must_have_skills": [],
            "blacklisted_companies": [],
            "daily_caps": {"internshala": 20, "career_page": 20},
            "default_match_threshold": 70
        }
    }
    settings.master_profile_path.write_text(json.dumps(empty_master, indent=2), encoding="utf-8")
    print("[OK] Empty vault initialized. Zero placeholder data.")

if __name__ == "__main__":
    asyncio.run(clean_vault())
