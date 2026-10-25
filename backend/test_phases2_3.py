import asyncio
import json
import httpx
from backend.main import app

async def run_tests():
    print("Testing Phases 2 & 3 Integration...")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Test Discovery & Matching
        print("1. Running Discovery and Matching...")
        r_disc = await client.post("/api/discovery/run", json={"platform": "internshala", "limit": 5})
        print("  Discovery response:", r_disc.status_code, r_disc.json())
        assert r_disc.status_code == 200

        # 2. Test Discovered Jobs List
        print("2. Fetching Discovered Jobs...")
        r_jobs = await client.get("/api/discovery/jobs")
        jobs = r_jobs.json()
        print(f"  Found {len(jobs)} total jobs in database.")
        for j in jobs[:3]:
            print(f"   [{j['status'].upper()}] {j['company']} - {j['title']} (Score: {j.get('match_score')}) Skip Reason: {j.get('skip_reason')}")

        # 3. Test Grounded Answer Engine - Hard fact
        print("3. Testing Hard Fact Question (Notice Period)...")
        r_ans1 = await client.post("/api/discovery/answer-engine/generate", json={
            "question": "What is your notice period?",
            "job_description": "Senior Python Developer"
        })
        print("  Answer 1:", r_ans1.json())
        assert "[FIXED-PROFILE]" in r_ans1.json()["answer"]

        # 4. Test Grounded Answer Engine - Experience question
        print("4. Testing Experience Question...")
        r_ans2 = await client.post("/api/discovery/answer-engine/generate", json={
            "question": "What experience do you have with microservices and caching?",
            "job_description": "FastAPI, PostgreSQL, microservices"
        })
        ans2_data = r_ans2.json()
        print("  Answer 2:", ans2_data)

        # 5. Test 'Needs You' alert and saving answer to vault
        print("5. Testing 'Needs You' and Saving New Answer...")
        r_save = await client.post("/api/discovery/answer-engine/save-user-answer", json={
            "question": "Are you willing to relocate to Tokyo?",
            "answer": "Yes, I am open to relocating to Tokyo for an exceptional senior engineering role."
        })
        print("  Save answer response:", r_save.status_code, r_save.json())
        assert r_save.status_code == 200

        print("\nAll Phases 2 & 3 Integration Tests PASSED!")

if __name__ == "__main__":
    asyncio.run(run_tests())
