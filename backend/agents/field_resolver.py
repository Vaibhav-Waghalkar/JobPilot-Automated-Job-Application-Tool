import re
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.vault.models import FixedProfile, VaultFact, SavedQuestionAnswer
from backend.agents.grounded_engine import GroundedAnswerEngine

class FieldResolver:
    """
    Classifies form fields and resolves their values strictly in hierarchical order:
    (1) Fixed profile (hard facts: name, email, phone, notice period, CTC, DOB, location)
    (2) Verified vault facts via Grounded Answer Engine (cited, verified, allowlist checked)
    (3) Previously saved answers in saved_qa table
    (4) Unknown -> Blocker / 'Needs You' alert (never guess or invent)
    """

    @classmethod
    def classify_field(cls, label: str, field_type: str, tag_name: str) -> str:
        tag = (tag_name or "").lower()
        ftype = (field_type or "").lower()
        lbl = (label or "").lower()

        if ftype == "file" or any(k in lbl for k in ["upload", "resume", "cv", "document", "attachment"]):
            return "file"
        if tag == "textarea" or any(k in lbl for k in ["cover letter", "why", "describe", "assignment", "solution", "project link", "github link", "assessment"]):
            return "textarea"
        if tag == "select" or ftype == "select-one":
            return "dropdown"
        if ftype == "checkbox":
            return "checkbox"
        if ftype == "radio":
            return "radio"
        if ftype == "date" or "dob" in lbl or "date of birth" in lbl:
            return "date"
        return "text"

    @classmethod
    async def resolve_field_value(
        cls,
        field_label: str,
        field_type: str,
        job_description: str,
        session: AsyncSession
    ) -> Tuple[Optional[str], str]:
        """
        Returns (resolved_value, source_name).
        If unresolvable, returns (None, 'needs_you').
        """
        lbl = field_label.lower().strip()

        # Step (1): Check Fixed Profile
        stmt_prof = select(FixedProfile).limit(1)
        res_prof = await session.execute(stmt_prof)
        prof = res_prof.scalars().first()

        if prof:
            if any(k in lbl for k in ["full name", "your name", "candidate name", "first name"]) and prof.full_name:
                return prof.full_name, "fixed_profile"
            if "email" in lbl and prof.email:
                return prof.email, "fixed_profile"
            if any(k in lbl for k in ["phone", "mobile", "contact number"]) and prof.phone:
                return prof.phone, "fixed_profile"
            if any(k in lbl for k in ["notice period", "notice days"]) and prof.notice_period_days is not None:
                return str(prof.notice_period_days), "fixed_profile"
            if any(k in lbl for k in ["current ctc", "current salary", "current compensation"]) and prof.current_ctc:
                return prof.current_ctc, "fixed_profile"
            if any(k in lbl for k in ["expected ctc", "expected salary", "expected compensation"]) and prof.expected_ctc:
                return prof.expected_ctc, "fixed_profile"
            if any(k in lbl for k in ["total experience", "years of experience"]) and prof.total_experience_years is not None:
                return str(prof.total_experience_years), "fixed_profile"
            if any(k in lbl for k in ["date of birth", "dob", "birth date"]) and prof.date_of_birth:
                return prof.date_of_birth, "fixed_profile"
            if any(k in lbl for k in ["city", "current location", "residence"]) and prof.location:
                return prof.location, "fixed_profile"
            if "github" in lbl and prof.links and prof.links.get("github"):
                return prof.links["github"], "fixed_profile"
            if "linkedin" in lbl and prof.links and prof.links.get("linkedin"):
                return prof.links["linkedin"], "fixed_profile"
            if "portfolio" in lbl and prof.links and prof.links.get("portfolio"):
                return prof.links["portfolio"], "fixed_profile"

        # Step (2): Check Verified Vault Facts via Grounded Engine
        stmt_facts = select(VaultFact).where(VaultFact.verified == True)
        facts = (await session.execute(stmt_facts)).scalars().all()

        if facts:
            ans_res = await GroundedAnswerEngine.generate_answer(
                question=field_label,
                job_description=job_description,
                facts=facts,
                profile=prof
            )
            if ans_res["status"] == "grounded" and not ans_res["answer"].startswith("UNKNOWN"):
                # Clean citations from the field fill
                clean_val = re.sub(r"\[(FACT-[A-Z]+-[a-z0-9-]+|FIXED-PROFILE)\]", "", ans_res["answer"]).strip()
                source_tag = ", ".join(ans_res.get("citations", [])) or "vault_fact"
                return clean_val, source_tag

        # Step (3): Check previously saved answers in saved_qa table
        norm_q = re.sub(r"[^\w\s]", "", lbl).strip()
        stmt_qa = select(SavedQuestionAnswer).where(SavedQuestionAnswer.normalized_question == norm_q)
        res_qa = await session.execute(stmt_qa)
        saved = res_qa.scalars().first()
        if saved and saved.answer:
            return saved.answer, "saved_qa"

        # Step (4): Unknown -> Ask User ('Needs You')
        return None, "needs_you"
