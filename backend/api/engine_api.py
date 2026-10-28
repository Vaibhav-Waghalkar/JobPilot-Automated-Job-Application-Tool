import asyncio
import logging
import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.vault.database import get_db, AsyncSessionLocal
from backend.vault.models import (
    FixedProfile,
    VaultFact,
    Resume,
    JobPreference,
    JobApplication,
    ActivityLog
)
from backend.agents.hard_filters import apply_hard_filters
from backend.agents.job_matcher import JobMatcher
from backend.agents.form_filler import playwright_form_filler
from backend.adapters.internshala_adapter import InternshalaAdapter
from backend.adapters.naukri_adapter import NaukriAdapter
from backend.adapters.base_adapter import DiscoveredJob
from backend.vault.missing_info import analyze_missing_info

logger = logging.getLogger("jobpilot.engine")

router = APIRouter(prefix="/api/engine", tags=["Engine Single Start & Controller"])

class EngineState:
    def __init__(self):
        self.status = "Stopped" # "Running", "Paused", "Stopped"
        self.mode = "REVIEW" # "DRY_RUN", "REVIEW", "AUTO"
        self.current_job_id: Optional[int] = None
        self.current_job_title: Optional[str] = None
        self.current_company: Optional[str] = None
        self.current_step: Optional[str] = None
        self.stop_requested = False
        self.pause_requested = False
        self.last_run_summary: Dict[str, Any] = {}

engine_state = EngineState()

class StartEngineRequest(BaseModel):
    mode: Optional[str] = "DRY_RUN" # DRY_RUN, REVIEW, AUTO
    platform: Optional[str] = "internshala" # "internshala", "naukri", "mock"
    max_applications: Optional[int] = 2
    job_type: Optional[str] = "job"

@router.get("/status")
async def get_engine_status(db: AsyncSession = Depends(get_db)):
    """Returns real-time engine running status and stats for Dashboard."""
    # Count today stats from database
    stmt_apps = select(JobApplication)
    res = await db.execute(stmt_apps)
    all_apps = res.scalars().all()

    found = len(all_apps)
    matched = sum(1 for a in all_apps if a.status in ["matched", "needs_you", "applied"])
    applied = sum(1 for a in all_apps if a.status == "applied")
    skipped = sum(1 for a in all_apps if a.status == "skipped")
    needs_you = sum(1 for a in all_apps if a.status == "needs_you")

    # Fetch waiting for approval items (status == needs_you and reason has Review Mode)
    waiting_for_approval = [
        {
            "id": a.id,
            "company": a.company,
            "title": a.title,
            "salary_raw": a.salary_raw,
            "status": a.status,
            "answers_submitted": a.answers_submitted or {},
            "screenshot": a.needs_you_screenshot,
            "resume_version_used": a.resume_version_used or "Vaibhav Waghalkar - Full-Stack Developer.pdf",
            "apply_url": a.apply_url
        }
        for a in all_apps if a.status == "needs_you" and a.needs_you_screenshot
    ]

    # Fetch active Needs You questions (blockers / questions requiring user input)
    needs_you_questions = [
        {
            "id": a.id,
            "company": a.company,
            "title": a.title,
            "question": a.needs_you_question or a.needs_you_reason or "Unknown field requiring answer",
            "reason": a.needs_you_reason,
            "timestamp": a.needs_you_timestamp.isoformat() if a.needs_you_timestamp else None,
            "screenshot": a.needs_you_screenshot,
        }
        for a in all_apps if a.status == "needs_you" and not a.needs_you_screenshot
    ]

    return {
        "status": engine_state.status,
        "mode": engine_state.mode,
        "current_job_id": engine_state.current_job_id,
        "current_job_title": engine_state.current_job_title,
        "current_company": engine_state.current_company,
        "current_step": engine_state.current_step,
        "stats": {
            "found": found,
            "matched": matched,
            "applied": applied,
            "skipped": skipped,
            "needs_you": needs_you
        },
        "waiting_for_approval": waiting_for_approval,
        "needs_you_questions": needs_you_questions
    }

