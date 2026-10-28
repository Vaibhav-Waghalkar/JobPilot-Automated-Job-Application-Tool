import unittest
from backend.agents.hard_filters import parse_salary_and_stipend, extract_experience_years, apply_hard_filters
from backend.adapters.base_adapter import DiscoveredJob
from backend.vault.models import JobPreference

class TestBugFixes(unittest.TestCase):
    def test_salary_parsing_internshala_formats(self):
        # Format 1: Internship monthly range
        res1 = parse_salary_and_stipend("₹ 10,000 - 15,000 /month", job_type="internship")
        self.assertFalse(res1["is_unpaid"])
        self.assertFalse(res1["is_undisclosed"])
        self.assertEqual(res1["min_val"], 10000.0)
        self.assertEqual(res1["max_val"], 15000.0)
        self.assertEqual(res1["monthly_val"], 15000.0)

        # Format 2: Indian comma grouping annual (1,50,000 - 2,20,000 /year)
        res2 = parse_salary_and_stipend("1,50,000 - 2,20,000 /year", job_type="job")
        self.assertEqual(res2["min_val"], 150000.0)
        self.assertEqual(res2["max_val"], 220000.0)
        self.assertEqual(res2["annual_val"], 220000.0)

        # Format 3: Duplicated string due to mobile/desktop concatenation
        res3 = parse_salary_and_stipend("1,50,000 - 2,20,000 1,50,000 - 2,20,000 /year", job_type="job")
        self.assertEqual(res3["min_val"], 150000.0)
        self.assertEqual(res3["max_val"], 220000.0)

        # Format 4: LPA range
        res4 = parse_salary_and_stipend("5 - 8 LPA", job_type="job")
        self.assertEqual(res4["min_val"], 500000.0)
        self.assertEqual(res4["max_val"], 800000.0)
        self.assertEqual(res4["annual_val"], 800000.0)

        # Format 5: Unpaid internship
        res5 = parse_salary_and_stipend("Unpaid", job_type="internship")
        self.assertTrue(res5["is_unpaid"])
        self.assertEqual(res5["monthly_val"], 0.0)

        # Format 6: Undisclosed
        res6 = parse_salary_and_stipend("Not Disclosed", job_type="job")
        self.assertTrue(res6["is_undisclosed"])

    def test_non_tech_role_filtering(self):
        prefs = JobPreference(
            target_roles=["Backend Developer", "Python Developer", "Software Developer"],
            min_salary=500000.0,
            allow_undisclosed_salary=True
        )

        # Content Developer (Mathematics) -> Must be rejected as non-tech prior to LLM
        job_non_tech = DiscoveredJob(
            platform="internshala",
            external_id="nt-1",
            company="EduCorp",
            title="Content Developer (Mathematics)",
            location="Remote",
            salary_raw="6 LPA",
            apply_url="https://example.com/job/math-content",
            description="Create math textbook questions"
        )
        passed, reason = apply_hard_filters(job_non_tech, prefs, applied_urls=set())
        self.assertFalse(passed)
        self.assertIn("non-tech role", reason.lower())

        # Tech role Python Backend Developer -> Must pass
        job_tech = DiscoveredJob(
            platform="internshala",
            external_id="t-1",
            company="TechCorp",
            title="Python Backend Developer",
            location="Remote",
            salary_raw="7 LPA",
            apply_url="https://example.com/job/python-backend",
            description="FastAPI microservices"
        )
        passed_tech, reason_tech = apply_hard_filters(job_tech, prefs, applied_urls=set())
        self.assertTrue(passed_tech)
        self.assertIsNone(reason_tech)

    def test_salary_minimum_filters(self):
        prefs = JobPreference(
            target_roles=["Backend Developer"],
            min_salary=500000.0,
            allow_undisclosed_salary=False
        )

        # Job below 5 LPA (3 LPA) -> Must be rejected
        job_low = DiscoveredJob(
            platform="internshala",
            external_id="low-1",
            company="SmallCo",
            title="Backend Developer",
            location="Remote",
            salary_raw="3 LPA",
            apply_url="https://example.com/job/low-1",
            description="Python junior developer"
        )
        passed_low, reason_low = apply_hard_filters(job_low, prefs, applied_urls=set())
        self.assertFalse(passed_low)
        self.assertIn("below minimum requirement", reason_low)

        # Internship below 10,000 /month (e.g. 5,000 /month) -> Must be rejected
        internship_low = DiscoveredJob(
            platform="internshala",
            external_id="int-low",
            company="StartupCo",
            title="Python Backend Intern",
            location="Remote",
            salary_raw="5,000 /month",
            apply_url="https://example.com/intern/low",
            description="Python backend intern"
        )
        passed_int, reason_int = apply_hard_filters(internship_low, prefs, applied_urls=set(), job_type="internship")
        self.assertFalse(passed_int)
        self.assertIn("below minimum requirement", reason_int)

        # Unpaid internship -> Must be rejected
        internship_unpaid = DiscoveredJob(
            platform="internshala",
            external_id="int-unpaid",
            company="VolunteerCo",
            title="Python Backend Intern",
            location="Remote",
            salary_raw="Unpaid",
            apply_url="https://example.com/intern/unpaid",
            description="Unpaid internship"
        )
        passed_unp, reason_unp = apply_hard_filters(internship_unpaid, prefs, applied_urls=set(), job_type="internship")
        self.assertFalse(passed_unp)
        self.assertIn("unpaid", reason_unp.lower())

if __name__ == "__main__":
    unittest.main()
