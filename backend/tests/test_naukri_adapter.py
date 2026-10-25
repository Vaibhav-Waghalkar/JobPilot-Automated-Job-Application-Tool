import unittest
from pathlib import Path
from backend.adapters.naukri_adapter import NaukriAdapter
from backend.agents.hard_filters import apply_hard_filters
from backend.vault.models import JobPreference, VaultFact

class TestNaukriAdapter(unittest.TestCase):

    def setUp(self):
        self.adapter = NaukriAdapter()
        mock_path = Path("data/mock_naukri_search.html")
        self.assertTrue(mock_path.exists())
        self.mock_html = mock_path.read_text(encoding="utf-8")

    def test_parse_mock_search_results(self):
        jobs = self.adapter.parse_search_results(self.mock_html, limit=10)
        self.assertEqual(len(jobs), 5)

        # Job 1 check
        j1 = jobs[0]
        self.assertEqual(j1.company, "Apex Cloud Systems")
        self.assertEqual(j1.title, "Python Backend Developer - FastAPI & SQL")
        self.assertEqual(j1.salary_raw, "7-10 LPA")
        self.assertEqual(j1.metadata["experience_raw"], "0-2 Yrs")
        self.assertFalse(j1.metadata["is_external"])

        # Job 4 check (external redirect)
        j4 = jobs[3]
        self.assertTrue(j4.metadata["is_external"])

    def test_naukri_hard_filtering_rules(self):
        jobs = self.adapter.parse_search_results(self.mock_html, limit=10)
        prefs = JobPreference(
            min_salary=500000.0, # 5 LPA
            target_roles=["Backend Developer", "Python Developer", "Software Developer"],
            preferred_locations=["Pune", "Remote"]
        )

        # Job 1: 7-10 LPA, 0-2 yrs -> PASS
        p1, r1 = apply_hard_filters(jobs[0], prefs, set(), job_type="job")
        self.assertTrue(p1, f"Job 1 should pass: {r1}")

        # Job 2: 3.5 - 4.5 LPA -> FAIL (< 5 LPA)
        p2, r2 = apply_hard_filters(jobs[1], prefs, set(), job_type="job")
        self.assertFalse(p2)
        self.assertIn("below minimum requirement", r2)

        # Job 3: 4-7 Yrs exp -> FAIL (> 2.0 yrs)
        p3, r3 = apply_hard_filters(jobs[2], prefs, set(), job_type="job", max_experience_years=2.0)
        self.assertFalse(p3)
        self.assertIn("exceeds fresher cap", r3)

        # Job 5: Not Disclosed -> PASS when allow_undisclosed_salary=True
        p5_allow, _ = apply_hard_filters(jobs[4], prefs, set(), job_type="job", allow_undisclosed_salary=True)
        self.assertTrue(p5_allow)

        # Job 5: Not Disclosed -> FAIL when allow_undisclosed_salary=False
        p5_skip, r5 = apply_hard_filters(jobs[4], prefs, set(), job_type="job", allow_undisclosed_salary=False)
        self.assertFalse(p5_skip)
        self.assertIn("undisclosed", r5)

    def test_profile_update_proposal_generation(self):
        current_profile = {
            "resume_headline": "Student at MBES",
            "profile_summary": "Looking for entry level opportunities.",
            "key_skills": ["Python"],
            "projects": [],
            "education": "BE CSE",
            "resume_file": "old_resume.pdf"
        }

        facts = [
            VaultFact(id="F1", section="skill", title="Skill: Python", content="Proficient in Python"),
            VaultFact(id="F2", section="skill", title="Skill: FastAPI", content="Built 55+ REST API endpoints"),
            VaultFact(id="F3", section="skill", title="Skill: SQL", content="Database operations"),
            VaultFact(id="F4", section="project", title="ReviewGuard", content="Fraudulent review detection system")
        ]

        proposal = NaukriAdapter.generate_profile_update_proposal(current_profile, facts)
        self.assertIn("diff", proposal)
        diff = proposal["diff"]
        self.assertEqual(diff["resume_headline"]["proposed"], "Python Backend Developer | FastAPI, REST APIs, SQL, System Architecture")
        self.assertIn("FastAPI", diff["key_skills"]["proposed"])
        self.assertEqual(diff["resume_headline"]["status"], "pending_approval")

    def test_blocker_and_chatbot_detection(self):
        # 1. Recruiter questionnaire
        res1 = NaukriAdapter.detect_blockers_or_chatbot("Please answer recruiter questionnaire before submitting.")
        self.assertIsNotNone(res1)
        self.assertEqual(res1["type"], "chatbot_questionnaire")

        # 2. CAPTCHA
        res2 = NaukriAdapter.detect_blockers_or_chatbot("Verify you are human. Complete the CAPTCHA to continue.")
        self.assertIsNotNone(res2)
        self.assertEqual(res2["type"], "captcha_alert")

        # 3. Clean page
        res3 = NaukriAdapter.detect_blockers_or_chatbot("Application submitted successfully.")
        self.assertIsNone(res3)

if __name__ == "__main__":
    unittest.main()
