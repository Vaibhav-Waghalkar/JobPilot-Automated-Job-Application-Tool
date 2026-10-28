import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response
from pydantic import BaseModel
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.vault.database import get_db
from backend.vault.models import (
    FixedProfile,
    VaultFact,
    Resume,
    DocumentVault,
    JobPreference,
    ImportReviewItem,
    ConflictItem,
    ProjectTierItem,
)
from backend.vault.importer import ProfileImporter, compute_hash, slugify
from backend.vault.vector_store import (
    upsert_vault_fact_embedding,
    delete_vault_fact_embedding,
    query_vault_facts,
)
from backend.vault.missing_info import analyze_missing_info
from backend.vault.pdf_extractor import extract_text_from_pdf
from backend.export.pdf_generator import generate_biodata_pdf_bytes
from backend.importers.review_importer import (
    parse_linkedin_zip,
    scrape_portfolio_url,
    stage_for_review,
)
from backend.importers.full_ingestion_service import FullDataIngestionService

router = APIRouter(prefix="/api/vault", tags=["Vault"])

# --- Schemas ---
class FixedProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    location: Optional[str] = None
    notice_period_days: Optional[int] = None
    current_ctc: Optional[str] = None
    expected_ctc: Optional[str] = None
    total_experience_years: Optional[float] = None
    employment_status: Optional[str] = None
    availability: Optional[str] = None
    links: Optional[Dict[str, str]] = None
    languages: Optional[List[str]] = None

class VaultFactUpdate(BaseModel):
    title: str
    content: str
    section: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None

class JobPreferencesUpdate(BaseModel):
    target_roles: Optional[List[str]] = None
    min_salary: Optional[float] = None
    max_salary: Optional[float] = None
    preferred_locations: Optional[List[str]] = None
    work_modes: Optional[List[str]] = None
    must_have_skills: Optional[List[str]] = None
    blacklisted_companies: Optional[List[str]] = None
    daily_caps: Optional[Dict[str, int]] = None
    default_match_threshold: Optional[int] = None
    allow_undisclosed_salary: Optional[bool] = None
    max_experience_years: Optional[float] = None

class StagedItemDecision(BaseModel):
    action: str # "approve", "reject", "edit_and_approve"
    edited_title: Optional[str] = None
    edited_content: Optional[str] = None
    edited_section: Optional[str] = None

class ConflictResolutionRequest(BaseModel):
    chosen_value: str
    chosen_source: Optional[str] = "User typed/selected"

class ProjectTierConfirmRequest(BaseModel):
    tier: Optional[str] = None # "Tier A", "Tier B", "Tier C"
    use_in_applications: Optional[bool] = None

class ScrapeRequest(BaseModel):
    url: str

class PasteImportRequest(BaseModel):
    source: str # "linkedin_text" or "portfolio_text"
    section: str
    title: str
    text: str

# --- Endpoints ---

@router.get("/summary")
async def get_vault_summary(db: AsyncSession = Depends(get_db)):
    """Summary counts and status for dashboard overview."""
    facts_count = (await db.execute(select(VaultFact))).scalars().all()
    resumes_count = (await db.execute(select(Resume))).scalars().all()
    docs_count = (await db.execute(select(DocumentVault))).scalars().all()
    pending_reviews = (await db.execute(select(ImportReviewItem).where(ImportReviewItem.status == "pending"))).scalars().all()
    missing_info = await analyze_missing_info(db)

    return {
        "facts_count": len(facts_count),
        "resumes_count": len(resumes_count),
        "documents_count": len(docs_count),
        "pending_reviews_count": len(pending_reviews),
        "missing_items_count": missing_info["missing_count"],
        "is_ready_for_application": missing_info["is_ready_for_application"],
    }

@router.post("/import-master-profile")
async def import_master_profile(db: AsyncSession = Depends(get_db)):
    """Imports the master_profile.json from data directory into SQLite & ChromaDB."""
    profile_path = settings.master_profile_path
    if not profile_path.exists():
        raise HTTPException(status_code=404, detail="master_profile.json not found in data directory")

    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read/parse master_profile.json: {e}")

    stats = await ProfileImporter.import_profile_data(data, db)
    return {"message": "Master profile imported successfully", "stats": stats}

