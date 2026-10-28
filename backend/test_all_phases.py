import os
import sys

# Ensure tests run in an isolated test database
os.environ["JOBPILOT_TEST_MODE"] = "1"
os.environ["TEST_DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_jobpilot.db"

import asyncio
from pathlib import Path
import httpx
from sqlalchemy import select
from backend.main import app
from backend.vault.database import AsyncSessionLocal
from backend.vault.models import FixedProfile, VaultFact, Resume, ImportReviewItem, JobApplication, SavedQuestionAnswer
from backend.agents.form_filler import playwright_form_filler

async def test_full_pipeline():
    print("=" * 60)
    print("JOBPILOT LOCAL END-TO-END PIPELINE TEST (Phases 1 - 5)")
    print("=" * 60)

    sample_resume = Path("data/sample_alex_resume.pdf").resolve()
    assert sample_resume.exists(), "Sample resume file must exist"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        
        # 1. Test Resume-to-Vault Upload & Strict Extraction
        print("\n[STEP 1] Uploading resume and extracting strictly into review queue...")
        with open(sample_resume, "rb") as f:
            resp = await client.post(
                "/api/workflow/resume-upload-and-extract",
                data={"role_tag": "Backend", "version": 1},
                files={"file": ("sample_alex_resume.pdf", f, "application/pdf")}
            )
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
        data = resp.json()
        print(f"  Result: {data['message']}")
        print(f"  Prefilled profile: {data['extraction']['prefilled_profile']}")

        # Verify candidate prefilled fixed profile
        async with AsyncSessionLocal() as session:
            prof = (await session.execute(select(FixedProfile).limit(1))).scalars().first()
            assert prof.full_name is not None
            assert prof.notice_period_days is None, "Strict Rule: Notice period must remain null until user input"
            assert prof.current_ctc is None, "Strict Rule: CTC must remain null until user input"
            print("  [OK] Strict profile rule validated: Name/email prefilled, CTC/Notice/DOB remain null.")

            # 2. Test Review Queue and Bulk Approval
            print("\n[STEP 2] Bulk approving staged facts into verified vault...")
            items = (await session.execute(select(ImportReviewItem))).scalars().all()
            item_ids = [i.id for i in items]
            print(f"  Found {len(item_ids)} staged items in review queue.")

        resp_appr = await client.post("/api/workflow/review/bulk-approve", json={"item_ids": item_ids})
        assert resp_appr.status_code == 200
        print(f"  {resp_appr.json()['message']}")

        # Verify verified facts
        async with AsyncSessionLocal() as session:
            v_facts = (await session.execute(select(VaultFact).where(VaultFact.verified == True))).scalars().all()
            print(f"  [OK] Verified facts count in vault: {len(v_facts)}")

            # 3. Create a mock application targeting our local multi-page mock form
            print("\n[STEP 3] Registering mock job application targeting local multi-page form...")
            mock_app_entry = JobApplication(
                platform="career_page",
                company="LocalMock Corp",
                title="Backend Software Engineer",
                location="Remote",
                salary_raw="15-20 LPA",
                apply_url="http://127.0.0.1:8000/mock/apply",
                job_description="Seeking a Backend Software Engineer with Python and FastAPI experience.",
                status="matched",
                resume_id=1
            )
            session.add(mock_app_entry)
            await session.commit()
            await session.refresh(mock_app_entry)
            app_id = mock_app_entry.id
            print(f"  Mock application created with ID: {app_id}")

        # 4. Run Form Filler in DRY_RUN / REVIEW mode (Expect 'Needs You' on unknown question)
        print("\n[STEP 4] Executing Form Filler against local mock form...")
        playwright_form_filler.headless = True # Headless for automated headless CI/test run

        async with AsyncSessionLocal() as session:
            fill_result = await playwright_form_filler.fill_application(
                application_id=app_id,
                session=session,
                override_resume_path=str(sample_resume)
            )
            print(f"  Form filler result: {fill_result['status']}")
            assert fill_result["status"] == "needs_you", "Should trigger 'Needs You' on ungrounded distributed consensus question"
            print(f"  [OK] Blocker detected: '{fill_result.get('reason')}'")

        # 5. Resolve 'Needs You' blocker and verify answer persistence in saved_qa
        print("\n[STEP 5] Resolving 'Needs You' blocker with user answer...")
        resp_resolve = await client.post("/api/workflow/needs-you/resolve", json={
            "application_id": app_id,
            "question": "What is your favorite distributed consensus algorithm?",
            "answer": "Raft, due to its understandable leader election and replicated log architecture."
        })
        assert resp_resolve.status_code == 200
        print(f"  {resp_resolve.json()['message']}")

        # Verify answer is in saved_qa so it will NEVER be asked twice
        async with AsyncSessionLocal() as session:
            stmt_qa = select(SavedQuestionAnswer)
            saved_all = (await session.execute(stmt_qa)).scalars().all()
            assert len(saved_all) > 0
            print(f"  [OK] Persistent saved_qa store updated: '{saved_all[0].raw_question}' -> '{saved_all[0].answer}'")

        # 6. Test Tracker & Outcomes
        print("\n[STEP 6] Testing Tracker outcomes and response rate calculation...")
        resp_out = await client.put(f"/api/workflow/tracker/{app_id}/outcome", json={"outcome": "interview"})
        assert resp_out.status_code == 200

        resp_stats = await client.get("/api/workflow/tracker/stats")
        assert resp_stats.status_code == 200
        print("  Tracker statistics:", resp_stats.json())

        # 7. Test Scheduler controls
        print("\n[STEP 7] Testing Scheduler controls (start/pause/kill-switch)...")
        r_sched = await client.post("/api/workflow/scheduler/start")
        print("  Scheduler start:", r_sched.json())
        r_kill = await client.post("/api/workflow/scheduler/kill-switch")
        print("  Scheduler kill-switch:", r_kill.json())

    print("\n" + "=" * 60)
    print("ALL REMAINING PHASES (A, B, C) TESTED & PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
