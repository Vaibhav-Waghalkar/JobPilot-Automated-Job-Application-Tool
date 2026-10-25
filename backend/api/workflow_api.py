import os
import json
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.vault.database import get_db, AsyncSessionLocal
from backend.vault.models import (
    FixedProfile,
    VaultFact,
    Resume,
    JobPreference,
    JobApplication,
    ImportReviewItem,
    SavedQuestionAnswer,
    ActivityLog,
)
from backend.vault.importer import slugify, compute_hash
from backend.vault.vector_store import upsert_vault_fact_embedding, delete_vault_fact_embedding
from backend.vault.pdf_extractor import extract_text_from_file_bytes
from backend.importers.resume_extractor import ResumeToVaultExtractor
from backend.agents.form_filler import playwright_form_filler
from backend.agents.scheduler import jobpilot_scheduler

router = APIRouter(prefix="/api/workflow", tags=["Workflow & Form Filler"])

# --- Schemas ---
class RunConfigRequest(BaseModel):
    platform: str # "internshala", "career_page"
    role_tag: Optional[str] = None
    resume_id: Optional[int] = None
    mode: Optional[str] = "REVIEW" # DRY_RUN, REVIEW, AUTO
    max_applications: Optional[int] = 5
    job_type: Optional[str] = "job"

class AnswerNeedsYouRequest(BaseModel):
    application_id: int
    question: str
    answer: str

class UpdateOutcomeRequest(BaseModel):
    outcome: str # no_response, screening_call, interview, offer, rejected

class BulkApproveRequest(BaseModel):
    item_ids: List[int]

# --- Endpoints ---

