import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class FixedProfile(Base):
    """
    Fixed profile table, strictly never LLM generated.
    Stores authoritative user facts.
    Notice period, CTC, DOB, city stay null until entered by user or confirmed.
    """
    __tablename__ = "fixed_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(255), nullable=True)
    date_of_birth = Column(String(50), nullable=True) # YYYY-MM-DD - NULL until user inputs
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True) # City, State - NULL until user inputs
    notice_period_days = Column(Integer, nullable=True) # NULL until user inputs
    current_ctc = Column(String(100), nullable=True) # NULL until user inputs
    expected_ctc = Column(String(100), nullable=True) # NULL until user inputs
    total_experience_years = Column(Float, nullable=True)
    links = Column(JSON, default=dict) # {"github": "...", "linkedin": "...", "portfolio": "..."}
    languages = Column(JSON, default=list)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class VaultFact(Base):
    """
    Granular fact unit embedded into ChromaDB and stored in SQLite with a stable fact ID.
    Only verified=True facts are accessible to the matcher and answer engine.
    """
    __tablename__ = "vault_facts"

    id = Column(String(100), primary_key=True)
    section = Column(String(50), nullable=False) # personal, education, experience, project, skill, certification, achievement, standard_qa
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict)
    content_hash = Column(String(64), nullable=False)
    verified = Column(Boolean, default=False) # STRICT: Only verified facts enter matcher/answer engine
    source = Column(String(255), nullable=True) # e.g. resume_Backend_v1.pdf or user_interactive
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class Resume(Base):
    """
    Role-tagged resumes with versioning.
    """
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_tag = Column(String(100), nullable=False) # "Backend", "Python", "Full Stack"
    version = Column(Integer, nullable=False, default=1)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    parsed_text = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)

class DocumentVault(Base):
    """
    Document proofs (marksheets, degrees, ID proofs, certificates).
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_type = Column(String(100), nullable=False) # degree, marksheet, id_proof, pan, aadhaar, certificate
    name = Column(String(255), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    extracted_text = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)

class JobPreference(Base):
    """
    Target roles, salary bounds, daily caps, and mode settings.
    """
    __tablename__ = "job_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    target_roles = Column(JSON, default=list)
    min_salary = Column(Float, nullable=True)
    max_salary = Column(Float, nullable=True)
    preferred_locations = Column(JSON, default=list)
    work_modes = Column(JSON, default=list) # remote, hybrid, on-site
    must_have_skills = Column(JSON, default=list)
    blacklisted_companies = Column(JSON, default=list)
    daily_caps = Column(JSON, default=dict) # {"internshala": 20, "career_page": 20}
    default_match_threshold = Column(Integer, default=70)
    mode = Column(String(20), default="REVIEW") # DRY_RUN, REVIEW, AUTO
    auto_submit_platforms = Column(JSON, default=list) # e.g. ["internshala"]
    active_role_tag = Column(String(100), nullable=True) # Role + Resume run config
    active_resume_id = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class ImportReviewItem(Base):
    """
    Staging table for extracted resume items or scraped data.
    Requires human review / bulk approval before becoming verified facts.
    """
    __tablename__ = "import_review_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(255), nullable=False) # e.g. "resume_backend_v1.pdf"
    section = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    proposed_content = Column(Text, nullable=False)
    conflict_detected = Column(Boolean, default=False)
    conflict_details = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict)
    status = Column(String(20), default="pending") # pending, approved, rejected, edited
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class SavedQuestionAnswer(Base):
    """
    Persistent store of questions previously answered by user.
    Checked in field-resolution hierarchy step (3) so the user is never asked twice.
    """
    __tablename__ = "saved_qa"

    id = Column(Integer, primary_key=True, autoincrement=True)
    normalized_question = Column(String(500), nullable=False, unique=True, index=True)
    raw_question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    verified = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class JobApplication(Base):
    """
    Job application tracking record.
    Stores status, resume version, match score, submitted answers with sources, and outcome.
    """
    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False)
    job_id_external = Column(String(255), nullable=True)
    company = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    salary_raw = Column(String(255), nullable=True)
    apply_url = Column(Text, nullable=False)
    job_description = Column(Text, nullable=True)
    
    # Discovery & Match
    status = Column(String(50), default="discovered") # discovered, matched, skipped, needs_you, applied, failed
    match_score = Column(Integer, nullable=True)
    match_reasons = Column(JSON, default=dict)
    skip_reason = Column(String(255), nullable=True)
    
    # Application execution
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=True)
    resume_version_used = Column(String(100), nullable=True)
    answers_submitted = Column(JSON, default=dict) # {"question": {"answer": "...", "source": "fixed_profile|fact_id|user_answer"}}
    
    # Blocker / "Needs You" flow
    needs_you_reason = Column(Text, nullable=True)
    needs_you_question = Column(Text, nullable=True)
    needs_you_screenshot = Column(Text, nullable=True)
    needs_you_state = Column(JSON, default=dict) # {page_num, filled_fields, current_url}
    needs_you_timestamp = Column(DateTime, nullable=True)
    
    # Manual outcome tracking
    outcome = Column(String(50), default="no_response") # no_response, screening_call, interview, offer, rejected
    outcome_updated_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    applied_at = Column(DateTime, nullable=True)

class ActivityLog(Base):
    """Activity log stream displayed on live dashboard view."""
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String(20), default="INFO")
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
