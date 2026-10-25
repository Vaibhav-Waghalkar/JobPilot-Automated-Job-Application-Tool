import re
from typing import List, Set, Tuple
from backend.vault.models import FixedProfile, VaultFact

class VaultAllowlist:
    """
    Extracts authoritative entities from the user's SQLite vault
    (technologies, company names, degrees, institutions, numbers/years)
    to perform deterministic code allowlist verification on generated outputs.
    """

    def __init__(self, profile: FixedProfile, facts: List[VaultFact]):
        self.profile = profile
        self.facts = facts
        self.allowed_technologies: Set[str] = set()
        self.allowed_companies: Set[str] = set()
        self.allowed_years_numbers: Set[str] = set()
        self._build_allowlist()

    def _build_allowlist(self):
        # Extract technologies & skills
        for f in self.facts:
            if f.section in ["skill", "project", "experience"]:
                # Title often has the skill or project name
                self.allowed_technologies.add(f.title.lower().replace("skill: ", "").replace("project: ", "").strip())
                if f.metadata_json:
                    # Skills from project stack
                    for stack_item in f.metadata_json.get("stack", []):
                        self.allowed_technologies.add(stack_item.lower().strip())
                    # Company names
                    if "company" in f.metadata_json:
                        self.allowed_companies.add(f.metadata_json["company"].lower().strip())
                    if "issuer" in f.metadata_json:
                        self.allowed_companies.add(f.metadata_json["issuer"].lower().strip())
                    if "institution" in f.metadata_json:
                        self.allowed_companies.add(f.metadata_json["institution"].lower().strip())

        # Fixed profile additions
        if self.profile:
            if self.profile.full_name:
                self.allowed_companies.add(self.profile.full_name.lower())
            if self.profile.notice_period_days:
                self.allowed_years_numbers.add(str(self.profile.notice_period_days))
            if self.profile.total_experience_years:
                self.allowed_years_numbers.add(str(self.profile.total_experience_years))

        # Add common conversational English stop words so they aren't flagged as tech names
        self.stop_words = {
            "the", "and", "with", "for", "from", "that", "this", "have", "been", "team",
            "developed", "system", "designed", "built", "managed", "created", "led", "reduced",
            "increased", "work", "role", "years", "months", "experience", "engineering", "lead",
            "senior", "software", "backend", "fullstack", "solutions", "application", "daily"
        }

    def check_output_allowlist(self, text: str) -> Tuple[bool, List[str]]:
        """
        Scans generated output for suspicious ungrounded capital acronyms or claims.
        Returns (is_valid, list_of_violations).
        """
        violations = []
        # Check for ungrounded uppercase tech acronyms like GCP, K8S, AWS if not in vault
        capital_words = set(re.findall(r"\b[A-Z]{2,}\b", text))
        
        # Allowed acronyms derived from vault
        allowed_acronyms = set()
        for t in self.allowed_technologies:
            for word in t.upper().split():
                if len(word) >= 2:
                    allowed_acronyms.add(word)
        for c in self.allowed_companies:
            for word in c.upper().split():
                if len(word) >= 2:
                    allowed_acronyms.add(word)

        # Common acceptable acronyms in writing (ID, API, REST, QA, HR, etc.)
        whitelist_generic = {"API", "REST", "QA", "HR", "SQL", "UI", "UX", "ID", "FACT", "EXP", "PRJ", "SKL", "EDU", "CRT"}

        for cw in capital_words:
            if cw not in whitelist_generic and cw not in allowed_acronyms:
                # If it looks like a specific ungrounded tech claim
                if cw in {"GCP", "AZURE", "DJANGO", "ANGULAR", "KAFKA", "HADOOP", "SPARK", "GRAPHQL", "SWIFT"}:
                    violations.append(f"Ungrounded technology acronym: {cw}")

        return len(violations) == 0, violations
