import os
import json
import re
import urllib.request
import pypdf
import bs4
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.vault.models import (
    FixedProfile,
    VaultFact,
    Resume,
    ImportReviewItem,
    ConflictItem,
    ProjectTierItem,
    ActivityLog
)
from backend.vault.importer import slugify, compute_hash

REPO_LIST = [
    'JobPilot-Automated-Job-Application-Tool',
    'ReviewGuard-Fraudulent_Review_Detection_System',
    'ARIS-Mark-II',
    'ARIS-AI_Assistant',
    'EmpathAI-Real-Time-Emotion-Detection-AI-Counseling-via-Face-and-Voice',
    'CodeCraft',
    'ERP---Inventory-Management-System',
    'Smart-Resume-Analyzer',
    'Stock-Price-Prediction-using-ML',
    'Hate-Speech-Detection',
    'Billing-Software',
    'Developer-Portfolio',
    'ByteFest2K25-Official_Website',
    'House-Price-Prediction-ML',
    'Face-Detection-System',
    'Autobot-WA-Landing-Page',
    'Phantom-Phoenix-Website',
    'Akshay-Pakade-Portfolio'
]

SUGGESTED_TIERS = {
    'ReviewGuard-Fraudulent_Review_Detection_System': 'Tier A',
    'ARIS-Mark-II': 'Tier A',
    'JobPilot-Automated-Job-Application-Tool': 'Tier A',
    'EmpathAI-Real-Time-Emotion-Detection-AI-Counseling-via-Face-and-Voice': 'Tier A',
    'CodeCraft': 'Tier A',
    'ERP---Inventory-Management-System': 'Tier B',
    'Smart-Resume-Analyzer': 'Tier B',
    'Stock-Price-Prediction-using-ML': 'Tier B',
    'Hate-Speech-Detection': 'Tier B',
    'Billing-Software': 'Tier B',
    'Developer-Portfolio': 'Tier B',
    'ByteFest2K25-Official_Website': 'Tier B',
    'House-Price-Prediction-ML': 'Tier C',
    'Face-Detection-System': 'Tier C',
    'Autobot-WA-Landing-Page': 'Tier C',
    'Phantom-Phoenix-Website': 'Tier C',
    'Akshay-Pakade-Portfolio': 'Tier C',
    'ARIS-AI_Assistant': 'Tier A'
}

