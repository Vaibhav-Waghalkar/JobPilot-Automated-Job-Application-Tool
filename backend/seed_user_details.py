import asyncio
from sqlalchemy import select
from backend.vault.database import AsyncSessionLocal
from backend.vault.models import FixedProfile, JobPreference, VaultFact
from backend.vault.vector_store import upsert_vault_fact_embedding
from backend.vault.importer import compute_hash

async def seed_confirmed_details():
    async with AsyncSessionLocal() as db:
        # 1. Update Fixed Profile with user confirmed details
        stmt = select(FixedProfile).limit(1)
        res = await db.execute(stmt)
        profile = res.scalars().first()
        if not profile:
            profile = FixedProfile()
            db.add(profile)

        profile.full_name = "Vaibhav Santosh Waghalkar"
        profile.email = "vaibhavwaghalkar3@gmail.com"
        profile.phone = "9356630640"
        profile.location = "Pune"
        profile.current_ctc = "0 LPA"
        profile.expected_ctc = "6 to 8 LPA"
        profile.notice_period_days = 0
        profile.total_experience_years = 0.5
        profile.employment_status = "not currently employed, internships only"
        profile.availability = "immediate"
        if not profile.links:
            profile.links = {}
        profile.links["linkedin"] = "https://www.linkedin.com/in/vaibhav-waghalkar/"
        profile.links["portfolio"] = "https://dev-vaibhav-ai.co.in/"
        profile.links["github"] = "https://github.com/Vaibhav-Waghalkar"
        profile.languages = ["English (Professional Working)", "Hindi", "Marathi", "German (A1)"]

        # 2. Update Job Preferences (Filters: internship min 10k/mo, job min 5 LPA, undisclosed allowed, fresher max 2.0 yrs)
        stmt_pref = select(JobPreference).limit(1)
        pref_res = await db.execute(stmt_pref)
        pref = pref_res.scalars().first()
        if not pref:
            pref = JobPreference()
            db.add(pref)

        pref.target_roles = ["Backend Developer", "Python Developer", "Full Stack Developer", "Software Developer"]
        pref.min_salary = 500000.0 # 5 LPA
        pref.preferred_locations = ["Pune", "Bengaluru", "Remote", "Work from Home"]
        pref.allow_undisclosed_salary = True
        pref.max_experience_years = 2.0
        pref.default_match_threshold = 70
        pref.blacklisted_companies = ["CryptoScamCo", "SpamCorp"]

        # 3. Add Verified Vault Facts for confirmed details
        confirmed_facts = [
            {
                "id": "FACT-USR-full-name",
                "section": "basic",
                "title": "Full Name",
                "content": "Full name is Vaibhav Santosh Waghalkar.",
            },
            {
                "id": "FACT-USR-email",
                "section": "basic",
                "title": "Email Address",
                "content": "Email address is vaibhavwaghalkar3@gmail.com.",
            },
            {
                "id": "FACT-USR-phone",
                "section": "basic",
                "title": "Phone Number",
                "content": "Phone number is 9356630640.",
            },
            {
                "id": "FACT-USR-location",
                "section": "basic",
                "title": "Current Location",
                "content": "Current city and location is Pune.",
            },
            {
                "id": "FACT-USR-experience",
                "section": "experience",
                "title": "Total Experience",
                "content": "Total experience is 0.5 years, all completed across internships. Employment status is not currently employed, internships only. Availability is immediate (0 days notice).",
            },
            {
                "id": "FACT-USR-compensation",
                "section": "application_details",
                "title": "Compensation Details",
                "content": "Current CTC is 0 LPA. Expected CTC is 6 to 8 LPA. Notice period is immediate (0 days).",
            }
        ]

        for cf in confirmed_facts:
            stmt_f = select(VaultFact).where(VaultFact.id == cf["id"])
            fact = (await db.execute(stmt_f)).scalars().first()
            chash = compute_hash(cf["content"])
            if not fact:
                fact = VaultFact(
                    id=cf["id"],
                    section=cf["section"],
                    title=cf["title"],
                    content=cf["content"],
                    content_hash=chash,
                    verified=True,
                    source="user"
                )
                db.add(fact)
            else:
                fact.title = cf["title"]
                fact.content = cf["content"]
                fact.content_hash = chash
                fact.verified = True
                fact.source = "user"
            try:
                upsert_vault_fact_embedding(cf["id"], cf["content"], {"section": cf["section"], "title": cf["title"]})
            except Exception:
                pass

        await db.commit()
        print("Successfully seeded confirmed user details into database!")

if __name__ == "__main__":
    asyncio.run(seed_confirmed_details())
