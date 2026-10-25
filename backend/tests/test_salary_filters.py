import unittest
from backend.agents.hard_filters import parse_salary_and_stipend, extract_experience_years, apply_hard_filters
from backend.adapters.base_adapter import DiscoveredJob
from backend.vault.models import JobPreference

class TestSalaryAndExperienceFilters(unittest.TestCase):

    def test_internship_stipend_monthly(self):
        # 10,000 / month meets minimum
        res = parse_salary_and_stipend("10,000 /month", job_type="internship")
        self.assertFalse(res["is_unpaid"])
        self.assertFalse(res["is_undisclosed"])
        self.assertEqual(res["monthly_val"], 10000.0)

        # 8,000 / month below minimum
        res_low = parse_salary_and_stipend("8,000 /month", job_type="internship")
        self.assertEqual(res_low["monthly_val"], 8000.0)

    def test_internship_unpaid(self):
        for term in ["Unpaid", "un-paid internship", "0 stipend", "free internship"]:
            res = parse_salary_and_stipend(term, job_type="internship")
            self.assertTrue(res["is_unpaid"], f"Failed for {term}")

    def test_job_salary_lpa_and_ranges(self):
        # Range 5-8 LPA -> upper bound is 8 LPA (800,000)
        res = parse_salary_and_stipend("5-8 LPA", job_type="job")
        self.assertEqual(res["annual_val"], 800000.0)
        self.assertEqual(res["lower_bound_annual"], 500000.0)

        # Single 6 LPA
        res2 = parse_salary_and_stipend("6 LPA", job_type="job")
        self.assertEqual(res2["annual_val"], 600000.0)

        # Range 3-6 LPA (lower is 3 LPA, but upper is 6 LPA -> passes 5 LPA minimum requirement)
        res3 = parse_salary_and_stipend("3 - 6 LPA", job_type="job")
        self.assertEqual(res3["annual_val"], 600000.0)

    def test_job_monthly_conversion(self):
        # 45,000 / month converted to annual: 45,000 * 12 = 540,000 (5.4 LPA)
        res = parse_salary_and_stipend("45,000 / month", job_type="job")
        self.assertEqual(res["annual_val"], 540000.0)

    def test_undisclosed_and_performance_based(self):
        for term in ["Not Disclosed", "Performance based", "As per industry standard", "Competitive", "Undisclosed"]:
            res = parse_salary_and_stipend(term, job_type="job")
            self.assertTrue(res["is_undisclosed"], f"Expected undisclosed for {term}")

    def test_experience_extraction(self):
        self.assertEqual(extract_experience_years("0-2 Yrs"), 0.0)
        self.assertEqual(extract_experience_years("Fresher"), 0.0)
        self.assertEqual(extract_experience_years("1 - 3 years"), 1.0)
        self.assertEqual(extract_experience_years("3+ years"), 3.0)
        self.assertEqual(extract_experience_years("Minimum 4 years exp"), 4.0)

    def test_hard_filter_decision(self):
        prefs = JobPreference(min_salary=500000.0, target_roles=["Backend Developer", "Python Developer"])

        # 1. Job with 6 LPA -> passes
        job1 = DiscoveredJob(
            platform="naukri", external_id="1", company="Tech Corp",
            title="Backend Developer", location="Remote", salary_raw="6 LPA", apply_url="http://job1"
        )
        passed, reason = apply_hard_filters(job1, prefs, set(), job_type="job")
        self.assertTrue(passed)

        # 2. Job with 4 LPA -> fails
        job2 = DiscoveredJob(
            platform="naukri", external_id="2", company="LowPay",
            title="Python Developer", location="Remote", salary_raw="4 LPA", apply_url="http://job2"
        )
        passed, reason = apply_hard_filters(job2, prefs, set(), job_type="job")
        self.assertFalse(passed)
        self.assertIn("below minimum requirement", reason)

        # 3. Unpaid internship -> always fails
        intern_unpaid = DiscoveredJob(
            platform="internshala", external_id="3", company="Startup",
            title="Python Backend Intern", location="Remote", salary_raw="Unpaid", apply_url="http://job3"
        )
        passed, reason = apply_hard_filters(intern_unpaid, prefs, set(), job_type="internship")
        self.assertFalse(passed)
        self.assertIn("Skipped unpaid internship", reason)

        # 4. Internship with 15k/mo -> passes
        intern_paid = DiscoveredJob(
            platform="internshala", external_id="4", company="GoodStartup",
            title="Python Developer Intern", location="Remote", salary_raw="15,000 /month", apply_url="http://job4"
        )
        passed, reason = apply_hard_filters(intern_paid, prefs, set(), job_type="internship")
        self.assertTrue(passed)

        # 5. Over 2 years experience -> fails fresher cap
        job_exp = DiscoveredJob(
            platform="naukri", external_id="5", company="BigTech",
            title="Senior Python Developer", location="Remote", salary_raw="10 LPA", apply_url="http://job5",
            metadata={"experience_raw": "3-5 Yrs"}
        )
        passed, reason = apply_hard_filters(job_exp, prefs, set(), job_type="job", max_experience_years=2.0)
        self.assertFalse(passed)
        self.assertIn("exceeds fresher cap", reason)

if __name__ == "__main__":
    unittest.main()
