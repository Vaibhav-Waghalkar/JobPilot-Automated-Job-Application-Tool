import io
import zipfile
import csv
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.vault.models import VaultFact, ImportReviewItem

async def stage_for_review(
    items: List[Dict[str, Any]],
    source: str,
    session: AsyncSession
) -> List[ImportReviewItem]:
    """
    Takes candidate items, checks for potential conflicts with existing vault facts,
    and stages them in import_review_items table for human approval/editing.
    """
    created_staging_items = []
    
    # Pre-fetch existing facts
    stmt = select(VaultFact)
    res = await session.execute(stmt)
    existing_facts = res.scalars().all()
    existing_by_title = {f.title.lower().strip(): f for f in existing_facts}

    for item in items:
        section = item.get("section", "general")
        title = item.get("title", "Imported Item").strip()
        proposed_content = item.get("content", "").strip()

        conflict_detected = False
        conflict_details = None

        # Check for title overlap
        if title.lower() in existing_by_title:
            matched_fact = existing_by_title[title.lower()]
            conflict_detected = True
            conflict_details = (
                f"Conflict with existing fact [{matched_fact.id}]: "
                f"Existing content differs. Review before approving."
            )

        review_item = ImportReviewItem(
            source=source,
            section=section,
            title=title,
            proposed_content=proposed_content,
            conflict_detected=conflict_detected,
            conflict_details=conflict_details,
            status="pending"
        )
        session.add(review_item)
        created_staging_items.append(review_item)

    await session.commit()
    return created_staging_items

async def parse_linkedin_zip(zip_bytes: bytes, session: AsyncSession) -> List[ImportReviewItem]:
    """
    Extracts Positions.csv, Education.csv, Skills.csv from standard LinkedIn export zip.
    """
    items_to_stage = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        namelist = z.namelist()

        # Positions
        pos_file = next((name for name in namelist if name.endswith("Positions.csv")), None)
        if pos_file:
            with z.open(pos_file) as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
                for row in reader:
                    comp = row.get("Company Name", "Unknown Company")
                    title = row.get("Title", "Role")
                    desc = row.get("Description", "")
                    start = row.get("Started On", "")
                    end = row.get("Finished On", "Present")
                    loc = row.get("Location", "")
                    content = (
                        f"Company: {comp}\n"
                        f"Role: {title}\n"
                        f"Duration: {start} - {end}\n"
                        f"Location: {loc}\n"
                        f"Summary: {desc}"
                    )
                    items_to_stage.append({
                        "section": "experience",
                        "title": f"{title} at {comp}",
                        "content": content
                    })

        # Skills
        skill_file = next((name for name in namelist if name.endswith("Skills.csv")), None)
        if skill_file:
            with z.open(skill_file) as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
                for row in reader:
                    name = row.get("Name", "").strip()
                    if name:
                        items_to_stage.append({
                            "section": "skill",
                            "title": f"Skill: {name}",
                            "content": f"Skill: {name}\nSource: LinkedIn Export"
                        })

        # Education
        edu_file = next((name for name in namelist if name.endswith("Education.csv")), None)
        if edu_file:
            with z.open(edu_file) as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
                for row in reader:
                    school = row.get("School Name", "")
                    degree = row.get("Degree Name", "")
                    notes = row.get("Notes", "")
                    start = row.get("Start Date", "")
                    end = row.get("End Date", "")
                    items_to_stage.append({
                        "section": "education",
                        "title": f"{degree} at {school}",
                        "content": f"Institution: {school}\nDegree: {degree}\nDuration: {start} - {end}\nNotes: {notes}"
                    })

    return await stage_for_review(items_to_stage, "linkedin_zip", session)

async def scrape_portfolio_url(url: str, session: AsyncSession) -> List[ImportReviewItem]:
    """
    Scrapes public portfolio website, extracts text sections, and stages for review.
    """
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "JobPilot/1.0 (+http://localhost)"})
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    # Clean scripts, styles
    for s in soup(["script", "style", "noscript", "svg"]):
        s.extract()

    items = []
    # Extract projects if headings exist
    for heading in soup.find_all(["h1", "h2", "h3"]):
        heading_text = heading.get_text(strip=True)
        if not heading_text or len(heading_text) < 3:
            continue
        # Get next sibling paragraphs
        paragraphs = []
        sibling = heading.find_next_sibling()
        while sibling and sibling.name in ["p", "ul", "ol", "div"] and sibling.name not in ["h1", "h2", "h3"]:
            txt = sibling.get_text(separator=" ", strip=True)
            if txt:
                paragraphs.append(txt)
            sibling = sibling.find_next_sibling()

        if paragraphs:
            content = "\n".join(paragraphs)
            items.append({
                "section": "project" if "project" in heading_text.lower() else "experience",
                "title": f"Web: {heading_text}",
                "content": content
            })

    if not items:
        # Fallback to general page text
        text = soup.get_text(separator="\n", strip=True)
        items.append({
            "section": "personal",
            "title": f"Scraped Page from {url}",
            "content": text[:3000] # First 3000 chars
        })

    return await stage_for_review(items, "portfolio_scrape", session)