async def _run_engine_flow(req: StartEngineRequest):
    """
    End-to-end autonomous engine execution:
    1. Pre-flight verification (verified facts & resume existence)
    2. Discovery of listings (mock by default or selected platform)
    3. Hard filters (deterministic)
    4. Match scoring (LLM)
    5. Form fill preparation per mode (DRY_RUN / REVIEW / AUTO)
    6. Respects Pause, Stop, human delays, daily caps, and 5-min blocker countdown
    """
    engine_state.status = "Running"
    engine_state.mode = req.mode or "REVIEW"
    engine_state.stop_requested = False
    engine_state.pause_requested = False
    engine_state.current_step = "Starting discovery..."

    try:
        async with AsyncSessionLocal() as db:
            # 1. Preflight check
            stmt_f = select(VaultFact).where(VaultFact.verified == True)
            facts = (await db.execute(stmt_f)).scalars().all()
            stmt_r = select(Resume)
            resumes = (await db.execute(stmt_r)).scalars().all()

            if not facts:
                engine_state.status = "Stopped"
                engine_state.current_step = "Error: No verified vault facts found."
                return
            if not resumes:
                engine_state.status = "Stopped"
                engine_state.current_step = "Error: No uploaded resume found in library."
                return

            stmt_pref = select(JobPreference).limit(1)
            pref = (await db.execute(stmt_pref)).scalars().first()

            # Record activity log
            db.add(ActivityLog(message=f"Engine started in {engine_state.mode} mode on platform '{req.platform}'."))
            await db.commit()

            # 2. Platform & Login Verification
            target_platform = req.platform or "internshala"
            if target_platform == "internshala":
                # Verify that persistent browser context has active Internshala login cookies
                engine_state.current_step = "Checking Internshala login session..."
                is_logged_in = await playwright_form_filler.is_logged_in_to_internshala()
                if not is_logged_in:
                    engine_state.status = "Stopped"
                    engine_state.current_step = "Log in to Internshala in Settings > Platforms first."
                    db.add(ActivityLog(message="Engine stopped: Log in to Internshala in Settings > Platforms first."))
                    await db.commit()
                    return

            # First real run limits: enforce DRY_RUN and max 2 jobs if not explicitly changed
            effective_mode = "DRY_RUN" if req.mode in [None, "DRY_RUN", "REVIEW"] else req.mode
            # Enforce max 2 jobs for initial run
            effective_limit = min(req.max_applications or 2, 2)

            # Discover jobs from selected platform
            engine_state.current_step = f"Searching jobs on {target_platform} (limit {effective_limit})..."
            raw_jobs = []

            if target_platform == "internshala":
                adapter = InternshalaAdapter()
                search_keywords = pref.target_roles if (pref and pref.target_roles) else ["python", "backend"]
                search_locations = pref.preferred_locations if (pref and pref.preferred_locations) else ["Pune", "Remote"]
                raw_jobs = await adapter.search_jobs(
                    keywords=search_keywords,
                    locations=search_locations,
                    limit=effective_limit,
                    job_type=req.job_type or "job"
                )
            else:
                # Fallback to mock only if platform is explicitly mock
                raw_jobs = [
                    DiscoveredJob(
                        platform="mock",
                        external_id="mock-job-1",
                        company="Apex Innovations",
                        title="Backend Developer",
                        location="Pune",
                        salary_raw="6-8 LPA",
                        apply_url="http://127.0.0.1:8000/mock/page1",
                        description="Looking for Python FastAPI and PostgreSQL backend engineer."
                    )
                ]

            if not raw_jobs:
                engine_state.status = "Stopped"
                engine_state.current_step = f"No new listings found on {target_platform} matching search criteria."
                return

            # Query already applied URLs
            stmt_apps = select(JobApplication.apply_url).where(JobApplication.status == "applied")
            applied_urls = set((await db.execute(stmt_apps)).scalars().all())

            matched_jobs_to_run = []

            # Evaluate each discovered job
            total_listings = len(raw_jobs)
            for idx, job in enumerate(raw_jobs, 1):
                if engine_state.stop_requested:
                    break
                while engine_state.pause_requested:
                    engine_state.status = "Paused"
                    await asyncio.sleep(1)
                engine_state.status = "Running"

                engine_state.current_company = job.company
                engine_state.current_job_title = job.title
                engine_state.current_step = f"Evaluating listing {idx} of {total_listings}: {job.company} - {job.title}"

                # Hard filter check
                passed, skip_reason = apply_hard_filters(
                    job=job,
                    prefs=pref,
                    applied_urls=applied_urls,
                    job_type=req.job_type or "job",
                    allow_undisclosed_salary=pref.allow_undisclosed_salary if pref else True,
                    max_experience_years=pref.max_experience_years if pref else 2.0
                )

                if not passed:
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
                        skip_reason=skip_reason
                    )
                    db.add(app_entry)
                    db.add(ActivityLog(message=f"Skipped {job.company} ({job.title}): {skip_reason}"))
                    await db.commit()
                    continue

                # Match scoring
                match_result = await JobMatcher.match_job(
                    title=job.title,
                    company=job.company,
                    job_description=job.description,
                    facts=facts
                )
                score = match_result.get("score", 0)
                threshold = pref.default_match_threshold if pref else 70

                if score < threshold:
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
                        skip_reason=f"Match score {score} is below threshold {threshold}"
                    )
                    db.add(app_entry)
                    db.add(ActivityLog(message=f"Skipped {job.company} - score {score} < {threshold}"))
                    await db.commit()
                    continue

                # Best resume selection
                best_resume = JobMatcher.select_best_resume(job.title, match_result.get("matched_skills", []), resumes)
                resume_file_path = best_resume.file_path if best_resume else None

                # Matched -> Create application record
                app_entry = JobApplication(
                    platform=job.platform,
                    job_id_external=job.external_id,
                    company=job.company,
                    title=job.title,
                    location=job.location,
                    salary_raw=job.salary_raw,
                    apply_url=job.apply_url,
                    job_description=job.description,
                    status="matched",
                    match_score=score,
                    match_reasons=match_result.get("matched_skills", []),
                    skill_gaps=match_result.get("gaps", []),
                    resume_version_used=best_resume.file_name if best_resume else None
                )
                db.add(app_entry)
                await db.commit()
                await db.refresh(app_entry)
                matched_jobs_to_run.append((app_entry, resume_file_path))

                if len(matched_jobs_to_run) >= effective_limit:
                    break

            # Process matched applications step by step with live progress
            total_matched = len(matched_jobs_to_run)
            for m_idx, (app_entry, resume_file_path) in enumerate(matched_jobs_to_run, 1):
                if engine_state.stop_requested:
                    break
                while engine_state.pause_requested:
                    engine_state.status = "Paused"
                    await asyncio.sleep(1)
                engine_state.status = "Running"

                engine_state.current_job_id = app_entry.id
                engine_state.current_company = app_entry.company
                engine_state.current_job_title = app_entry.title
                engine_state.current_step = f"Opening listing {m_idx} of {total_matched}: {app_entry.company}..."

                async def _update_step(msg: str):
                    engine_state.current_step = msg

                try:
                    fill_res = await playwright_form_filler.fill_application(
                        application_id=app_entry.id,
                        session=db,
                        override_resume_path=resume_file_path,
                        timeout_seconds=300,
                        mode_override=effective_mode,
                        progress_callback=_update_step
                    )
                except Exception as step_err:
                    logger.error(f"Step failed for {app_entry.company}: {step_err}", exc_info=True)
                    screenshot_path = str(settings.data_path / f"error_step_{app_entry.id}.png")
                    try:
                        if playwright_form_filler.context and playwright_form_filler.context.pages:
                            await playwright_form_filler.context.pages[-1].screenshot(path=screenshot_path)
                    except Exception:
                        screenshot_path = None

                    err_msg = f"Step failed on {app_entry.company}: {str(step_err)}"
                    engine_state.current_step = err_msg
                    app_entry.status = "failed"
                    app_entry.skip_reason = err_msg
                    db.add(ActivityLog(message=err_msg))
                    await db.commit()
                    # Continue to next job instead of crashing
                    continue

        engine_state.status = "Stopped"
        engine_state.current_step = "Run completed successfully."
        async with AsyncSessionLocal() as db_end:
            db_end.add(ActivityLog(message="Engine run finished."))
            await db_end.commit()

    except Exception as e:
        logger.error(f"Engine run error: {e}", exc_info=True)
        engine_state.status = "Stopped"
        engine_state.current_step = f"Engine stopped: {str(e)}"

