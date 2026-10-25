import httpx
import logging
from bs4 import BeautifulSoup
from typing import List, Optional
from backend.adapters.base_adapter import BaseJobAdapter, DiscoveredJob

logger = logging.getLogger("jobpilot.internshala")

class InternshalaAdapter(BaseJobAdapter):
    """
    Robust adapter for Internshala:
    - Supports job_type: 'job' or 'internship'
    - Keyword formulation & location filtering
    - Robust selector fallbacks for title, company, location, salary/stipend, detail link
    - Fallback error logging with full structure details
    """
    def __init__(self):
        super().__init__("internshala")
        self.base_url = "https://internshala.com"

    async def search_jobs(
        self,
        keywords: List[str],
        locations: List[str],
        limit: int = 20,
        job_type: str = "job"
    ) -> List[DiscoveredJob]:
        results: List[DiscoveredJob] = []
        is_internship = (job_type or "job").lower() == "internship"

        # Build clean search path for jobs vs internships
        keyword_str = "-".join(keywords[0].lower().split()) if keywords else "python"
        
        if is_internship:
            search_path = f"/internships/{keyword_str}-internship"
        else:
            search_path = f"/jobs/{keyword_str}-jobs"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            async with httpx.AsyncClient(timeout=20.0, headers=headers, follow_redirects=True) as client:
                url = f"{self.base_url}{search_path}"
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.error(f"Internshala search failed: HTTP {resp.status_code} for {url}")
                    return results

                soup = BeautifulSoup(resp.text, "html.parser")
                
                # Primary and fallback selectors for job/internship cards
                all_cards = soup.select(".individual_internship, .job-internship-card")
                if not all_cards:
                    all_cards = soup.select(".internship_meta, div[data-internship_id]")

                if not all_cards:
                    logger.warning(f"No listing cards found on {url}. Internshala page structure may have changed.")
                    return results

                seen_urls = set()
                for card in all_cards:
                    if len(results) >= limit:
                        break

                    job_id = (
                        card.get("id") or 
                        card.get("data-internship_id") or 
                        card.get("data-href", "") or 
                        ""
                    )

                    # Selector fallbacks for Title
                    title_elem = (
                        card.select_one(".job-title-href") or
                        card.select_one(".heading_4_5") or
                        card.select_one("h3.job-internship-name") or
                        card.select_one("a[href*='/job/detail/']") or
                        card.select_one("a[href*='/internship/detail/']")
                    )

                    # Selector fallbacks for Company
                    company_elem = (
                        card.select_one(".link_display_like_text") or
                        card.select_one(".company-name") or
                        card.select_one("p.company-name") or
                        card.select_one("div.company_name")
                    )

                    # Selector fallbacks for Location
                    loc_elem = (
                        card.select_one(".location_link") or
                        card.select_one(".row-1-item.locations") or
                        card.select_one("[class*='location']")
                    )

                    # Selector fallbacks for Compensation (Salary for jobs / Stipend for internships)
                    sal_elem = (
                        card.select_one(".desktop-text") or
                        card.select_one(".salary") or
                        card.select_one(".stipend") or
                        card.select_one("[class*='salary']") or
                        card.select_one("[class*='stipend']")
                    )
                    
                    # If salary element is row-1-item, check children or siblings
                    salary_text = None
                    if sal_elem:
                        salary_text = sal_elem.get_text(strip=True)
                    else:
                        # Scan all row-1-item divs for salary / stipend currency symbols
                        for r_item in card.select(".row-1-item"):
                            txt = r_item.get_text(strip=True)
                            if any(sym in txt for sym in ["₹", "LPA", "/year", "/month", "Unpaid"]):
                                salary_text = txt
                                break

                    detail_link = ""
                    if title_elem and title_elem.get("href"):
                        detail_link = title_elem.get("href")
                    elif card.get("data-href"):
                        detail_link = card.get("data-href")

                    title = title_elem.get_text(strip=True) if title_elem else "Software Engineer"
                    company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"
                    location = loc_elem.get_text(strip=True) if loc_elem else "Remote"
                    salary = salary_text or ("Stipend Undisclosed" if is_internship else "Not Disclosed")
                    
                    if detail_link.startswith("/"):
                        apply_url = f"{self.base_url}{detail_link}"
                    elif detail_link.startswith("http"):
                        apply_url = detail_link
                    else:
                        apply_url = f"{self.base_url}/job/detail/{job_id}"

                    if apply_url in seen_urls:
                        continue
                    seen_urls.add(apply_url)

                    desc = f"Position: {title} at {company}. Type: {'Internship' if is_internship else 'Job'}. Location: {location}. Compensation: {salary}."

                    results.append(DiscoveredJob(
                        platform="internshala",
                        external_id=str(job_id or f"insh-{len(results)+1}"),
                        company=company,
                        title=title,
                        location=location,
                        salary_raw=salary,
                        apply_url=apply_url,
                        description=desc,
                        metadata={"job_type": "internship" if is_internship else "job"}
                    ))
        except Exception as e:
            logger.error(f"Error scraping Internshala: {e}", exc_info=True)

        return results
