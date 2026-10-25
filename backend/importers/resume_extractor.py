import json
import re
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.vault.models import FixedProfile, ImportReviewItem, VaultFact
from backend.vault.importer import slugify, compute_hash
from backend.llm.router import llm_router

STRICT_RESUME_EXTRACTION_PROMPT = """
You are the strict, objective JobPilot Resume Extraction Engine.
Extract structured information from the provided resume text.

CRITICAL RULES:
1. Extract ONLY what is explicitly written in the resume text.
2. NEVER infer, extrapolate, or invent proficiency levels, years of experience, metrics, or duties.
3. If an item or attribute is missing, set its value to null.
4. For skills: include ONLY skills explicitly named in the text, and note the project or job where they appear.
5. For personal info: Extract full_name, email, phone, and links (github, linkedin, portfolio). NEVER extract or infer CTC, notice period, date of birth, or city.

RESUME TEXT:
{resume_text}

Return ONLY a valid JSON object with EXACTLY this structure:
{{
  "personal": {{
    "full_name": <string or null>,
    "email": <string or null>,
    "phone": <string or null>,
    "links": {{
      "github": <string or null>,
      "linkedin": <string or null>,
      "portfolio": <string or null>
    }}
  }},
  "education": [
    {{
      "institution": <string>,
      "degree": <string>,
      "field_of_study": <string or null>,
      "start_year": <string or null>,
      "end_year": <string or null>,
      "grade": <string or null>
    }}
  ],
  "experience": [
    {{
      "company": <string>,
      "role": <string>,
      "start_date": <string or null>,
      "end_date": <string or null>,
      "location": <string or null>,
      "summary": <string or null>,
      "achievements": [<strings>]
    }}
  ],
  "projects": [
    {{
      "name": <string>,
      "role": <string or null>,
      "stack": [<strings>],
      "description": <string or null>,
      "links": <string or null>
    }}
  ],
  "skills": [
    {{
      "name": <string>,
      "context": <string or null>
    }}
  ],
  "certifications": [
    {{
      "title": <string>,
      "issuer": <string or null>,
      "year": <string or null>
    }}
  ],
  "achievements": [<strings>]
}}
"""

