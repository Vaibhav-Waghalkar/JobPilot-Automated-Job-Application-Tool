import json
import re
from typing import Dict, Any, List
from backend.llm.router import llm_router
from backend.vault.models import VaultFact, Resume

MATCH_PROMPT = """
You are the JobPilot Matching Engine. Evaluate how well the candidate matches the job description.
CRITICAL RULE: Base your evaluation ONLY on the Candidate Skills and Experience provided below. Do NOT assume any skills not listed.

CANDIDATE SKILLS & EXPERIENCE:
{candidate_profile}

JOB TITLE: {title}
COMPANY: {company}
JOB DESCRIPTION:
{job_description}

Return ONLY a valid JSON object with EXACTLY this structure:
{{
  "score": <integer from 0 to 100>,
  "matched_skills": [<list of candidate skills that directly match JD requirements>],
  "gaps": [<list of requirements in the JD that candidate lacks>],
  "analysis": "<short 2-sentence rationale>"
}}
"""

class JobMatcher:
    """
    Evaluates job description against authoritative candidate vault facts
    and scores match from 0-100 with matched skills and gaps.
    """

    @classmethod
    async def match_job(cls, title: str, company: str, job_description: str, facts: List[VaultFact]) -> Dict[str, Any]:
        # Aggregate candidate skills and experience facts
        relevant_facts = [f for f in facts if f.section in ["skill", "experience", "project"]]
        profile_snippets = []
        for f in relevant_facts:
            profile_snippets.append(f"[{f.id}] {f.title}:\n{f.content}")

        profile_text = "\n\n".join(profile_snippets)

        prompt = MATCH_PROMPT.format(
            candidate_profile=profile_text[:4000],
            title=title,
            company=company,
            job_description=job_description[:3000]
        )

        resp = await llm_router.generate(prompt=prompt, system_prompt="You are a strict, objective technical recruiter.")
        text = resp.text.strip()

        # Clean JSON markdown if wrapped
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            parsed = json.loads(text)
            score = int(parsed.get("score", 50))
            return {
                "score": max(0, min(100, score)),
                "matched_skills": parsed.get("matched_skills", []),
                "gaps": parsed.get("gaps", []),
                "analysis": parsed.get("analysis", "Evaluation completed.")
            }
        except Exception:
            # Deterministic regex keyword overlap fallback
            jd_lower = job_description.lower()
            matched = []
            for f in facts:
                if f.section == "skill" and f.title.replace("Skill: ", "").lower() in jd_lower:
                    matched.append(f.title.replace("Skill: ", ""))

            fallback_score = 75 if len(matched) >= 3 else (50 if len(matched) >= 1 else 30)
            return {
                "score": fallback_score,
                "matched_skills": matched,
                "gaps": ["Requires domain review"],
                "analysis": f"Evaluated based on {len(matched)} matching vault skills."
            }

    @classmethod
    def select_best_resume(cls, job_title: str, matched_skills: List[str], resumes: List[Resume]) -> Resume:
        """
        Auto-selects best-fit resume version based on role tags and skills overlap.
        """
        if not resumes:
            return None

        title_lower = job_title.lower()
        skills_str = " ".join(matched_skills).lower()

        best_resume = resumes[0]
        best_score = -1

        for r in resumes:
            tag_lower = r.role_tag.lower()
            score = 0
            # Role tag match in job title
            if tag_lower in title_lower:
                score += 10
            # Role tag match in matched skills
            if tag_lower in skills_str:
                score += 5
            # Higher version preference
            score += (r.version * 0.1)

            if score > best_score:
                best_score = score
                best_resume = r

        return best_resume
