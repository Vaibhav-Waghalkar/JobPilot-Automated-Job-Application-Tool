import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

def generate_biodata_pdf_bytes(profile: dict, facts: list) -> bytes:
    """
    Generates a minimalist, elegant, readable PDF of the user's full profile
    directly from authoritative vault facts.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    
    # Custom minimalist styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1e293b"),
        alignment=TA_LEFT,
    )
    
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569"),
        alignment=TA_LEFT,
    )
    
    section_head_style = ParagraphStyle(
        "SectionHead",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=10,
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
    )
    
    body_bold = ParagraphStyle(
        "BodyBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#0f172a"),
    )

    story = []

    # Header with Fixed Profile data
    full_name = profile.get("full_name", "Applicant Profile")
    email = profile.get("email", "")
    phone = profile.get("phone", "")
    location = profile.get("location", "")
    exp = profile.get("total_experience_years", "")
    links = profile.get("links", {})
    links_str = " | ".join(f"{k}: {v}" for k, v in links.items() if v)

    story.append(Paragraph(full_name, title_style))
    contact_line = f"{email} | {phone} | {location} | Total Experience: {exp} Years"
    story.append(Spacer(1, 4))
    story.append(Paragraph(contact_line, subtitle_style))
    if links_str:
        story.append(Paragraph(links_str, subtitle_style))
    
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceBefore=4, spaceAfter=8))

    # Group facts by section
    facts_by_section = {}
    for f in facts:
        sec = f.get("section", "other")
        facts_by_section.setdefault(sec, []).append(f)

    # 1. Experience
    if "experience" in facts_by_section:
        story.append(Paragraph("EXPERIENCE", section_head_style))
        for item in facts_by_section["experience"]:
            title = item.get("title", "")
            content = item.get("content", "").replace("\n", "<br/>")
            story.append(Paragraph(f"<b>{title}</b>", body_bold))
            story.append(Paragraph(content, body_style))
            story.append(Spacer(1, 6))

    # 2. Projects
    if "project" in facts_by_section:
        story.append(Paragraph("PROJECTS", section_head_style))
        for item in facts_by_section["project"]:
            title = item.get("title", "")
            content = item.get("content", "").replace("\n", "<br/>")
            story.append(Paragraph(f"<b>{title}</b>", body_bold))
            story.append(Paragraph(content, body_style))
            story.append(Spacer(1, 6))

    # 3. Skills
    if "skill" in facts_by_section:
        story.append(Paragraph("SKILLS INVENTORY", section_head_style))
        skill_texts = [f"• {item.get('title')}: {item.get('content')}".replace("\n", " | ") for item in facts_by_section["skill"]]
        for st in skill_texts:
            story.append(Paragraph(st, body_style))
        story.append(Spacer(1, 6))

    # 4. Education
    if "education" in facts_by_section:
        story.append(Paragraph("EDUCATION", section_head_style))
        for item in facts_by_section["education"]:
            content = item.get("content", "").replace("\n", "<br/>")
            story.append(Paragraph(content, body_style))
            story.append(Spacer(1, 6))

    # 5. Certifications
    if "certification" in facts_by_section:
        story.append(Paragraph("CERTIFICATIONS", section_head_style))
        for item in facts_by_section["certification"]:
            content = item.get("content", "").replace("\n", "<br/>")
            story.append(Paragraph(content, body_style))
            story.append(Spacer(1, 6))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
