import re
from typing import Tuple, Optional
from backend.vault.models import JobPreference
from backend.adapters.base_adapter import DiscoveredJob

def parse_salary_to_annual(salary_text: Optional[str]) -> Optional[float]:
    """
    Parses common Indian and international salary formats to annual INR float.
    e.g., '12-18 LPA', '15,00,000 / year', '80,000 / month'
    """
    if not salary_text:
        return None
    text = salary_text.lower()

    # Case: LPA (Lakhs per annum)
    lpa_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)?\s*(\d+(?:\.\d+)?)\s*lpa", text)
    if lpa_match:
        # Take the lower bound or single number
        val = float(lpa_match.group(1))
        return val * 100000

    single_lpa = re.search(r"(\d+(?:\.\d+)?)\s*lpa", text)
    if single_lpa:
        return float(single_lpa.group(1)) * 100000

    # Case: monthly amount
    if "month" in text:
        nums = re.findall(r"\d[\d,]*", text)
        if nums:
            raw = nums[0].replace(",", "")
            return float(raw) * 12

    # Case: direct yearly amount
    nums = re.findall(r"\d[\d,]*", text)
    if nums:
        raw = nums[0].replace(",", "")
        if float(raw) > 50000:
            return float(raw)

    return None

def apply_hard_filters(job: DiscoveredJob, prefs: Optional[JobPreference], applied_urls: set) -> Tuple[bool, Optional[str]]:
    """
    Hard filters executed in deterministic code before any LLM is called:
    - Already applied
    - Blacklisted companies
    - Salary below min
    - Location mismatch
    - Role mismatch
    """
    # 1. Already applied
    if job.apply_url in applied_urls:
        return False, "Already applied or logged in vault"

    if not prefs:
        return True, None

    # 2. Blacklisted companies
    blacklist = [b.lower().strip() for b in (prefs.blacklisted_companies or [])]
    for b in blacklist:
        if b and b in job.company.lower():
            return False, f"Company '{job.company}' is in blacklist"

    # 3. Target roles filter
    target_roles = [r.lower().strip() for r in (prefs.target_roles or [])]
    if target_roles:
        title_lower = job.title.lower()
        # Check if any target role keyword is in the job title
        matches_role = any(r in title_lower or any(word in title_lower for word in r.split()) for r in target_roles)
        if not matches_role:
            return False, f"Job title '{job.title}' does not match target roles ({', '.join(target_roles[:3])})"

    # 4. Location & Work mode filter
    pref_locations = [loc.lower().strip() for loc in (prefs.preferred_locations or [])]
    if pref_locations:
        loc_lower = job.location.lower()
        is_remote_friendly = "remote" in loc_lower or "anywhere" in loc_lower or "work from home" in loc_lower
        is_loc_match = any(loc in loc_lower for loc in pref_locations)
        if not (is_loc_match or (is_remote_friendly and "remote" in pref_locations)):
            return False, f"Location '{job.location}' does not match preferred locations"

    # 5. Salary range filter (only if salary is disclosed)
    if prefs.min_salary:
        parsed_annual = parse_salary_to_annual(job.salary_raw)
        if parsed_annual and parsed_annual < (prefs.min_salary * 0.85): # 15% grace margin for negotiation
            return False, f"Salary {job.salary_raw} is below minimum requirement of {prefs.min_salary}"

    return True, None
