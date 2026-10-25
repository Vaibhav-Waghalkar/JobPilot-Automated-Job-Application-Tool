import json
import hashlib
import re
from typing import Dict, Any, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.vault.models import FixedProfile, VaultFact, JobPreference
from backend.vault.vector_store import upsert_vault_fact_embedding

def compute_hash(content: str) -> str:
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)

class ProfileImporter:
    """
    Imports master profile JSON (or dict) into SQLite & ChromaDB.
    Maintains deterministic stable fact IDs and only updates changed items.
    """

    @classmethod
    async def import_profile_data(cls, data: Dict[str, Any], session: AsyncSession) -> Dict[str, Any]:
        stats = {
            "fixed_profile_updated": False,
            "preferences_updated": False,
            "facts_created": 0,
            "facts_updated": 0,
            "facts_unchanged": 0,
            "total_facts": 0
        }

        # 1. Update Fixed Profile (Authoritative, never LLM generated)
        fixed_data = data.get("fixed_profile", {})
        if fixed_data:
            stmt = select(FixedProfile).limit(1)
            result = await session.execute(stmt)
            profile_row = result.scalars().first()
            if not profile_row:
                profile_row = FixedProfile()
                session.add(profile_row)

            profile_row.full_name = fixed_data.get("full_name", profile_row.full_name or "")
            profile_row.date_of_birth = fixed_data.get("date_of_birth", profile_row.date_of_birth)
            profile_row.phone = fixed_data.get("phone", profile_row.phone)
            profile_row.email = fixed_data.get("email", profile_row.email)
            profile_row.location = fixed_data.get("location", profile_row.location)
            profile_row.notice_period_days = int(fixed_data.get("notice_period_days", profile_row.notice_period_days or 0))
            profile_row.current_ctc = fixed_data.get("current_ctc", profile_row.current_ctc)
            profile_row.expected_ctc = fixed_data.get("expected_ctc", profile_row.expected_ctc)
            profile_row.total_experience_years = float(fixed_data.get("total_experience_years", profile_row.total_experience_years or 0.0))
            profile_row.links = fixed_data.get("links", profile_row.links or {})
            profile_row.languages = fixed_data.get("languages", profile_row.languages or [])
            stats["fixed_profile_updated"] = True

        # 2. Update Job Preferences
        pref_data = data.get("job_preferences", {})
        if pref_data:
            stmt = select(JobPreference).limit(1)
            result = await session.execute(stmt)
            pref_row = result.scalars().first()
            if not pref_row:
                pref_row = JobPreference()
                session.add(pref_row)

            pref_row.target_roles = pref_data.get("target_roles", pref_row.target_roles or [])
            pref_row.min_salary = pref_data.get("min_salary", pref_row.min_salary)
            pref_row.max_salary = pref_data.get("max_salary", pref_row.max_salary)
            pref_row.preferred_locations = pref_data.get("preferred_locations", pref_row.preferred_locations or [])
            pref_row.work_modes = pref_data.get("work_modes", pref_row.work_modes or [])
            pref_row.must_have_skills = pref_data.get("must_have_skills", pref_row.must_have_skills or [])
            pref_row.blacklisted_companies = pref_data.get("blacklisted_companies", pref_row.blacklisted_companies or [])
            pref_row.daily_caps = pref_data.get("daily_caps", pref_row.daily_caps or {})
            pref_row.default_match_threshold = pref_data.get("default_match_threshold", pref_row.default_match_threshold or 70)
            stats["preferences_updated"] = True

        # 3. Process granular fact sections with stable IDs
        raw_facts: List[Tuple[str, str, str, str, Dict[str, Any]]] = []
        # format: (fact_id, section, title, content, metadata)

        # Personal summary facts (if any)
        if "personal_summary" in data:
            raw_facts.append((
                "FACT-PER-summary",
                "personal",
                "Personal Professional Summary",
                str(data["personal_summary"]),
                {"type": "summary"}
            ))

        # Education
        for idx, edu in enumerate(data.get("education", []), start=1):
            inst_slug = slugify(edu.get("institution", f"edu-{idx}"))[:20]
            fid = f"FACT-EDU-{inst_slug}"
            title = f"{edu.get('degree', 'Degree')} at {edu.get('institution', 'Institution')}"
            content = (
                f"Degree: {edu.get('degree', '')}\n"
                f"Institution: {edu.get('institution', '')}\n"
                f"Field: {edu.get('field_of_study', '')}\n"
                f"Duration: {edu.get('start_year', '')} - {edu.get('end_year', '')}\n"
                f"Grade: {edu.get('grade', '')}\n"
                f"Highlights: {edu.get('highlights', '')}"
            )
            raw_facts.append((fid, "education", title, content, edu))

        # Experience
        for idx, exp in enumerate(data.get("experience", []), start=1):
            comp_slug = slugify(exp.get("company", f"comp-{idx}"))[:20]
            fid = f"FACT-EXP-{comp_slug}"
            title = f"{exp.get('role', 'Role')} at {exp.get('company', 'Company')}"
            achievements_text = "\n".join(f"- {a}" for a in exp.get("achievements", []))
            content = (
                f"Role: {exp.get('role', '')}\n"
                f"Company: {exp.get('company', '')}\n"
                f"Duration: {exp.get('start_date', '')} to {exp.get('end_date', '')}\n"
                f"Location: {exp.get('location', '')}\n"
                f"Summary: {exp.get('summary', '')}\n"
                f"Achievements:\n{achievements_text}"
            )
            raw_facts.append((fid, "experience", title, content, exp))

        # Projects
        for idx, prj in enumerate(data.get("projects", []), start=1):
            prj_slug = slugify(prj.get("name", f"proj-{idx}"))[:20]
            fid = f"FACT-PRJ-{prj_slug}"
            title = f"Project: {prj.get('name', '')}"
            stack_text = ", ".join(prj.get("stack", []))
            links_dict = prj.get("links", {})
            links_text = ", ".join(f"{k}: {v}" for k, v in links_dict.items())
            content = (
                f"Project: {prj.get('name', '')}\n"
                f"Role: {prj.get('role', '')}\n"
                f"Tech Stack: {stack_text}\n"
                f"Purpose: {prj.get('purpose', '')}\n"
                f"Problem: {prj.get('problem', '')}\n"
                f"Challenges: {prj.get('challenges', '')}\n"
                f"Outcomes: {prj.get('outcomes', '')}\n"
                f"Links: {links_text}"
            )
            raw_facts.append((fid, "project", title, content, prj))

        # Skills
        for idx, sk in enumerate(data.get("skills", []), start=1):
            sk_slug = slugify(sk.get("name", f"skill-{idx}"))[:20]
            fid = f"FACT-SKL-{sk_slug}"
            title = f"Skill: {sk.get('name', '')}"
            projects_str = ", ".join(sk.get("projects_or_jobs", []))
            content = (
                f"Skill: {sk.get('name', '')}\n"
                f"Category: {sk.get('category', 'General')}\n"
                f"Proficiency Level: {sk.get('level', 'Intermediate')}\n"
                f"Years of Experience: {sk.get('years', 0)}\n"
                f"Applied in: {projects_str}"
            )
            raw_facts.append((fid, "skill", title, content, sk))

        # STAR Stories
        for idx, star in enumerate(data.get("star_stories", []), start=1):
            star_slug = slugify(star.get("title", f"story-{idx}"))[:20]
            fid = f"FACT-STAR-{star_slug}"
            title = f"STAR: {star.get('title', '')}"
            skills_shown = ", ".join(star.get("skills_shown", []))
            content = (
                f"Title: {star.get('title', '')}\n"
                f"Situation: {star.get('situation', '')}\n"
                f"Task: {star.get('task', '')}\n"
                f"Action: {star.get('action', '')}\n"
                f"Result: {star.get('result', '')}\n"
                f"Skills Demonstrated: {skills_shown}"
            )
            raw_facts.append((fid, "star_story", title, content, star))

        # Certifications
        for idx, cert in enumerate(data.get("certifications", []), start=1):
            cert_slug = slugify(cert.get("title", f"cert-{idx}"))[:20]
            fid = f"FACT-CRT-{cert_slug}"
            title = f"Certification: {cert.get('title', '')}"
            content = (
                f"Certification: {cert.get('title', '')}\n"
                f"Issuer: {cert.get('issuer', '')}\n"
                f"Issue Date: {cert.get('issue_date', '')}\n"
                f"Expiry: {cert.get('expiry_date', 'N/A')}\n"
                f"ID: {cert.get('credential_id', '')}\n"
                f"Link: {cert.get('verification_link', '')}"
            )
            raw_facts.append((fid, "certification", title, content, cert))

        # Standard Q&A
        for idx, qa in enumerate(data.get("standard_qa", []), start=1):
            q_slug = slugify(qa.get("question", f"qa-{idx}"))[:20]
            fid = f"FACT-QA-{q_slug}"
            title = f"Q&A: {qa.get('question', '')}"
            content = f"Question: {qa.get('question', '')}\nAnswer: {qa.get('answer', '')}"
            raw_facts.append((fid, "standard_qa", title, content, qa))

        stats["total_facts"] = len(raw_facts)

        # Upsert facts with hash check
        for fid, section, title, content, meta in raw_facts:
            chash = compute_hash(content)
            stmt = select(VaultFact).where(VaultFact.id == fid)
            res = await session.execute(stmt)
            existing_fact = res.scalars().first()

            if not existing_fact:
                new_fact = VaultFact(
                    id=fid,
                    section=section,
                    title=title,
                    content=content,
                    metadata_json=meta,
                    content_hash=chash
                )
                session.add(new_fact)
                upsert_vault_fact_embedding(fid, content, {"section": section, "title": title})
                stats["facts_created"] += 1
            elif existing_fact.content_hash != chash:
                existing_fact.title = title
                existing_fact.content = content
                existing_fact.metadata_json = meta
                existing_fact.content_hash = chash
                upsert_vault_fact_embedding(fid, content, {"section": section, "title": title})
                stats["facts_updated"] += 1
            else:
                stats["facts_unchanged"] += 1

        await session.commit()
        return stats
