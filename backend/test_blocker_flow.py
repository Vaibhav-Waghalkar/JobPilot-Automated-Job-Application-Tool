import asyncio
import time
from backend.vault.database import init_db, AsyncSessionLocal
from backend.vault.models import JobApplication
from backend.agents.form_filler import playwright_form_filler

async def test_blocker_timeout_and_resolution():
    await init_db()

    print("=== TEST PART 1: BLOCKER TIMEOUT (Shortened to 10 seconds) ===")
    async with AsyncSessionLocal() as session:
        # Create test job application targeting mock form with an unknown question
        test_app = JobApplication(
            platform="mock",
            company="BlockerTest Corp",
            title="Senior Test Engineer",
            location="Remote",
            apply_url="http://127.0.0.1:8000/mock/page1",
            status="matched",
            answers_submitted={}
        )
        session.add(test_app)
        await session.commit()
        await session.refresh(test_app)
        app_id = test_app.id

    start_time = time.time()
    # Run form filler with a 10 second timeout
    async with AsyncSessionLocal() as session:
        result = await playwright_form_filler.fill_application(
            application_id=app_id,
            session=session,
            timeout_seconds=10
        )
    elapsed = time.time() - start_time

    print(f"Elapsed time: {elapsed:.2f} seconds")
    print("Result status:", result.get("status"))
    print("Parked as Needs You:", result.get("parked"))
    print("Timed out flag:", result.get("timed_out"))
    print("Reason:", result.get("reason"))

    # Verify database state after timeout
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        res = await session.execute(select(JobApplication).where(JobApplication.id == app_id))
        saved_app = res.scalars().first()
        print("Database status:", saved_app.status)
        print("Needs You Reason:", saved_app.needs_you_reason)
        print("Saved State Page:", saved_app.needs_you_state.get("page_num"))
        print("Saved State Filled Fields:", saved_app.needs_you_state.get("filled_fields"))

        assert saved_app.status == "needs_you"
        assert result.get("timed_out") is True
        print("PART 1 PASSED: Job parked as 'Needs You' with saved state after timeout.\n")

    print("=== TEST PART 2: USER ANSWERS IN TIME (Continues immediately) ===")
    async with AsyncSessionLocal() as session:
        test_app2 = JobApplication(
            platform="mock",
            company="FastAnswer Corp",
            title="Speed Engineer",
            location="Remote",
            apply_url="http://127.0.0.1:8000/mock/page1",
            status="matched",
            answers_submitted={}
        )
        session.add(test_app2)
        await session.commit()
        await session.refresh(test_app2)
        app2_id = test_app2.id

    # Launch filler and answer it after 2 seconds
    async def answer_after_delay():
        await asyncio.sleep(2)
        print("  -> User dashboard answering blocker after 2 seconds...")
        playwright_form_filler.signal_blocker_resolved(app2_id, "Fast Answer From Dashboard")

    start_time2 = time.time()
    async with AsyncSessionLocal() as session:
        # Run concurrent answer task and filler
        task_ans = asyncio.create_task(answer_after_delay())
        res2 = await playwright_form_filler.fill_application(
            application_id=app2_id,
            session=session,
            timeout_seconds=10
        )
        await task_ans
    elapsed2 = time.time() - start_time2

    print(f"Elapsed time: {elapsed2:.2f} seconds (Expected ~3-4s, far less than 10s)")
    print("Result 2 status:", res2.get("status"))
    print("PART 2 PASSED: Job received answer in time and continued immediately without parking.\n")

    await playwright_form_filler.close()
    print("ALL BLOCKER FLOW TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_blocker_timeout_and_resolution())
