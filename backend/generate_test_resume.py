import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_sample_candidate_resume_pdf(target_path: str):
    """
    Generates a realistic sample candidate resume PDF for local testing.
    """
    doc = SimpleDocTemplate(target_path, pagesize=letter)
    styles = getSampleStyleSheet()

    story = [
        Paragraph("<b>Alex Morgan</b>", styles["Title"]),
        Paragraph("alex.morgan@example.com | +1-555-0199 | https://github.com/alexmorgan", styles["Normal"]),
        Spacer(1, 12),
        Paragraph("<b>EDUCATION</b>", styles["Heading2"]),
        Paragraph("University of Washington - B.S. in Computer Science (2018 - 2022) | 3.8 GPA", styles["Normal"]),
        Spacer(1, 8),
        Paragraph("<b>EXPERIENCE</b>", styles["Heading2"]),
        Paragraph("<b>Backend Software Engineer</b> - CloudPulse Data (2022 - Present)", styles["Normal"]),
        Paragraph("Built distributed REST APIs using Python and FastAPI. Optimized database indexing on PostgreSQL.", styles["Normal"]),
        Spacer(1, 8),
        Paragraph("<b>PROJECTS</b>", styles["Heading2"]),
        Paragraph("<b>PulseCache Redis Agent</b>", styles["Normal"]),
        Paragraph("Engineered an async cache invalidation worker in Python and Redis. Stack: Python, Redis, Docker.", styles["Normal"]),
        Spacer(1, 8),
        Paragraph("<b>SKILLS</b>", styles["Heading2"]),
        Paragraph("Python, FastAPI, PostgreSQL, Redis, Docker", styles["Normal"]),
        Spacer(1, 8),
        Paragraph("<b>CERTIFICATIONS</b>", styles["Heading2"]),
        Paragraph("AWS Certified Developer - Associate (2023)", styles["Normal"])
    ]

    doc.build(story)

if __name__ == "__main__":
    generate_sample_candidate_resume_pdf("data/sample_alex_resume.pdf")
    print("Sample resume PDF generated.")