@router.get("/fixed-profile")
async def get_fixed_profile(db: AsyncSession = Depends(get_db)):
    """Retrieves fixed profile facts (never generated by LLM)."""
    stmt = select(FixedProfile).limit(1)
    res = await db.execute(stmt)
    profile = res.scalars().first()
    if not profile:
        return {}
    return {
        "full_name": profile.full_name,
        "date_of_birth": profile.date_of_birth,
        "phone": profile.phone,
        "email": profile.email,
        "location": profile.location,
        "notice_period_days": profile.notice_period_days,
        "current_ctc": profile.current_ctc,
        "expected_ctc": profile.expected_ctc,
        "total_experience_years": profile.total_experience_years,
        "employment_status": profile.employment_status,
        "availability": profile.availability,
        "links": profile.links,
        "languages": profile.languages,
        "updated_at": profile.updated_at,
    }

@router.put("/fixed-profile")
async def update_fixed_profile(payload: FixedProfileUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(FixedProfile).limit(1)
    res = await db.execute(stmt)
    profile = res.scalars().first()
    if not profile:
        profile = FixedProfile()
        db.add(profile)

    update_dict = payload.model_dump(exclude_unset=True)
    for k, v in update_dict.items():
        setattr(profile, k, v)

    await db.commit()
    await db.refresh(profile)
    return {"message": "Fixed profile updated successfully", "profile": profile}

@router.get("/facts")
async def get_all_facts(section: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    stmt = select(VaultFact)
    if section:
        stmt = stmt.where(VaultFact.section == section)
    res = await db.execute(stmt)
    facts = res.scalars().all()
    return [
        {
            "id": f.id,
            "section": f.section,
            "title": f.title,
            "content": f.content,
            "metadata_json": f.metadata_json,
            "verified": f.verified,
            "source": f.source,
            "updated_at": f.updated_at,
        }
        for f in facts
    ]

@router.put("/facts/{fact_id}")
async def update_fact(fact_id: str, payload: VaultFactUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(VaultFact).where(VaultFact.id == fact_id)
    res = await db.execute(stmt)
    fact = res.scalars().first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")

    fact.title = payload.title
    fact.content = payload.content
    if payload.section:
        fact.section = payload.section
    if payload.metadata_json is not None:
        fact.metadata_json = payload.metadata_json
    fact.content_hash = compute_hash(payload.content)
    fact.verified = True
    fact.source = "edited by user"

    try:
        upsert_vault_fact_embedding(fact.id, fact.content, {"section": fact.section, "title": fact.title})
    except Exception:
        pass
    await db.commit()
    return {"message": "Fact updated, verified, and re-indexed in ChromaDB", "id": fact.id, "verified": True}

@router.post("/facts")
async def create_fact(payload: VaultFactUpdate, db: AsyncSession = Depends(get_db)):
    """Creates a new user fact directly in the vault as verified."""
    fid = f"FACT-USR-{slugify(payload.title)[:30]}"
    chash = compute_hash(payload.content)
    fact = VaultFact(
        id=fid,
        section=payload.section or "skill",
        title=payload.title,
        content=payload.content,
        metadata_json=payload.metadata_json or {},
        content_hash=chash,
        verified=True,
        source="added by user"
    )
    db.add(fact)
    try:
        upsert_vault_fact_embedding(fid, payload.content, {"section": payload.section or "skill", "title": payload.title})
    except Exception:
        pass
    await db.commit()
    return {"status": "success", "message": "Fact created and verified in vault", "id": fid}

@router.delete("/facts/{fact_id}")
async def delete_fact(fact_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(VaultFact).where(VaultFact.id == fact_id)
    res = await db.execute(stmt)
    fact = res.scalars().first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")

    await db.delete(fact)
    delete_vault_fact_embedding(fact_id)
    await db.commit()
    return {"message": "Fact deleted from SQLite and ChromaDB", "id": fact_id}

# --- Saved Answers (Learned Q&A) ---
class SavedQAUpdate(BaseModel):
    answer: str

@router.get("/saved-answers")
async def get_saved_answers(db: AsyncSession = Depends(get_db)):
    from backend.vault.models import SavedQuestionAnswer
    stmt = select(SavedQuestionAnswer).order_by(SavedQuestionAnswer.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.put("/saved-answers/{qa_id}")
async def update_saved_answer(qa_id: int, req: SavedQAUpdate, db: AsyncSession = Depends(get_db)):
    from backend.vault.models import SavedQuestionAnswer
    stmt = select(SavedQuestionAnswer).where(SavedQuestionAnswer.id == qa_id)
    res = await db.execute(stmt)
    item = res.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Saved answer not found")
    item.answer = req.answer
    await db.commit()
    return {"status": "success", "message": "Saved answer updated", "id": qa_id, "answer": req.answer}

@router.delete("/saved-answers/{qa_id}")
async def delete_saved_answer(qa_id: int, db: AsyncSession = Depends(get_db)):
    from backend.vault.models import SavedQuestionAnswer
    stmt = select(SavedQuestionAnswer).where(SavedQuestionAnswer.id == qa_id)
    res = await db.execute(stmt)
    item = res.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Saved answer not found")
    await db.delete(item)
    await db.commit()
    return {"status": "success", "message": "Saved answer deleted", "id": qa_id}

@router.get("/missing-info")
async def get_missing_info(db: AsyncSession = Depends(get_db)):
    """Computes all required fields missing before an application can be submitted."""
    return await analyze_missing_info(db)

# --- Resume Library ---
@router.get("/resumes")
async def get_resumes(db: AsyncSession = Depends(get_db)):
    stmt = select(Resume).order_by(Resume.role_tag, Resume.version.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/resumes/upload")
async def upload_resume(
    role_tag: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Role-tagged resumes with versioning.
    Uploading a new resume with an existing role_tag increments version.
    """
    stmt = select(Resume).where(Resume.role_tag == role_tag).order_by(Resume.version.desc()).limit(1)
    res = await db.execute(stmt)
    latest = res.scalars().first()
    next_version = (latest.version + 1) if latest else 1

    file_bytes = await file.read()
    sanitized_tag = slugify(role_tag)
    ext = Path(file.filename or "resume.pdf").suffix or ".pdf"
    stored_filename = f"resume_{sanitized_tag}_v{next_version}{ext}"
    target_path = settings.resumes_path / stored_filename

    target_path.write_bytes(file_bytes)

    # Extract text
    parsed_text = extract_text_from_pdf(file_bytes)

    resume_entry = Resume(
        role_tag=role_tag,
        version=next_version,
        file_name=stored_filename,
        file_path=str(target_path),
        parsed_text=parsed_text,
    )
    db.add(resume_entry)
    await db.commit()
    await db.refresh(resume_entry)

    return {
        "message": f"Resume uploaded as version {next_version} for role '{role_tag}'",
        "resume": resume_entry
    }

# --- Document Vault & Checklist ---
@router.get("/documents")
async def get_documents(db: AsyncSession = Depends(get_db)):
    stmt = select(DocumentVault).order_by(DocumentVault.uploaded_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/documents/upload")
async def upload_document(
    doc_type: str = Form(...),
    name: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    file_bytes = await file.read()
    ext = Path(file.filename or "doc.pdf").suffix or ".pdf"
    stored_name = f"{slugify(doc_type)}_{slugify(name)}{ext}"
    target_path = settings.documents_path / stored_name

    target_path.write_bytes(file_bytes)
    extracted_text = extract_text_from_pdf(file_bytes) if ext.lower() == ".pdf" else ""

    doc_entry = DocumentVault(
        doc_type=doc_type,
        name=name,
        file_name=stored_name,
        file_path=str(target_path),
        extracted_text=extracted_text,
    )
    db.add(doc_entry)
    await db.commit()
    await db.refresh(doc_entry)
    return {"message": "Document added to vault", "document": doc_entry}

@router.post("/documents/checklist-audit")
async def audit_application_checklist(required_types: List[str], db: AsyncSession = Depends(get_db)):
    """
    Per-application checklist that flags missing or mismatched docs before submit.
    """
    stmt = select(DocumentVault)
    res = await db.execute(stmt)
    docs = res.scalars().all()
    available_types = {d.doc_type for d in docs}

    missing = [req for req in required_types if req not in available_types]
    return {
        "ready": len(missing) == 0,
        "required": required_types,
        "available": list(available_types),
        "missing": missing,
    }

# --- Job Preferences ---
@router.get("/preferences")
async def get_job_preferences(db: AsyncSession = Depends(get_db)):
    stmt = select(JobPreference).limit(1)
    res = await db.execute(stmt)
    prefs = res.scalars().first()
    if not prefs:
        return {}
    return prefs

@router.put("/preferences")
async def update_job_preferences(payload: JobPreferencesUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(JobPreference).limit(1)
    res = await db.execute(stmt)
    prefs = res.scalars().first()
    if not prefs:
        prefs = JobPreference()
        db.add(prefs)

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(prefs, k, v)

    await db.commit()
    await db.refresh(prefs)
    return {"message": "Job preferences updated", "preferences": prefs}

# --- Importers with Human Review & Conflict Detection ---
@router.get("/import/review-items")
async def get_pending_review_items(status: Optional[str] = "pending", db: AsyncSession = Depends(get_db)):
    stmt = select(ImportReviewItem)
    if status:
        stmt = stmt.where(ImportReviewItem.status == status)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/import/review-items/{item_id}/decide")
async def decide_review_item(item_id: int, decision: StagedItemDecision, db: AsyncSession = Depends(get_db)):
    stmt = select(ImportReviewItem).where(ImportReviewItem.id == item_id)
    res = await db.execute(stmt)
    item = res.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")

    if decision.action == "reject":
        item.status = "rejected"
        await db.commit()
        return {"status": "success", "message": "Item rejected", "id": item_id}

    # Approve or edit_and_approve
    final_title = decision.edited_title or item.title
    final_content = decision.edited_content or item.proposed_content
    final_section = decision.edited_section or item.section

    # Add as new vault fact or update existing with clean slug ID
    clean_slug = slugify(final_title)
    fid = f"FACT-IMP-{clean_slug[:35]}"
    chash = compute_hash(final_content)

    stmt_fact = select(VaultFact).where(VaultFact.id == fid)
    fact_res = await db.execute(stmt_fact)
    fact = fact_res.scalars().first()

    if not fact:
        fact = VaultFact(
            id=fid,
            section=final_section,
            title=final_title,
            content=final_content,
            metadata_json={"source": item.source, "imported_from_staging": True},
            content_hash=chash,
            verified=True,
            source="user_approved"
        )
        db.add(fact)
    else:
        fact.title = final_title
        fact.content = final_content
        fact.section = final_section
        fact.content_hash = chash
        fact.verified = True
        fact.source = "user_approved"

    try:
        upsert_vault_fact_embedding(fid, final_content, {"section": final_section, "title": final_title})
    except Exception as emb_err:
        pass # Allow DB commit even if vector embedding store is offline

    item.status = "approved" if decision.action == "approve" else "edited"
    await db.commit()

    return {"status": "success", "message": f"Item approved and added to vault as {fid}", "fact_id": fid}

@router.post("/import/review-items/bulk-approve")
async def bulk_approve_review_items(db: AsyncSession = Depends(get_db)):
    """Approves all pending staged review items into verified vault facts."""
    stmt = select(ImportReviewItem).where(ImportReviewItem.status == "pending")
    items = (await db.execute(stmt)).scalars().all()
    approved_count = 0
    for item in items:
        fid = f"FACT-IMP-{slugify(item.title)[:35]}"
        chash = compute_hash(item.proposed_content)
        stmt_f = select(VaultFact).where(VaultFact.id == fid)
        fact = (await db.execute(stmt_f)).scalars().first()
        if not fact:
            fact = VaultFact(
                id=fid,
                section=item.section,
                title=item.title,
                content=item.proposed_content,
                metadata_json={"source": item.source, "imported_from_staging": True},
                content_hash=chash,
                verified=True,
                source="user_bulk_approved"
            )
            db.add(fact)
        else:
            fact.verified = True
        try:
            upsert_vault_fact_embedding(fid, item.proposed_content, {"section": item.section, "title": item.title})
        except Exception:
            pass
        item.status = "approved"
        approved_count += 1

    await db.commit()
    return {"status": "success", "message": f"Approved {approved_count} items into verified vault facts", "count": approved_count}

@router.post("/import/review-items/bulk-reject")
async def bulk_reject_review_items(db: AsyncSession = Depends(get_db)):
    """Rejects all pending staged review items."""
    stmt = select(ImportReviewItem).where(ImportReviewItem.status == "pending")
    items = (await db.execute(stmt)).scalars().all()
    rejected_count = 0
    for item in items:
        item.status = "rejected"
        rejected_count += 1
    await db.commit()
    return {"status": "success", "message": f"Rejected {rejected_count} items", "count": rejected_count}

@router.post("/import/linkedin-zip")
async def import_linkedin_data(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    content = await file.read()
    staged = await parse_linkedin_zip(content, db)
    return {
        "message": f"Extracted {len(staged)} items from LinkedIn export and sent to Review screen",
        "count": len(staged)
    }

@router.post("/import/scrape-portfolio")
async def scrape_portfolio(payload: ScrapeRequest, db: AsyncSession = Depends(get_db)):
    try:
        staged = await scrape_portfolio_url(payload.url, db)
        return {
            "message": f"Scraped {len(staged)} items from {payload.url} and staged for Review",
            "count": len(staged)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to scrape URL: {str(e)}")

@router.post("/import/paste-text")
async def import_pasted_text(payload: PasteImportRequest, db: AsyncSession = Depends(get_db)):
    items = [{
        "section": payload.section,
        "title": payload.title,
        "content": payload.text
    }]
    staged = await stage_for_review(items, payload.source, db)
    return {"message": "Pasted item staged for Review", "staged_id": staged[0].id}

# --- Biodata PDF Export ---
@router.get("/export/biodata-pdf")
async def export_biodata_pdf(db: AsyncSession = Depends(get_db)):
    stmt_prof = select(FixedProfile).limit(1)
    res_prof = await db.execute(stmt_prof)
    profile_row = res_prof.scalars().first()
    
    prof_dict = {}
    if profile_row:
        prof_dict = {
            "full_name": profile_row.full_name,
            "email": profile_row.email,
            "phone": profile_row.phone,
            "location": profile_row.location,
            "total_experience_years": profile_row.total_experience_years,
            "links": profile_row.links or {},
        }

    stmt_facts = select(VaultFact)
    res_facts = await db.execute(stmt_facts)
    facts_rows = res_facts.scalars().all()
    facts_list = [{"id": f.id, "section": f.section, "title": f.title, "content": f.content} for f in facts_rows]

    pdf_bytes = generate_biodata_pdf_bytes(prof_dict, facts_list)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=JobPilot_Biodata.pdf"}
    )

# --- Full Data Ingestion & Conflicts Management ---

@router.post("/full-ingestion/run")
async def trigger_full_ingestion(db: AsyncSession = Depends(get_db)):
    """Triggers Section A full data ingestion from inbox PDFs, portfolio, LinkedIn data, and GitHub."""
    return await FullDataIngestionService.run_full_ingestion(db)

@router.get("/conflicts")
async def get_conflicts(db: AsyncSession = Depends(get_db)):
    """Retrieves all conflict items for user review."""
    stmt = select(ConflictItem).order_by(ConflictItem.resolved, ConflictItem.id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(conflict_id: int, req: ConflictResolutionRequest, db: AsyncSession = Depends(get_db)):
    """Resolves a conflict with user-chosen or user-typed value."""
    stmt = select(ConflictItem).where(ConflictItem.id == conflict_id)
    res = await db.execute(stmt)
    item = res.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Conflict item not found")

    item.resolved = True
    item.chosen_value = req.chosen_value
    item.chosen_source = req.chosen_source
    item.resolved_at = datetime.utcnow()
    await db.commit()
    return {"status": "resolved", "id": conflict_id, "chosen_value": req.chosen_value}

@router.get("/project-tiers")
async def get_project_tiers(db: AsyncSession = Depends(get_db)):
    """Retrieves all categorized project tiers with rubric details."""
    stmt = select(ProjectTierItem).order_by(ProjectTierItem.tier, ProjectTierItem.project_name)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/project-tiers/{project_id}/confirm")
async def confirm_project_tier(project_id: int, req: ProjectTierConfirmRequest, db: AsyncSession = Depends(get_db)):
    """User confirms or adjusts project tier and usage in applications."""
    stmt = select(ProjectTierItem).where(ProjectTierItem.id == project_id)
    res = await db.execute(stmt)
    item = res.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Project item not found")

    if req.tier:
        item.tier = req.tier
    if req.use_in_applications is not None:
        item.use_in_applications = req.use_in_applications
    item.user_confirmed = True
    await db.commit()
    return {"status": "confirmed", "id": project_id, "tier": item.tier, "use_in_applications": item.use_in_applications}