@router.post("/start")
async def start_engine(
    req: StartEngineRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Single Start applying endpoint for the entire run.
    Verifies that verified vault facts and resumes exist before starting.
    """
    # 1. Preflight validation
    stmt_facts = select(VaultFact).where(VaultFact.verified == True)
    facts_count = len((await db.execute(stmt_facts)).scalars().all())

    stmt_resumes = select(Resume)
    resumes_count = len((await db.execute(stmt_resumes)).scalars().all())

    missing_errors = []
    if facts_count == 0:
        missing_errors.append("No verified vault facts exist in your profile. Please review and verify facts first.")
    if resumes_count == 0:
        missing_errors.append("No uploaded resume found in Documents. Please upload at least one role-tagged resume.")

    if missing_errors:
        raise HTTPException(status_code=400, detail="; ".join(missing_errors))

    if engine_state.status == "Running":
        return {"status": "already_running", "message": "Engine is already actively running."}

    engine_state.stop_requested = False
    engine_state.pause_requested = False
    background_tasks.add_task(_run_engine_flow, req)

    return {
        "status": "started",
        "mode": req.mode or "REVIEW",
        "message": f"Engine started in {req.mode or 'REVIEW'} mode."
    }

@router.post("/pause")
async def pause_engine():
    """Pauses current running engine execution."""
    if engine_state.status == "Running":
        engine_state.pause_requested = True
        engine_state.status = "Paused"
        return {"status": "paused", "message": "Engine paused."}
    return {"status": engine_state.status, "message": f"Engine is currently {engine_state.status}."}

@router.post("/resume")
async def resume_engine():
    """Resumes paused engine execution."""
    if engine_state.status == "Paused":
        engine_state.pause_requested = False
        engine_state.status = "Running"
        return {"status": "resumed", "message": "Engine resumed."}
    return {"status": engine_state.status, "message": f"Engine is currently {engine_state.status}."}

@router.post("/stop")
async def stop_engine():
    """Immediately stops engine and closes browser context."""
    engine_state.stop_requested = True
    engine_state.pause_requested = False
    engine_state.status = "Stopped"
    engine_state.current_step = "Stopped by user."
    try:
        await playwright_form_filler.close()
    except Exception:
        pass
    return {"status": "stopped", "message": "Engine halted."}

@router.post("/approve-application/{application_id}")
async def approve_waiting_application(application_id: int, db: AsyncSession = Depends(get_db)):
    """User clicks Approve on a prepared application in Review mode."""
    stmt = select(JobApplication).where(JobApplication.id == application_id)
    res = await db.execute(stmt)
    app_entry = res.scalars().first()
    if not app_entry:
        raise HTTPException(status_code=404, detail="Job application not found")

    app_entry.status = "applied"
    app_entry.applied_at = datetime.datetime.utcnow()
    app_entry.needs_you_reason = None
    app_entry.needs_you_question = None
    db.add(ActivityLog(message=f"Application for {app_entry.company} ({app_entry.title}) approved and marked applied."))
    await db.commit()
    return {"status": "success", "message": f"Application for {app_entry.company} approved."}

@router.post("/skip-application/{application_id}")
async def skip_waiting_application(application_id: int, db: AsyncSession = Depends(get_db)):
    """User clicks Skip on a prepared application in Review mode."""
    stmt = select(JobApplication).where(JobApplication.id == application_id)
    res = await db.execute(stmt)
    app_entry = res.scalars().first()
    if not app_entry:
        raise HTTPException(status_code=404, detail="Job application not found")

    app_entry.status = "skipped"
    app_entry.skip_reason = "Skipped by user during review approval"
    app_entry.needs_you_reason = None
    app_entry.needs_you_question = None
    db.add(ActivityLog(message=f"Application for {app_entry.company} skipped by user."))
    await db.commit()
    return {"status": "success", "message": f"Application for {app_entry.company} skipped."}
