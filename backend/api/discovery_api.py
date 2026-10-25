import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.vault.database import get_db
from backend.vault.models import (
    VaultFact,
    FixedProfile,
    Resume,
    JobPreference,
    JobApplication,
)
from backend.vault.importer import slugify, compute_hash
from backend.vault.vector_store import upsert_vault_fact_embedding
from backend.adapters.internshala_adapter import InternshalaAdapter
from backend.adapters.career_pages_adapter import CareerPagesAdapter
from backend.adapters.naukri_adapter import NaukriAdapter
from backend.adapters.base_adapter import DiscoveredJob
from backend.agents.hard_filters import apply_hard_filters
from backend.agents.job_matcher import JobMatcher
from backend.agents.grounded_engine import GroundedAnswerEngine

router = APIRouter(prefix="/api/discovery", tags=["Discovery and Matching"])

# --- Schemas ---
class DiscoveryRequest(BaseModel):
    platform: str # "internshala", "career_page"
    keywords: Optional[List[str]] = ["python", "software engineer"]
    locations: Optional[List[str]] = ["Bengaluru", "Remote"]
    career_url: Optional[str] = None
    job_type: Optional[str] = "job" # "job" or "internship"
    limit: Optional[int] = 10

class TestLiveListingRequest(BaseModel):
    platform: Optional[str] = "internshala"
    keywords: Optional[List[str]] = ["python"]
    locations: Optional[List[str]] = ["Remote"]
    job_type: Optional[str] = "job" # "job" or "internship"
    limit: Optional[int] = 5

class QuestionAnswerRequest(BaseModel):
    question: str
    job_description: Optional[str] = ""

class SaveAnswerToVaultRequest(BaseModel):
    question: str
    answer: str
    section: Optional[str] = "standard_qa"

# --- Endpoints ---

@router.post("/test-live-listing")
async def test_live_listing(req: TestLiveListingRequest, db: AsyncSession = Depends(get_db)):
    """
    TEST WITH LIVE LISTING (Safety Sandbox):
    Scrapes real Internshala listings, executes hard filters and LLM match scoring ONLY.
    Never creates application runs or applies to anything.
    Allows user to inspect match score, hard-filter decisions, and best resume fit safely.
    """
    stmt_prefs = select(JobPreference).limit(1)
    prefs_res = await db.execute(stmt_prefs)
    prefs = prefs_res.scalars().first()

    stmt_apps = select(JobApplication.apply_url)
    apps_res = await db.execute(stmt_apps)
    applied_urls = set(apps_res.scalars().all())

    # 1. Scrape real live listings
    adapter = InternshalaAdapter()
    raw_jobs = await adapter.search_jobs(
        keywords=req.keywords or ["python"],
        locations=req.locations or ["Remote"],
        limit=req.limit or 5,
        job_type=req.job_type or "job"
    )

    if not raw_jobs:
        return {
            "status": "warning",
            "message": "No live listings found from Internshala for the given parameters.",
            "results": []
        }

    stmt_facts = select(VaultFact).where(VaultFact.verified == True)
    facts_rows = (await db.execute(stmt_facts)).scalars().all()

    stmt_resumes = select(Resume).order_by(Resume.version.desc())
    resumes_rows = (await db.execute(stmt_resumes)).scalars().all()

    threshold = prefs.default_match_threshold if prefs else 70
    audit_results = []

    for job in raw_jobs:
        # Check hard filters
        passed, skip_reason = apply_hard_filters(job, prefs, applied_urls)

        match_score = None
        match_details = None
        best_resume_tag = None

        if passed:
            # Run LLM match scoring
            match_details = await JobMatcher.match_job(
                title=job.title,
                company=job.company,
                job_description=job.description,
                facts=facts_rows
            )
            match_score = match_details.get("score")
            best_resume = JobMatcher.select_best_resume(job.title, match_details.get("matched_skills", []), resumes_rows)
            best_resume_tag = f"{best_resume.role_tag} v{best_resume.version}" if best_resume else "None"

        audit_results.append({
            "company": job.company,
            "title": job.title,
            "job_type": job.metadata.get("job_type", req.job_type),
            "location": job.location,
            "salary": job.salary_raw,
            "apply_url": job.apply_url,
            "hard_filter_passed": passed,
            "skip_reason": skip_reason,
            "match_score": match_score,
            "above_threshold": (match_score >= threshold) if match_score is not None else False,
            "matched_skills": match_details.get("matched_skills", []) if match_details else [],
            "gaps": match_details.get("gaps", []) if match_details else [],
            "analysis": match_details.get("analysis", "") if match_details else "",
            "recommended_resume": best_resume_tag,
            "action": "MATCHED" if (passed and match_score and match_score >= threshold) else "SKIPPED"
        })

    return {
        "status": "success",
        "message": f"Successfully evaluated {len(audit_results)} live Internshala listings with zero form submissions.",
        "threshold": threshold,
        "results": audit_results
    }

