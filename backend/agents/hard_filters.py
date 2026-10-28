import re
from typing import Tuple, Optional, Dict, Any
from backend.vault.models import JobPreference
from backend.adapters.base_adapter import DiscoveredJob

def parse_salary_and_stipend(salary_text: Optional[str], job_type: str = "job") -> Dict[str, Any]:
    """
    Parses salary/stipend text into structured representation.
    Handles:
    - LPA ranges: '5-8 LPA', '12 - 18 LPA', '6 LPA'
    - Monthly: '10,000 /month', 'Rs 15000-20000 per month', '₹ 25,000 / month'
    - Yearly: '5,00,000 - 8,00,000 / year'
    - Unpaid / performance-based / as per industry standards / competitive
    - Undisclosed / not disclosed / null / empty
    
    Returns:
    {
        "is_undisclosed": bool,
        "is_unpaid": bool,
        "annual_val": Optional[float],   # Upper bound or single value annual INR
        "monthly_val": Optional[float],  # Upper bound or single value monthly INR
        "lower_bound_annual": Optional[float],
        "raw": str
    }
    """
    if not salary_text or not salary_text.strip():
        return {
            "is_undisclosed": True,
            "is_unpaid": False,
            "annual_val": None,
            "monthly_val": None,
            "lower_bound_annual": None,
            "raw": ""
        }

    # Normalize Indian digit grouping and clean text
    # E.g. "1,50,000 - 2,20,000" or "1,50,00,000" if erroneously formatted
    # Check if string has repeated tokens (e.g. "1,50,000 - 2,20,000 1,50,000 - 2,20,000 /year")
    cleaned_input = salary_text.strip()
    # Deduplicate repeated half if present
    half = len(cleaned_input) // 2
    if len(cleaned_input) > 10 and cleaned_input[:half].strip() == cleaned_input[half:].strip():
        cleaned_input = cleaned_input[:half].strip()

    text = cleaned_input.lower().strip()

    # Check for unpaid indicators
    unpaid_keywords = ["unpaid", "un-paid", "0 stipend", "stipend: 0", "free internship", "no stipend"]
    if any(k in text for k in unpaid_keywords):
        return {
            "is_undisclosed": False,
            "is_unpaid": True,
            "min_val": 0.0,
            "max_val": 0.0,
            "annual_val": 0.0,
            "monthly_val": 0.0,
            "lower_bound_annual": 0.0,
            "raw": salary_text
        }

    # Check for undisclosed / vague / performance-based indicators
    undisclosed_keywords = [
        "not disclosed", "undisclosed", "confidential", "as per industry", 
        "industry standard", "best in industry", "competitive", "performance based",
        "performance-based", "incentive only", "incentives only", "negotiable", "tbd"
    ]
    if any(k in text for k in undisclosed_keywords) and not re.search(r"\d", text):
        return {
            "is_undisclosed": True,
            "is_unpaid": False,
            "min_val": None,
            "max_val": None,
            "annual_val": None,
            "monthly_val": None,
            "lower_bound_annual": None,
            "raw": salary_text
        }

    # Helper function to parse Indian formatted numbers with commas (e.g. 1,50,000 or 15000)
    def parse_inr_num(s: str) -> float:
        cleaned = s.replace(",", "").strip()
        return float(cleaned)

    # Case 1: LPA format e.g. "5-8 LPA", "6 LPA", "4.5 - 7.5 Lakhs", "5 to 8 LPA"
    lpa_range = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lac|lacs|lakh|lakhs)", text)
    if lpa_range:
        low = float(lpa_range.group(1)) * 100000
        high = float(lpa_range.group(2)) * 100000
        return {
            "is_undisclosed": False,
            "is_unpaid": False,
            "min_val": low,
            "max_val": high,
            "annual_val": high,
            "monthly_val": high / 12.0,
            "lower_bound_annual": low,
            "raw": salary_text
        }

    lpa_single = re.search(r"(\d+(?:\.\d+)?)\s*(?:lpa|lac|lacs|lakh|lakhs)", text)
    if lpa_single:
        val = float(lpa_single.group(1)) * 100000
        return {
            "is_undisclosed": False,
            "is_unpaid": False,
            "min_val": val,
            "max_val": val,
            "annual_val": val,
            "monthly_val": val / 12.0,
            "lower_bound_annual": val,
            "raw": salary_text
        }

    # Extract all comma-grouped or continuous numbers
    # E.g. "1,50,000" or "10,000" or "500000"
    num_matches = [m.group(0) for m in re.finditer(r"\d+(?:,\d+)*(?:\.\d+)?", text)]
    nums = [parse_inr_num(m) for m in num_matches]

    # Case 2: Monthly format e.g. "10000-15000 /month", "15000 / month", "10,000 /month"
    if "month" in text or "pm" in text or "/mo" in text:
        if nums:
            low_m = nums[0]
            high_m = nums[1] if len(nums) >= 2 and nums[0] < nums[1] else nums[0]
            return {
                "is_undisclosed": False,
                "is_unpaid": (high_m == 0),
                "min_val": low_m,
                "max_val": high_m,
                "annual_val": high_m * 12.0,
                "monthly_val": high_m,
                "lower_bound_annual": low_m * 12.0,
                "raw": salary_text
            }

    # Case 3: Direct yearly format or absolute numbers
    if nums:
        low = nums[0]
        high = nums[1] if len(nums) >= 2 and nums[0] < nums[1] else nums[0]

        is_yearly = ("year" in text or "annum" in text or "/yr" in text or "pa" in text)
        is_large = (high >= 50000)

        if is_yearly or (is_large and job_type != "internship"):
            return {
                "is_undisclosed": False,
                "is_unpaid": False,
                "min_val": low,
                "max_val": high,
                "annual_val": high,
                "monthly_val": high / 12.0,
                "lower_bound_annual": low,
                "raw": salary_text
            }
        else:
            # Monthly scale
            return {
                "is_undisclosed": False,
                "is_unpaid": (high == 0),
                "min_val": low,
                "max_val": high,
                "annual_val": high * 12.0,
                "monthly_val": high,
                "lower_bound_annual": low * 12.0,
                "raw": salary_text
            }

    # Fallback to undisclosed if no numbers parsed
    return {
        "is_undisclosed": True,
        "is_unpaid": False,
        "min_val": None,
        "max_val": None,
        "annual_val": None,
        "monthly_val": None,
        "lower_bound_annual": None,
        "raw": salary_text
    }

