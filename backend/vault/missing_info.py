from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.vault.models import FixedProfile, VaultFact, Resume, DocumentVault

MANDATORY_FIXED_FIELDS = [
    ("full_name", "Full Name"),
    ("email", "Email Address"),
    ("phone", "Phone Number"),
    ("location", "Current Location"),
    ("current_ctc", "Current CTC"),
    ("expected_ctc", "Expected CTC"),
    ("notice_period_days", "Notice Period"),
    ("total_experience_years", "Total Experience Years"),
]

MANDATORY_SECTIONS = [
    ("experience", "Work Experience"),
    ("education", "Education History"),
    ("project", "Projects Portfolio"),
    ("skill", "Skills Inventory"),
]

MANDATORY_DOC_TYPES = [
    ("resume", "At least one role-tagged Resume"),
    ("id_proof", "Government ID Proof (Aadhaar/Passport/PAN)"),
    ("degree", "Degree Certificate / Marksheet"),
]

async def analyze_missing_info(session: AsyncSession) -> Dict[str, Any]:
    missing_items: List[Dict[str, str]] = []

    # 1. Check fixed profile
    stmt = select(FixedProfile).limit(1)
    res = await session.execute(stmt)
    profile = res.scalars().first()

    if not profile:
        for key, label in MANDATORY_FIXED_FIELDS:
            missing_items.append({
                "category": "Fixed Profile",
                "field": key,
                "label": label,
                "description": f"Missing critical applicant fact: {label}"
            })
    else:
        for key, label in MANDATORY_FIXED_FIELDS:
            val = getattr(profile, key, None)
            if val is None or val == "" or (isinstance(val, (int, float)) and val < 0):
                missing_items.append({
                    "category": "Fixed Profile",
                    "field": key,
                    "label": label,
                    "description": f"Missing or empty: {label}"
                })

    # 2. Check vault fact sections
    stmt_facts = select(VaultFact.section).distinct()
    res_facts = await session.execute(stmt_facts)
    present_sections = set(res_facts.scalars().all())

    for sec, label in MANDATORY_SECTIONS:
        if sec not in present_sections:
            missing_items.append({
                "category": "Vault Facts",
                "field": sec,
                "label": label,
                "description": f"No facts found under section: {label}"
            })

    # 3. Check Resumes
    stmt_resumes = select(Resume).limit(1)
    res_res = await session.execute(stmt_resumes)
    has_resume = res_res.scalars().first() is not None
    if not has_resume:
        missing_items.append({
            "category": "Documents & Resumes",
            "field": "resume",
            "label": "Tagged Resume",
            "description": "No role-tagged resumes uploaded in Resume Library"
        })

    # Optional documents (ID proof, degree) are requested only when a job requires them
    # and do not block readiness for applications
    return {
        "missing_count": len(missing_items),
        "is_ready_for_application": len(missing_items) == 0,
        "items": missing_items
    }
