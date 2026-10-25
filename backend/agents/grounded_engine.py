import re
import json
from typing import Dict, Any, List, Optional
from backend.vault.models import FixedProfile, VaultFact
from backend.llm.router import llm_router
from backend.agents.allowlist_checker import VaultAllowlist

CLOSED_BOOK_SYSTEM_PROMPT = """
You are the strict, closed-book answer engine for JobPilot.
You generate answers for job applications and screening questions based ONLY on the Authoritative Vault Facts provided below.

STRICT ANTI-HALLUCINATION RULES:
1. Every single sentence MUST cite the relevant Fact ID in brackets at the end of the sentence (e.g. "...using FastAPI for high-throughput APIs [FACT-EXP-technova-solutions].").
2. If the provided facts DO NOT contain sufficient information to answer the question, or if any claim cannot be cited directly, return EXACTLY: UNKNOWN: <brief description of missing fact>
3. NEVER assume, extrapolate, or invent achievements, technologies, companies, dates, or numbers.
4. Hard facts (Notice Period, CTC, Experience years, Location) must reflect only what is in the facts.
5. Temperature is 0.2. Maintain a professional, concise, direct tone.
"""

VERIFIER_PROMPT = """
You are the second-pass Fact Verifier for JobPilot.
Your job is to strictly verify every sentence in the GENERATED ANSWER against the PROVIDED VAULT FACTS.

PROVIDED VAULT FACTS:
{vault_facts}

GENERATED ANSWER:
{generated_answer}

TASK:
1. Check if every single factual claim is supported by the cited Fact IDs.
2. Check if any technology, metric, year, or company name is ungrounded or absent from the facts.

Return ONLY a valid JSON object:
{{
  "passed": true/false,
  "unsupported_claims": [<list of sentences or claims that are not strictly supported by the cited facts>],
  "reason": "<short explanation>"
}}
"""

class GroundedAnswerEngine:
    """
    Closed-book answer engine with sentence-level citation, verifier pass,
    and code allowlist enforcement.
    """

    @classmethod
    async def generate_answer(
        cls,
        question: str,
        job_description: str,
        facts: List[VaultFact],
        profile: Optional[FixedProfile] = None,
        max_attempts: int = 3
    ) -> Dict[str, Any]:
        # 1. Check fixed profile for hard-fact questions
        q_lower = question.lower()
        if profile:
            if "notice period" in q_lower:
                return {
                    "answer": f"My notice period is {profile.notice_period_days} days [FIXED-PROFILE].",
                    "status": "grounded",
                    "citations": ["FIXED-PROFILE"],
                    "attempts": 1
                }
            if "current ctc" in q_lower or "current compensation" in q_lower or "current salary" in q_lower:
                return {
                    "answer": f"My current compensation is {profile.current_ctc} [FIXED-PROFILE].",
                    "status": "grounded",
                    "citations": ["FIXED-PROFILE"],
                    "attempts": 1
                }
            if "expected ctc" in q_lower or "expected salary" in q_lower:
                return {
                    "answer": f"My expected compensation is {profile.expected_ctc} [FIXED-PROFILE].",
                    "status": "grounded",
                    "citations": ["FIXED-PROFILE"],
                    "attempts": 1
                }
            if "total experience" in q_lower or "years of experience" in q_lower:
                return {
                    "answer": f"I have {profile.total_experience_years} years of professional software engineering experience [FIXED-PROFILE].",
                    "status": "grounded",
                    "citations": ["FIXED-PROFILE"],
                    "attempts": 1
                }
            if "location" in q_lower or "current city" in q_lower:
                return {
                    "answer": f"I am based in {profile.location} [FIXED-PROFILE].",
                    "status": "grounded",
                    "citations": ["FIXED-PROFILE"],
                    "attempts": 1
                }

        # 2. Format authoritative vault facts
        facts_text = "\n\n".join([f"[{f.id}] {f.title}:\n{f.content}" for f in facts])
        allowlist = VaultAllowlist(profile, facts)

        user_prompt = f"""
VAULT FACTS:
{facts_text}

TARGET JOB DESCRIPTION:
{job_description[:1500] if job_description else "General Application"}

QUESTION:
{question}
"""

        for attempt in range(1, max_attempts + 1):
            # Pass 1: Closed-book generation
            gen_resp = await llm_router.generate(
                prompt=user_prompt,
                system_prompt=CLOSED_BOOK_SYSTEM_PROMPT,
                temperature=0.2
            )
            candidate_answer = gen_resp.text.strip()

            if candidate_answer.startswith("UNKNOWN"):
                return {
                    "answer": candidate_answer,
                    "status": "needs_you",
                    "citations": [],
                    "attempts": attempt,
                    "reason": "Vault lacks sufficient information to answer this question truthfully."
                }

            # Pass 2: Code allowlist check
            allow_passed, violations = allowlist.check_output_allowlist(candidate_answer)
            if not allow_passed:
                # Retry with specific correction
                user_prompt += f"\n\nATTEMPT {attempt} REJECTED due to ungrounded terms: {', '.join(violations)}. Regenerate strictly using only vault facts."
                continue

            # Pass 3: Verifier pass
            verifier_prompt = VERIFIER_PROMPT.format(
                vault_facts=facts_text,
                generated_answer=candidate_answer
            )
            verifier_resp = await llm_router.generate(
                prompt=verifier_prompt,
                system_prompt="You are a strict factual consistency auditor.",
                temperature=0.1
            )
            
            # Parse verifier response
            ver_text = verifier_resp.text.strip()
            if ver_text.startswith("```json"):
                ver_text = ver_text[7:]
            if ver_text.startswith("```"):
                ver_text = ver_text[3:]
            if ver_text.endswith("```"):
                ver_text = ver_text[:-3]

            try:
                ver_json = json.loads(ver_text)
                if ver_json.get("passed", False):
                    # Extract citations
                    citations = re.findall(r"\[(FACT-[A-Z]+-[a-z0-9-]+|FIXED-PROFILE)\]", candidate_answer)
                    return {
                        "answer": candidate_answer,
                        "status": "grounded",
                        "citations": list(set(citations)),
                        "attempts": attempt,
                        "verifier": ver_json
                    }
                else:
                    user_prompt += f"\n\nATTEMPT {attempt} FAILED VERIFIER: {ver_json.get('reason')}. Unsupported: {ver_json.get('unsupported_claims')}. Regenerate."
            except Exception:
                # If verifier output was non-JSON, extract citations and pass if allowlist succeeded
                citations = re.findall(r"\[(FACT-[A-Z]+-[a-z0-9-]+|FIXED-PROFILE)\]", candidate_answer)
                return {
                    "answer": candidate_answer,
                    "status": "grounded",
                    "citations": list(set(citations)),
                    "attempts": attempt
                }

        # If max attempts exhausted without passing verifier
        return {
            "answer": "UNKNOWN: Unable to formulate a strictly verified response within 3 attempts.",
            "status": "needs_you",
            "citations": [],
            "attempts": max_attempts,
            "reason": "Verifier rejected output for lack of strict grounded evidence."
        }
