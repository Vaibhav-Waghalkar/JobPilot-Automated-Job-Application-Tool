import httpx
from bs4 import BeautifulSoup
from typing import List
from backend.adapters.base_adapter import BaseJobAdapter, DiscoveredJob

class CareerPagesAdapter(BaseJobAdapter):
    """
    Adapter for direct company career pages (e.g., Lever, Greenhouse, Workday, SmartRecruiters).
    """
    def __init__(self):
        super().__init__("career_page")

    async def scrape_career_url(self, url: str) -> List[DiscoveredJob]:
        results: List[DiscoveredJob] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JobPilot/1.0",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return results

                soup = BeautifulSoup(resp.text, "html.parser")
                # Look for typical job postings / listings
                postings = soup.select(".posting, .job-item, .career-item, li a[href*='job'], li a[href*='career']")
                
                # Derive company name from domain or title
                domain_parts = url.split("//")[-1].split("/")[0].split(".")
                company_guess = domain_parts[1].capitalize() if len(domain_parts) > 2 else domain_parts[0].capitalize()

                for idx, post in enumerate(postings[:15], start=1):
                    link = post.get("href") or (post.find("a")["href"] if post.find("a") else "")
                    title_text = post.get_text(strip=True)
                    if not title_text or len(title_text) > 80:
                        continue

                    full_apply_url = link if link.startswith("http") else f"{url.rstrip('/')}/{link.lstrip('/')}"

                    results.append(DiscoveredJob(
                        platform="career_page",
                        external_id=f"cp-{company_guess.lower()}-{idx}",
                        company=company_guess,
                        title=title_text,
                        location="Hybrid / Bengaluru",
                        salary_raw="Competitive",
                        apply_url=full_apply_url,
                        description=f"{title_text} position at {company_guess}."
                    ))
        except Exception:
            pass

        return results

    async def search_jobs(self, keywords: List[str], locations: List[str], limit: int = 20) -> List[DiscoveredJob]:
        # Career pages search defaults to seeded company targets
        return []