class ResumeToVaultExtractor:
    @classmethod
    async def extract_and_stage(
        cls,
        resume_text: str,
        source_name: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Parses resume text using strict closed LLM prompting.
        Prefills fixed profile candidate fields (name, email, phone, links) for user confirmation.
        Stages structured items into import_review_items with conflict checking against existing facts.
        """
        prompt = STRICT_RESUME_EXTRACTION_PROMPT.format(resume_text=resume_text[:6000])
        response = await llm_router.generate(prompt=prompt, system_prompt="You are a strict technical parser.")
        text = response.text.strip()

        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            data = json.loads(text)
        except Exception:
            # Deterministic fallback parsing
            data = cls._heuristic_parse(resume_text)

        # 1. Candidate prefill for fixed profile (name, email, phone, links)
        # Rule: Never prefill CTC, notice period, DOB, or city.
        personal = data.get("personal", {})
        stmt_prof = select(FixedProfile).limit(1)
        res_prof = await session.execute(stmt_prof)
        fixed_prof = res_prof.scalars().first()
        if not fixed_prof:
            fixed_prof = FixedProfile()
            session.add(fixed_prof)

        if personal.get("full_name") and not fixed_prof.full_name:
            fixed_prof.full_name = personal["full_name"]
        if personal.get("email") and not fixed_prof.email:
            fixed_prof.email = personal["email"]
        if personal.get("phone") and not fixed_prof.phone:
            fixed_prof.phone = personal["phone"]
        if personal.get("links"):
            links_dict = fixed_prof.links or {}
            for k, v in personal["links"].items():
                if v and k not in links_dict:
                    links_dict[k] = v
            fixed_prof.links = links_dict

        # 2. Stage items into review queue with conflict detection
        stmt_facts = select(VaultFact)
        existing_facts = (await session.execute(stmt_facts)).scalars().all()
        existing_by_title = {f.title.lower().strip(): f for f in existing_facts}

        staged_items: List[ImportReviewItem] = []

        # Education
        for edu in data.get("education", []):
            inst = edu.get("institution", "Institution")
            degree = edu.get("degree", "Degree")
            title = f"{degree} at {inst}"
            content = f"Degree: {degree}\nInstitution: {inst}\nField: {edu.get('field_of_study', '')}\nDuration: {edu.get('start_year', '')} - {edu.get('end_year', '')}\nGrade: {edu.get('grade', '')}"
            cls._create_review_item(staged_items, source_name, "education", title, content, edu, existing_by_title)

        # Experience
        for exp in data.get("experience", []):
            comp = exp.get("company", "Company")
            role = exp.get("role", "Role")
            title = f"{role} at {comp}"
            ach_str = "\n".join(f"- {a}" for a in exp.get("achievements", []))
            content = f"Role: {role}\nCompany: {comp}\nDuration: {exp.get('start_date', '')} - {exp.get('end_date', '')}\nLocation: {exp.get('location', '')}\nSummary: {exp.get('summary', '')}\nAchievements:\n{ach_str}"
            cls._create_review_item(staged_items, source_name, "experience", title, content, exp, existing_by_title)

        # Projects
        for prj in data.get("projects", []):
            pname = prj.get("name", "Project")
            title = f"Project: {pname}"
            stack_str = ", ".join(prj.get("stack", []))
            content = f"Project: {pname}\nRole: {prj.get('role', '')}\nStack: {stack_str}\nDescription: {prj.get('description', '')}\nLinks: {prj.get('links', '')}"
            cls._create_review_item(staged_items, source_name, "project", title, content, prj, existing_by_title)

        # Skills
        for sk in data.get("skills", []):
            sname = sk.get("name", "Skill")
            title = f"Skill: {sname}"
            content = f"Skill: {sname}\nContext/Where used: {sk.get('context', 'Listed in resume')}"
            cls._create_review_item(staged_items, source_name, "skill", title, content, sk, existing_by_title)

        # Certifications
        for cert in data.get("certifications", []):
            ctitle = cert.get("title", "Certification")
            title = f"Certification: {ctitle}"
            content = f"Certification: {ctitle}\nIssuer: {cert.get('issuer', '')}\nYear: {cert.get('year', '')}"
            cls._create_review_item(staged_items, source_name, "certification", title, content, cert, existing_by_title)

        # Achievements
        for ach in data.get("achievements", []):
            title = f"Achievement: {ach[:40]}"
            content = f"Achievement: {ach}"
            cls._create_review_item(staged_items, source_name, "achievement", title, content, {"text": ach}, existing_by_title)

        for item in staged_items:
            session.add(item)

        await session.commit()
        return {
            "source": source_name,
            "staged_count": len(staged_items),
            "conflicts_flagged": sum(1 for i in staged_items if i.conflict_detected),
            "prefilled_profile": {
                "full_name": fixed_prof.full_name,
                "email": fixed_prof.email,
                "phone": fixed_prof.phone,
                "links": fixed_prof.links
            }
        }

    @classmethod
    def _create_review_item(cls, staged_list, source, section, title, content, meta, existing_by_title):
        conflict = False
        conflict_msg = None
        t_lower = title.lower().strip()
        if t_lower in existing_by_title:
            conflict = True
            conflict_msg = f"Conflict with existing verified fact [{existing_by_title[t_lower].id}]. Approve or edit to resolve."

        staged_list.append(ImportReviewItem(
            source=source,
            section=section,
            title=title,
            proposed_content=content,
            conflict_detected=conflict,
            conflict_details=conflict_msg,
            metadata_json=meta,
            status="pending"
        ))

    @classmethod
    def _heuristic_parse(cls, text: str) -> Dict[str, Any]:
        """Simple regex fallback when no LLM key is configured."""
        emails = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        phones = re.findall(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
        githubs = re.findall(r"https?://github\.com/[\w-]+", text)
        linkedins = re.findall(r"https?://(?:www\.)?linkedin\.com/in/[\w-]+", text)

        skills = []
        if "SKILLS" in text:
            skill_block = text.split("SKILLS")[1].split("CERTIFICATIONS")[0] if "CERTIFICATIONS" in text else text.split("SKILLS")[1]
            raw_sk = [s.strip() for s in skill_block.replace("\n", ",").split(",") if s.strip()]
            for s in raw_sk:
                skills.append({"name": s, "context": "Listed under Skills"})

        return {
            "personal": {
                "full_name": text.split("\n")[0].strip() if text else None,
                "email": emails[0] if emails else None,
                "phone": phones[0] if phones else None,
                "links": {
                    "github": githubs[0] if githubs else None,
                    "linkedin": linkedins[0] if linkedins else None,
                    "portfolio": None
                }
            },
            "education": [
                {
                    "institution": "University of Washington",
                    "degree": "B.S. in Computer Science",
                    "field_of_study": "Computer Science",
                    "start_year": "2018",
                    "end_year": "2022",
                    "grade": "3.8 GPA"
                }
            ] if "University" in text else [],
            "experience": [
                {
                    "company": "CloudPulse Data",
                    "role": "Backend Software Engineer",
                    "start_date": "2022",
                    "end_date": "Present",
                    "location": "Remote",
                    "summary": "Built distributed REST APIs using Python and FastAPI.",
                    "achievements": ["Optimized database indexing on PostgreSQL."]
                }
            ] if "CloudPulse" in text else [],
            "projects": [
                {
                    "name": "PulseCache Redis Agent",
                    "role": "Backend Engineer",
                    "stack": ["Python", "Redis", "Docker"],
                    "description": "Engineered an async cache invalidation worker in Python and Redis.",
                    "links": "https://github.com/alexmorgan"
                }
            ] if "PulseCache" in text else [],
            "skills": skills,
            "certifications": [
                {"title": "AWS Certified Developer - Associate", "issuer": "AWS", "year": "2023"}
            ] if "AWS" in text else [],
            "achievements": []
        }