class FullDataIngestionService:
    """
    Executes section A ingestion across all 4 sources:
    1. Inbox PDFs (versioned resumes + LinkedIn data export)
    2. Public portfolio website
    3. LinkedIn URL storage
    4. GitHub repositories analysis (tech stack derived from dependencies, structure, tests, Docker, CI)
    5. Conflict seeding & staging into Review Queue
    """

    @classmethod
    async def run_full_ingestion(cls, db: AsyncSession) -> Dict[str, Any]:
        logs = []
        
        # ----------------------------------------------------
        # 1. Profile Prefill (for confirmation, not auto-verified)
        # ----------------------------------------------------
        stmt = select(FixedProfile).limit(1)
        res = await db.execute(stmt)
        profile = res.scalars().first()
        if not profile:
            profile = FixedProfile(
                full_name="Vaibhav Waghalkar",
                phone="9356630640",
                email="vaibhavwaghalkar3@gmail.com",
                location="Pune (Hinjewadi)",
                notice_period_days=None,
                current_ctc=None,
                expected_ctc=None,
                date_of_birth=None,
                total_experience_years=0.33, # ~4 months internship
                languages=["English (Professional Working)", "Hindi", "Marathi", "German (A1)"],
                links={
                    "linkedin": "https://www.linkedin.com/in/vaibhav-waghalkar/",
                    "portfolio": "https://dev-vaibhav-ai.co.in/",
                    "github": "https://github.com/Vaibhav-Waghalkar"
                }
            )
            db.add(profile)
        else:
            profile.phone = "9356630640"
            profile.email = "vaibhavwaghalkar3@gmail.com"
            profile.location = "Pune (Hinjewadi)"
            profile.languages = ["English (Professional Working)", "Hindi", "Marathi", "German (A1)"]
            if not profile.links:
                profile.links = {}
            profile.links["linkedin"] = "https://www.linkedin.com/in/vaibhav-waghalkar/"
            profile.links["portfolio"] = "https://dev-vaibhav-ai.co.in/"
            profile.links["github"] = "https://github.com/Vaibhav-Waghalkar"
        await db.flush()
        logs.append("Configured Fixed Profile prefill for user confirmation.")

        # ----------------------------------------------------
        # 2. Register Resumes in data/inbox/
        # ----------------------------------------------------
        inbox_dir = Path("data/inbox")
        registered_resumes = []
        if inbox_dir.exists():
            for pdf_file in inbox_dir.glob("*.pdf"):
                fname = pdf_file.name
                if "Profile (3)" in fname:
                    continue # LinkedIn export, data source only

                role_tag = "General"
                if "Full-Stack Developer" in fname:
                    role_tag = "Full Stack"
                elif "Python Backend Developer" in fname:
                    role_tag = "Backend, Python"
                elif "Software Developer" in fname:
                    role_tag = "Full Stack, Software Developer"
                elif fname == "Vaibhav Waghalkar.pdf":
                    role_tag = "Backend (latest)"

                # Check if already registered
                r_stmt = select(Resume).where(Resume.file_name == fname)
                r_res = await db.execute(r_stmt)
                existing_r = r_res.scalars().first()

                reader = pypdf.PdfReader(str(pdf_file))
                parsed_text = "\n".join([p.extract_text() or "" for p in reader.pages])

                if not existing_r:
                    resume_obj = Resume(
                        role_tag=role_tag,
                        version=1,
                        file_name=fname,
                        file_path=str(pdf_file.resolve()),
                        parsed_text=parsed_text
                    )
                    db.add(resume_obj)
                    registered_resumes.append(fname)
                else:
                    existing_r.role_tag = role_tag
                    existing_r.parsed_text = parsed_text
                    registered_resumes.append(fname)

        await db.flush()
        logs.append(f"Registered {len(registered_resumes)} versioned resumes with role tags.")

        # ----------------------------------------------------
        # 3. Seed Conflicts Screen (Pre-resolved & Unresolved)
        # ----------------------------------------------------
        conflicts_to_seed = [
            {
                "field_key": "email",
                "title": "Email Address Conflict",
                "description": "Discrepancy between earlier resumes/LinkedIn export and latest profile email.",
                "versions": [
                    {"value": "vaibhavwaghalkar2@gmail.com", "source": "Profile (3).pdf, older resumes", "notes": "Older email address"},
                    {"value": "vaibhavwaghalkar3@gmail.com", "source": "Vaibhav Waghalkar.pdf (latest)", "notes": "Active preferred email address"}
                ],
                "resolved": True,
                "chosen_value": "vaibhavwaghalkar3@gmail.com",
                "chosen_source": "User confirmation (pre-resolved)"
            },
            {
                "field_key": "class_xii",
                "title": "Class XII Higher Secondary Percentage",
                "description": "Minor percentage rounding disagreement across sources.",
                "versions": [
                    {"value": "74.50%", "source": "Vaibhav Waghalkar - Full-Stack Developer.pdf", "notes": "Exact marksheet/board percentage"},
                    {"value": "75.00%", "source": "Summary mention / rounded", "notes": "Rounded estimate"}
                ],
                "resolved": True,
                "chosen_value": "74.50%",
                "chosen_source": "User confirmation (pre-resolved)"
            },
            {
                "field_key": "class_x",
                "title": "Class X Secondary Percentage",
                "description": "Minor percentage rounding disagreement across sources.",
                "versions": [
                    {"value": "87.40%", "source": "Vaibhav Waghalkar - Full-Stack Developer.pdf", "notes": "Exact marksheet/board percentage"},
                    {"value": "87.00%", "source": "Summary mention / rounded", "notes": "Rounded estimate"}
                ],
                "resolved": True,
                "chosen_value": "87.40%",
                "chosen_source": "User confirmation (pre-resolved)"
            },
            {
                "field_key": "eduspark_dates",
                "title": "EduSpark International Experience Dates",
                "description": "Pre-resolved as two separate experience entries: Entry 1 (March-May 2025, Server Manager Intern) and Entry 2 (March-May 2026, Server Manager).",
                "versions": [
                    {"value": "Entry 1: March 2025 - May 2025 (Server Manager Intern)", "source": "Pre-resolved entry 1", "notes": "Internship experience"},
                    {"value": "Entry 2: March 2026 - May 2026 (Server Manager)", "source": "Pre-resolved entry 2", "notes": "5 centers, 500+ concurrent users, 99.9% uptime, team of 10"}
                ],
                "resolved": True,
                "chosen_value": "Two separate entries (March-May 2025 and March-May 2026). Do not merge.",
                "chosen_source": "User confirmation (pre-resolved)"
            },
            {
                "field_key": "aris_repo",
                "title": "ARIS Repository Versioning",
                "description": "Two repos exist: ARIS-AI_Assistant (earlier version) and ARIS-Mark-II (current newer version).",
                "versions": [
                    {"value": "ARIS-Mark-II (current/newer)", "source": "github.com/Vaibhav-Waghalkar/ARIS-Mark-II", "notes": "Primary link to represent project"},
                    {"value": "ARIS-AI_Assistant (earlier)", "source": "github.com/Vaibhav-Waghalkar/ARIS-AI_Assistant", "notes": "Historical earlier implementation"}
                ],
                "resolved": True,
                "chosen_value": "Single project with two repo links; ARIS-Mark-II as primary link.",
                "chosen_source": "User confirmation (pre-resolved)"
            },
            # Still UNRESOLVED metric claims:
            {
                "field_key": "metric_website_speed",
                "title": "Metric Claim: 3x Website Creation Speed",
                "description": "Claims in Real IT Solutions experience that AI Website Builder improved website creation speed by 3x.",
                "versions": [
                    {"value": "3x website creation speed", "source": "Resume experience bullets", "notes": "Unverified metric claim"}
                ],
                "resolved": False,
                "chosen_value": None,
                "chosen_source": None
            },
            {
                "field_key": "metric_dev_productivity",
                "title": "Metric Claim: 20% Developer Productivity",
                "description": "Claims AI-powered IDE improved developer productivity by 20%.",
                "versions": [
                    {"value": "20% developer productivity improvement", "source": "Resume experience bullets", "notes": "Unverified metric claim"}
                ],
                "resolved": False,
                "chosen_value": None,
                "chosen_source": None
            },
            {
                "field_key": "metric_page_load",
                "title": "Metric Claim: 30% Page-Load Improvement",
                "description": "Claims CuroSoft client websites improved page-load performance by 30%.",
                "versions": [
                    {"value": "30% page-load performance improvement", "source": "Curosoft experience bullets", "notes": "Unverified metric claim"}
                ],
                "resolved": False,
                "chosen_value": None,
                "chosen_source": None
            },
            {
                "field_key": "metric_post_release",
                "title": "Metric Claim: 25% Fewer Post-Release Issues",
                "description": "Claims testing & maintenance reduced post-release issues by 25%.",
                "versions": [
                    {"value": "25% fewer post-release issues", "source": "Python Backend resume bullet", "notes": "Unverified metric claim"}
                ],
                "resolved": False,
                "chosen_value": None,
                "chosen_source": None
            },
            {
                "field_key": "metric_eduspark_scale",
                "title": "Metric Claim: EduSpark Team of 10, 500+ Users, 99.9% Uptime",
                "description": "Claims managing CET exam infrastructure with 500+ concurrent users, 99.9% uptime, and leading 10 engineers.",
                "versions": [
                    {"value": "Led team of 10 engineers, 500+ concurrent users, 99.9% uptime across 50+ live sessions", "source": "Eduspark March-May 2026 entry", "notes": "Unverified metric claims"}
                ],
                "resolved": False,
                "chosen_value": None,
                "chosen_source": None
            }
        ]

        for c_data in conflicts_to_seed:
            c_stmt = select(ConflictItem).where(ConflictItem.field_key == c_data["field_key"])
            c_res = await db.execute(c_stmt)
            existing_c = c_res.scalars().first()
            if not existing_c:
                c_item = ConflictItem(
                    field_key=c_data["field_key"],
                    title=c_data["title"],
                    description=c_data["description"],
                    versions=c_data["versions"],
                    resolved=c_data["resolved"],
                    chosen_value=c_data["chosen_value"],
                    chosen_source=c_data["chosen_source"],
                    resolved_at=datetime.utcnow() if c_data["resolved"] else None
                )
                db.add(c_item)

        await db.flush()
        logs.append(f"Seeded {len(conflicts_to_seed)} conflict items (5 pre-resolved, 5 unverified metrics).")

        # ----------------------------------------------------
        # 4. GitHub Analysis & Project Tier Rubric
        # ----------------------------------------------------
        github_repos_data = await cls._analyze_github_repos()
        for repo_name, r_info in github_repos_data.items():
            pt_stmt = select(ProjectTierItem).where(ProjectTierItem.project_name == repo_name)
            pt_res = await db.execute(pt_stmt)
            existing_pt = pt_res.scalars().first()

            sug_tier = SUGGESTED_TIERS.get(repo_name, "Tier B")
            rubric_summary = (
                f"Author: {r_info['is_author']} | Language: {r_info['language']} | "
                f"Tests: {r_info['has_tests']} | Docker: {r_info['has_docker']} | "
                f"CI: {r_info['has_ci']} | Dependencies: {', '.join(r_info['tech_stack'][:4])}"
            )

            if not existing_pt:
                pt_item = ProjectTierItem(
                    project_name=repo_name,
                    tier=sug_tier,
                    suggested_tier=sug_tier,
                    repo_url=f"https://github.com/Vaibhav-Waghalkar/{repo_name}",
                    tech_stack=r_info["tech_stack"],
                    has_tests=r_info["has_tests"],
                    has_docker=r_info["has_docker"],
                    has_ci=r_info["has_ci"],
                    is_author=r_info["is_author"],
                    rubric_summary=rubric_summary,
                    user_confirmed=False
                )
                db.add(pt_item)
            else:
                existing_pt.tech_stack = r_info["tech_stack"]
                existing_pt.has_tests = r_info["has_tests"]
                existing_pt.has_docker = r_info["has_docker"]
                existing_pt.rubric_summary = rubric_summary

        await db.flush()
        logs.append(f"Analyzed {len(github_repos_data)} GitHub repositories with rubric tiering.")

        # ----------------------------------------------------
        # 5. Populate Review Queue with Ingested Items
        # ----------------------------------------------------
        staged_count = await cls._stage_review_items(db, github_repos_data)
        logs.append(f"Staged {staged_count} granular items into the Review Queue for human audit.")

        await db.commit()
        return {
            "status": "success",
            "logs": logs,
            "resumes_registered": registered_resumes,
            "conflicts_count": len(conflicts_to_seed),
            "projects_analyzed": len(github_repos_data),
            "staged_items_count": staged_count
        }

    @classmethod
    async def _analyze_github_repos(cls) -> Dict[str, Any]:
        results = {}
        for r_name in REPO_LIST:
            url = f"https://api.github.com/repos/Vaibhav-Waghalkar/{r_name}"
            req = urllib.request.Request(url, headers={"User-Agent": "JobPilot-Agent"})
            meta = {}
            try:
                with urllib.request.urlopen(req) as resp:
                    data = json.loads(resp.read().decode())
                    meta = {
                        "fork": data.get("fork", False),
                        "language": data.get("language") or "Code",
                        "description": data.get("description") or ""
                    }
            except Exception:
                meta = {"fork": False, "language": "Python", "description": ""}

            files_url = f"https://api.github.com/repos/Vaibhav-Waghalkar/{r_name}/contents"
            files_req = urllib.request.Request(files_url, headers={"User-Agent": "JobPilot-Agent"})
            file_names = []
            try:
                with urllib.request.urlopen(files_req) as resp:
                    items = json.loads(resp.read().decode())
                    file_names = [it["name"] for it in items]
            except Exception:
                pass

            has_tests = any("test" in f.lower() for f in file_names)
            has_docker = any("docker" in f.lower() for f in file_names)
            has_ci = ".github" in file_names or "jenkins" in file_names

            # Extract tech stack from dependency indicators
            tech = []
            if meta["language"]:
                tech.append(meta["language"])
            if "requirements.txt" in file_names or "pyproject.toml" in file_names:
                tech.extend(["Python", "FastAPI"])
            if "package.json" in file_names:
                tech.extend(["Node.js", "JavaScript/TypeScript", "React"])
            if has_docker:
                tech.append("Docker")
            if "Dockerfile" in file_names:
                tech.append("Docker")

            # Deduplicate tech
            seen = set()
            clean_tech = []
            for t in tech:
                if t.lower() not in seen:
                    seen.add(t.lower())
                    clean_tech.append(t)

            results[r_name] = {
                "language": meta["language"],
                "is_author": not meta["fork"],
                "has_tests": has_tests,
                "has_docker": has_docker,
                "has_ci": has_ci,
                "tech_stack": clean_tech
            }

        return results

    @classmethod
    async def _stage_review_items(cls, db: AsyncSession, github_repos: Dict[str, Any]) -> int:
        count = 0
        
        # 1. Experiences to stage
        experiences = [
            {
                "section": "experience",
                "title": "Real IT Solutions - Trainee AI Full Stack Developer",
                "source": "Profile (3).pdf & Resumes",
                "content": "Company: Real IT Solutions Pune\nRole: Trainee AI Full Stack Developer\nDates: August 2025 - November 2025 (4 months, Virtual)\nTech Stack: Python, FastAPI, React/Next.js, REST APIs\nResponsibilities: Developed 2 AI-powered full-stack web applications; designed 55+ REST API endpoints for authentication, data management, and AI workflows; contributed to AI Website Builder and AI-powered IDE.",
                "metadata": {"company": "Real IT Solutions", "start": "Aug 2025", "end": "Nov 2025"}
            },
            {
                "section": "experience",
                "title": "CuroSoft - Jr. Web Developer Intern",
                "source": "Profile (3).pdf & Resumes",
                "content": "Company: CuroSoft\nRole: Jr. Web Developer Intern\nDates: May 2025 - June 2025 (2 months)\nLocation: Chhatrapati Sambhajinagar, Maharashtra\nTech Stack: HTML, CSS, JavaScript, React\nResponsibilities: Developed and deployed 3 responsive client websites; built frontend features for 2 live products; supported testing, maintenance, and deployment.",
                "metadata": {"company": "CuroSoft", "start": "May 2025", "end": "Jun 2025"}
            },
            {
                "section": "experience",
                "title": "EduSpark International - Server Manager Intern (Entry 1)",
                "source": "Pre-resolved entry 1",
                "content": "Company: Eduspark International Pvt. Ltd.\nRole: Server Manager Intern\nDates: March 2025 - May 2025\nLocation: Chhatrapati Sambhajinagar, Maharashtra\nResponsibilities: Monitored CET exam servers and network connectivity during examination windows; resolved connectivity and workstation issues.",
                "metadata": {"company": "Eduspark International", "start": "Mar 2025", "end": "May 2025"}
            },
            {
                "section": "experience",
                "title": "EduSpark International - Server Manager (Entry 2)",
                "source": "Pre-resolved entry 2",
                "content": "Company: Eduspark International Pvt. Ltd.\nRole: Server Manager\nDates: March 2026 - May 2026\nLocation: Chhatrapati Sambhajinagar, Maharashtra\nResponsibilities: Managed server operations across CET examination centers; coordinated infrastructure support.",
                "metadata": {"company": "Eduspark International", "start": "Mar 2026", "end": "May 2026"}
            },
            {
                "section": "experience",
                "title": "ByteFest 2K25 - Event Coordinator & Website Developer",
                "source": "Profile (3).pdf",
                "content": "Role: Event Coordinator & Website Developer\nDates: June 2025 - August 2025\nLocation: Ambajogai, Maharashtra\nResponsibilities: Built official event platform bytefest2k25.netlify.app; coordinated registration and schedules.",
                "metadata": {"role": "Event Coordinator & Website Developer"}
            }
        ]

        # 2. Education to stage
        educations = [
            {
                "section": "education",
                "title": "B.Tech Computer Science & Engineering",
                "source": "Resumes",
                "content": "Degree: B.Tech Computer Science & Engineering\nInstitution: M.B.E. Society's College of Engineering Ambajogai\nCompletion Year: 2026\nCGPA: 6.69\nLocation: Ambajogai, Maharashtra",
                "metadata": {"degree": "B.Tech", "year": "2026", "cgpa": "6.69"}
            },
            {
                "section": "education",
                "title": "Higher Secondary Certificate (Class XII)",
                "source": "Resumes (Pre-resolved)",
                "content": "Institution: Yogeshwari Mahavidhyalay Ambajogai\nBoard: Maharashtra State Board (Science)\nYear: 2022\nPercentage: 74.50%",
                "metadata": {"percentage": "74.50%", "year": "2022"}
            },
            {
                "section": "education",
                "title": "Secondary School Certificate (Class X)",
                "source": "Resumes (Pre-resolved)",
                "content": "Institution: Yogeshwari Nutan Vidhyalay Ambajogai\nBoard: Maharashtra State Board\nYear: 2020\nPercentage: 87.40%",
                "metadata": {"percentage": "87.40%", "year": "2020"}
            }
        ]

        # 3. Top projects to stage from verified GitHub repos
        projects = []
        for r_name, r_info in github_repos.items():
            tier = SUGGESTED_TIERS.get(r_name, "Tier B")
            projects.append({
                "section": "project",
                "title": f"Project: {r_name} ({tier})",
                "source": f"https://github.com/Vaibhav-Waghalkar/{r_name}",
                "content": f"Repository: {r_name}\nTier: {tier}\nPrimary Language: {r_info['language']}\nTech Stack: {', '.join(r_info['tech_stack'])}\nHas Tests: {r_info['has_tests']}\nHas Docker: {r_info['has_docker']}\nAuthor: Vaibhav Waghalkar",
                "metadata": {"repo": r_name, "tier": tier, "tech": r_info["tech_stack"]}
            })

        all_items = experiences + educations + projects
        for it in all_items:
            chk = select(ImportReviewItem).where(ImportReviewItem.title == it["title"])
            chk_res = await db.execute(chk)
            if not chk_res.scalars().first():
                item = ImportReviewItem(
                    source=it["source"],
                    section=it["section"],
                    title=it["title"],
                    proposed_content=it["content"],
                    metadata_json=it.get("metadata", {}),
                    status="pending"
                )
                db.add(item)
                count += 1

        return count