def extract_experience_years(text: str) -> Optional[float]:
    """
    Extracts required experience years from job description or card snippet.
    e.g. '0-2 Yrs', '1 - 3 years', 'Fresher', 'Min 3 years', '2+ years'
    """
    if not text:
        return None
    lower = text.lower()

    if "fresher" in lower or "entry level" in lower or "intern" in lower or "0 year" in lower or "0-0 year" in lower:
        return 0.0

    # Range format e.g. "0-2 yrs", "1 to 3 years", "2-5 years"
    range_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:yr|yrs|year|years)", lower)
    if range_match:
        # Minimum required experience is group(1)
        return float(range_match.group(1))

    # Single number e.g. "2+ years", "3 years"
    single_match = re.search(r"(\d+(?:\.\d+)?)\+?\s*(?:yr|yrs|year|years)", lower)
    if single_match:
        return float(single_match.group(1))

    return None

def apply_hard_filters(
    job: DiscoveredJob,
    prefs: Optional[JobPreference],
    applied_urls: set,
    job_type: str = "job",
    allow_undisclosed_salary: bool = True,
    max_experience_years: float = 2.0
) -> Tuple[bool, Optional[str]]:
    """
    Hard filters executed in deterministic code before any LLM is called:
    1. Already applied or logged in vault
    2. Blacklisted companies
    3. Target roles filter
    4. Location & Work mode filter
    5. Salary & Stipend filter (Internship min 10k/mo, Job min 5 LPA, upper bound evaluation, unpaid skip)
    6. Experience filter (Fresher cap: max 2.0 years)
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

    # 3. Target roles filter: skip non-tech roles before any LLM call
    NON_TECH_KEYWORDS = [
        "content", "graphic", "business development", "marketing", "sales", "hr",
        "telecaller", "operations", "recruiter", "academic counselor", "social media",
        "teacher", "faculty", "curriculum", "copywriter", "seo specialist", "bpo", "voice process"
    ]
    title_lower = job.title.lower()
    for ntk in NON_TECH_KEYWORDS:
        if re.search(r"\b" + re.escape(ntk) + r"\b", title_lower):
            return False, f"Job title '{job.title}' is a non-tech role ({ntk})"

    target_roles = [r.lower().strip() for r in (prefs.target_roles or [])]
    if target_roles:
        # Match if target role phrase is present, or candidate title matches common software roles
        matches_role = False
        for r in target_roles:
            if r in title_lower:
                matches_role = True
                break
            # Check key software terms if target role contains developer/engineer
            if any(term in r for term in ["developer", "engineer", "programmer"]):
                if any(tech_term in title_lower for tech_term in ["software engineer", "software developer", "backend", "full stack", "fullstack", "python developer", "python engineer", "web developer"]):
                    matches_role = True
                    break

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

    # Determine effective job type from parameter, metadata, or title
    effective_job_type = job.metadata.get("job_type", job_type).lower()
    if "intern" in job.title.lower() or "internship" in job.title.lower():
        effective_job_type = "internship"

    # 5. Salary & Stipend filter
    salary_info = parse_salary_and_stipend(job.salary_raw, job_type=effective_job_type)

    # Rule: Always skip unpaid internships
    if effective_job_type == "internship" and salary_info["is_unpaid"]:
        return False, "Skipped unpaid internship (minimum requirement is 10,000 INR/month)"

    # Rule: Undisclosed salary toggle
    if salary_info["is_undisclosed"]:
        if not allow_undisclosed_salary:
            return False, "Skipped listing with undisclosed/unspecified salary"
    else:
        # Disclosed salary evaluation
        if effective_job_type == "internship":
            # Minimum stipend 10,000 INR/month. Pass if upper bound meets minimum.
            min_stipend = 10000.0
            stipend_monthly = salary_info["monthly_val"] or 0.0
            if stipend_monthly < min_stipend:
                return False, f"Stipend {job.salary_raw} ({stipend_monthly:,.0f}/mo) is below minimum requirement of 10,000 INR/month"
        else:
            # Job: minimum 5 LPA (500,000 INR/year). Pass if upper bound meets minimum.
            min_job_annual = (prefs.min_salary or 500000.0)
            if min_job_annual < 500000.0:
                min_job_annual = 500000.0 # Enforce at least 5 LPA default
            annual_val = salary_info["annual_val"] or 0.0
            if annual_val < min_job_annual:
                return False, f"Salary {job.salary_raw} ({annual_val/100000:.1f} LPA) is below minimum requirement of {min_job_annual/100000:.1f} LPA"

    # 6. Experience filter: skip jobs requiring more than max_experience_years (default 2.0 years)
    exp_snippet = job.metadata.get("experience_raw") or job.description or ""
    req_exp = extract_experience_years(exp_snippet)
    if req_exp is not None and req_exp > max_experience_years:
        return False, f"Requires {req_exp:.1f}+ years experience (exceeds fresher cap of {max_experience_years:.1f} years)"

    return True, None