@router.post("/resume-upload-and-extract")
async def upload_and_extract_resume(
    role_tag: str = Form(...),
    version: Optional[int] = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a resume (PDF/DOCX), tag with role, extract text strictly,
    and stage items in the review queue with conflict detection.
    """
    file_bytes = await file.read()
    filename = file.filename or "resume.pdf"
    ext = Path(filename).suffix.lower()

    # Determine version
    if version is None:
        stmt_v = select(Resume).where(Resume.role_tag == role_tag).order_by(Resume.version.desc()).limit(1)
        r_v = (await db.execute(stmt_v)).scalars().first()
        v_num = (r_v.version + 1) if r_v else 1
    else:
        v_num = version

    stored_name = f"resume_{slugify(role_tag)}_v{v_num}{ext}"
    target_path = settings.resumes_path / stored_name
    target_path.write_bytes(file_bytes)

    # Extract text cleanly with pypdf or docx
    text = extract_text_from_file_bytes(file_bytes, stored_name)

    resume_entry = Resume(
        role_tag=role_tag,
        version=v_num,
        file_name=stored_name,
        file_path=str(target_path),
        parsed_text=text
    )
    db.add(resume_entry)
    await db.commit()
    await db.refresh(resume_entry)

    # Run strict resume extraction and stage items into review queue
    extraction_result = await ResumeToVaultExtractor.extract_and_stage(
        resume_text=text,
        source_name=stored_name,
        session=db
    )

    return {
        "message": f"Resume uploaded as {role_tag} v{v_num}. {extraction_result['staged_count']} items staged for review.",
        "resume_id": resume_entry.id,
        "extraction": extraction_result
    }

@router.post("/review/bulk-approve")
async def bulk_approve_review_items(req: BulkApproveRequest, db: AsyncSession = Depends(get_db)):
    """
    Bulk approves staged resume items, marking them verified=True in the vault.
    Only verified facts enter the matcher and grounded answer engine.
    """
    stmt = select(ImportReviewItem).where(ImportReviewItem.id.in_(req.item_ids))
    res = await db.execute(stmt)
    items = res.scalars().all()

    approved_count = 0
    for item in items:
        item.status = "approved"
        fid = f"FACT-{item.section[:3].upper()}-{slugify(item.title)[:25]}"
        chash = compute_hash(item.proposed_content)

        stmt_f = select(VaultFact).where(VaultFact.id == fid)
        existing_f = (await db.execute(stmt_f)).scalars().first()

        if not existing_f:
            new_f = VaultFact(
                id=fid,
                section=item.section,
                title=item.title,
                content=item.proposed_content,
                metadata_json=item.metadata_json or {},
                content_hash=chash,
                verified=True,
                source=item.source
            )
            db.add(new_f)
            upsert_vault_fact_embedding(fid, item.proposed_content, {"section": item.section, "title": item.title})
        else:
            existing_f.title = item.title
            existing_f.content = item.proposed_content
            existing_f.content_hash = chash
            existing_f.verified = True
            existing_f.source = item.source
            upsert_vault_fact_embedding(fid, item.proposed_content, {"section": item.section, "title": item.title})

        approved_count += 1

    await db.commit()
    return {"message": f"Successfully approved {approved_count} items into verified vault."}

@router.post("/run-form-filler")
async def trigger_form_filler(
    application_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Launches Playwright form filler on an application in headed browser with persistent profile.
    """
    stmt = select(JobApplication).where(JobApplication.id == application_id)
    res = await db.execute(stmt)
    app_entry = res.scalars().first()
    if not app_entry:
        raise HTTPException(status_code=404, detail="Job application not found")

    async def _run_task():
        async with AsyncSessionLocal() as session:
            await playwright_form_filler.fill_application(application_id, session)

    background_tasks.add_task(_run_task)
    return {"message": f"Form filler launched for application {application_id}"}

@router.post("/needs-you/resolve")
async def resolve_needs_you(
    req: AnswerNeedsYouRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Resolves a 'Needs You' blocker:
    1. Saves answer into saved_qa and vault (verified=true) so it is NEVER asked twice.
    2. Resumes the application from the exact blocked step.
    """
    # 1. Save to saved_qa
    norm_q = re.sub(r"[^\w\s]", "", req.question.lower()).strip()
    stmt_qa = select(SavedQuestionAnswer).where(SavedQuestionAnswer.normalized_question == norm_q)
    existing_qa = (await db.execute(stmt_qa)).scalars().first()

    if not existing_qa:
        new_qa = SavedQuestionAnswer(
            normalized_question=norm_q,
            raw_question=req.question,
            answer=req.answer,
            verified=True
        )
        db.add(new_qa)
    else:
        existing_qa.answer = req.answer

    # 2. Add to vault facts as verified Q&A fact
    fid = f"FACT-QA-{slugify(req.question)[:25]}"
    content = f"Question: {req.question}\nAnswer: {req.answer}"
    chash = compute_hash(content)

    stmt_f = select(VaultFact).where(VaultFact.id == fid)
    fact = (await db.execute(stmt_f)).scalars().first()
    if not fact:
        fact = VaultFact(
            id=fid,
            section="standard_qa",
            title=f"Q&A: {req.question[:50]}",
            content=content,
            metadata_json={"question": req.question},
            content_hash=chash,
            verified=True,
            source="user_interactive_answer"
        )
        db.add(fact)
    else:
        fact.content = content
        fact.verified = True

    upsert_vault_fact_embedding(fid, content, {"section": "standard_qa", "title": fact.title})

    # 3. Update application status
    stmt_app = select(JobApplication).where(JobApplication.id == req.application_id)
    app_entry = (await db.execute(stmt_app)).scalars().first()
    if app_entry:
        app_entry.status = "matched" # Return to matched queue to resume
        app_entry.needs_you_reason = None
        app_entry.needs_you_question = None

    await db.commit()

    # 4. If application is currently paused waiting on blocker, signal it immediately
    if req.application_id in playwright_form_filler.pending_blockers:
        playwright_form_filler.signal_blocker_resolved(req.application_id, req.answer)
        return {"message": "Answer saved to verified vault and submitted to active browser immediately."}

    # Otherwise resume form filler in background
    async def _resume():
        async with AsyncSessionLocal() as session:
            await playwright_form_filler.fill_application(req.application_id, session)

    background_tasks.add_task(_resume)
    return {"message": "Answer saved to verified vault. Application resumed."}

@router.post("/browser/open-login")
async def open_browser_for_login(url: Optional[str] = "https://internshala.com/login/user"):
    """
    Opens persistent browser context for the user to log in manually once.
    JobPilot never asks for or stores user passwords.
    """
    res = await playwright_form_filler.open_manual_login_session(url)
    return res

@router.put("/tracker/{application_id}/outcome")
async def update_job_outcome(application_id: int, req: UpdateOutcomeRequest, db: AsyncSession = Depends(get_db)):
    """Update manual outcome (no response, screening, interview, offer, rejected)."""
    stmt = select(JobApplication).where(JobApplication.id == application_id)
    res = await db.execute(stmt)
    app_entry = res.scalars().first()
    if not app_entry:
        raise HTTPException(status_code=404, detail="Job application not found")

    app_entry.outcome = req.outcome
    app_entry.outcome_updated_at = datetime.datetime.utcnow()
    await db.commit()
    return {"message": f"Outcome updated to {req.outcome}"}

@router.get("/tracker/stats")
async def get_tracker_stats(db: AsyncSession = Depends(get_db)):
    """Computes response rates per platform and per resume version."""
    stmt = select(JobApplication)
    res = await db.execute(stmt)
    apps = res.scalars().all()

    platform_stats = {}
    resume_stats = {}

    positive_outcomes = {"screening_call", "interview", "offer"}

    for a in apps:
        p = a.platform or "other"
        r = a.resume_version_used or "unspecified"

        # Platform counts
        if p not in platform_stats:
            platform_stats[p] = {"applied": 0, "responses": 0, "interviews": 0}
        if a.status == "applied":
            platform_stats[p]["applied"] += 1
            if a.outcome in positive_outcomes:
                platform_stats[p]["responses"] += 1
            if a.outcome in {"interview", "offer"}:
                platform_stats[p]["interviews"] += 1

        # Resume version counts
        if r not in resume_stats:
            resume_stats[r] = {"applied": 0, "responses": 0, "interviews": 0}
        if a.status == "applied":
            resume_stats[r]["applied"] += 1
            if a.outcome in positive_outcomes:
                resume_stats[r]["responses"] += 1
            if a.outcome in {"interview", "offer"}:
                resume_stats[r]["interviews"] += 1

    return {
        "platform_stats": platform_stats,
        "resume_stats": resume_stats,
        "total_jobs": len(apps)
    }

# --- Scheduler & Controls ---

@router.post("/scheduler/start")
async def start_scheduler():
    jobpilot_scheduler.start()
    return {"status": "started", "kill_switch": jobpilot_scheduler.kill_switch_active}

@router.post("/scheduler/pause")
async def pause_scheduler():
    jobpilot_scheduler.pause()
    return {"status": "paused"}

@router.post("/scheduler/resume")
async def resume_scheduler():
    jobpilot_scheduler.resume()
    return {"status": "resumed"}

@router.post("/scheduler/kill-switch")
async def activate_kill_switch():
    jobpilot_scheduler.trigger_kill_switch()
    await playwright_form_filler.close()
    return {"status": "killed", "message": "All automation immediately stopped"}

@router.get("/activity-logs")
async def get_activity_logs(db: AsyncSession = Depends(get_db)):
    stmt = select(ActivityLog).order_by(ActivityLog.timestamp.desc()).limit(50)
    res = await db.execute(stmt)
    return res.scalars().all()