@router.post("/run")
async def run_job_discovery(req: DiscoveryRequest, db: AsyncSession = Depends(get_db)):
    """
    Executes platform discovery, applies hard filters, runs LLM match scoring,
    and logs matched/skipped jobs in SQLite.
    """
    # 1. Fetch preferences and existing applied URLs
    stmt_prefs = select(JobPreference).limit(1)
    prefs_res = await db.execute(stmt_prefs)
    prefs = prefs_res.scalars().first()

    stmt_apps = select(JobApplication.apply_url)
    apps_res = await db.execute(stmt_apps)
    applied_urls = set(apps_res.scalars().all())

    # 2. Scrape jobs from selected adapter
    raw_jobs: List[DiscoveredJob] = []
    if req.platform == "internshala":
        adapter = InternshalaAdapter()
        raw_jobs = await adapter.search_jobs(
            keywords=req.keywords or ["python"],
            locations=req.locations or ["Bengaluru"],
            limit=req.limit or 10,
            job_type=req.job_type or "job"
        )
    elif req.platform == "naukri":
        # Load local mock search results for safe mock testing
        from pathlib import Path
        mock_file = Path("data/mock_naukri_search.html")
        adapter = NaukriAdapter()
        if mock_file.exists():
            raw_jobs = adapter.parse_search_results(mock_file.read_text(encoding="utf-8"), limit=req.limit or 10)
        else:
            raw_jobs = []
    elif req.platform == "career_page" and req.career_url:
        adapter = CareerPagesAdapter()
        raw_jobs = await adapter.scrape_career_url(req.career_url)
    else:
        # Seeded realistic demonstration jobs for local testing
        raw_jobs = [
            DiscoveredJob(
                platform="internshala",
                external_id="insh-seed-1",
                company="TechEdge Innovations",
                title="Python Backend Developer",
                location="Bengaluru",
                salary_raw="18-24 LPA",
                apply_url="https://internshala.com/job/detail/python-backend-techedge-1",
                description="We are seeking a Python Backend Developer skilled in FastAPI, PostgreSQL, and distributed caching to build scalable microservices."
            ),
            DiscoveredJob(
                platform="internshala",
                external_id="insh-seed-2",
                company="CryptoScamCo",
                title="Senior Python Architect",
                location="Remote",
                salary_raw="35 LPA",
                apply_url="https://internshala.com/job/detail/crypto-lead-2",
                description="Lead architect for blockchain smart contract deployment."
            ),
            DiscoveredJob(
                platform="career_page",
                external_id="cp-seed-3",
                company="DataStream Systems",
                title="Junior PHP Specialist",
                location="Chennai",
                salary_raw="3.5 LPA",
                apply_url="https://datastream.io/careers/php-junior-3",
                description="Maintain legacy PHP codebases and MySQL databases."
            )
        ]

    # 3. Load authoritative vault facts and resumes
    stmt_facts = select(VaultFact)
    facts_rows = (await db.execute(stmt_facts)).scalars().all()

    stmt_resumes = select(Resume).order_by(Resume.version.desc())
    resumes_rows = (await db.execute(stmt_resumes)).scalars().all()

    threshold = prefs.default_match_threshold if prefs else 70
    processed_count = 0
    matched_count = 0
    skipped_count = 0

    for job in raw_jobs:
        # Check hard filters first
        passed, skip_reason = apply_hard_filters(job, prefs, applied_urls, job_type=req.job_type or "job")
        if not passed:
            # Record skipped job
            app_entry = JobApplication(
                platform=job.platform,
                job_id_external=job.external_id,
                company=job.company,
                title=job.title,
                location=job.location,
                salary_raw=job.salary_raw,
                apply_url=job.apply_url,
                job_description=job.description,
                status="skipped",
                skip_reason=skip_reason,
            )
            db.add(app_entry)
            skipped_count += 1
            processed_count += 1
            continue

        # Run LLM match scoring
        match_result = await JobMatcher.match_job(
            title=job.title,
            company=job.company,
            job_description=job.description,
            facts=facts_rows
        )

        score = match_result["score"]
        status = "matched" if score >= threshold else "skipped"
        skip_r = None if score >= threshold else f"Match score {score} is below threshold {threshold}"

        # Auto-select best-fit resume
        best_resume = JobMatcher.select_best_resume(job.title, match_result["matched_skills"], resumes_rows)
        resume_id = best_resume.id if best_resume else None

        app_entry = JobApplication(
            platform=job.platform,
            job_id_external=job.external_id,
            company=job.company,
            title=job.title,
            location=job.location,
            salary_raw=job.salary_raw,
            apply_url=job.apply_url,
            job_description=job.description,
            status=status,
            match_score=score,
            match_reasons=match_result,
            skip_reason=skip_r,
            resume_id=resume_id,
        )
        db.add(app_entry)
        if status == "matched":
            matched_count += 1
        else:
            skipped_count += 1
        processed_count += 1

    await db.commit()
    return {
        "message": f"Discovery complete: {processed_count} jobs evaluated. {matched_count} matched, {skipped_count} skipped.",
        "matched": matched_count,
        "skipped": skipped_count,
    }

@router.get("/jobs")
async def get_discovered_jobs(status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    stmt = select(JobApplication).order_by(JobApplication.created_at.desc())
    if status:
        stmt = stmt.where(JobApplication.status == status)
    res = await db.execute(stmt)
    return res.scalars().all()

# --- Grounded Answer Engine Endpoints ---

@router.post("/answer-engine/generate")
async def generate_grounded_answer(req: QuestionAnswerRequest, db: AsyncSession = Depends(get_db)):
    """
    Closed-book generation with fact citations, verifier pass, and code allowlist.
    """
    stmt_facts = select(VaultFact)
    facts = (await db.execute(stmt_facts)).scalars().all()

    stmt_prof = select(FixedProfile).limit(1)
    prof = (await db.execute(stmt_prof)).scalars().first()

    result = await GroundedAnswerEngine.generate_answer(
        question=req.question,
        job_description=req.job_description or "",
        facts=facts,
        profile=prof
    )
    return result

@router.post("/answer-engine/save-user-answer")
async def save_user_answer_to_vault(req: SaveAnswerToVaultRequest, db: AsyncSession = Depends(get_db)):
    """
    Saves user-provided answer from a 'Needs You' alert to SQLite & ChromaDB
    so that it is permanently recorded and never asked again.
    """
    fid = f"FACT-QA-{slugify(req.question)[:25]}"
    content = f"Question: {req.question}\nAnswer: {req.answer}"
    chash = compute_hash(content)

    stmt = select(VaultFact).where(VaultFact.id == fid)
    res = await db.execute(stmt)
    fact = res.scalars().first()

    if not fact:
        fact = VaultFact(
            id=fid,
            section=req.section or "standard_qa",
            title=f"Q&A: {req.question[:60]}",
            content=content,
            metadata_json={"source": "user_interactive_response", "question": req.question},
            content_hash=chash
        )
        db.add(fact)
    else:
        fact.content = content
        fact.content_hash = chash

    upsert_vault_fact_embedding(fid, content, {"section": fact.section, "title": fact.title})
    await db.commit()

    return {
        "message": f"Answer saved to vault as authoritative fact [{fid}]. Will never be asked again.",
        "fact_id": fid
    }
