"""Tests for the Document Intelligence classifier (CAREER-OS-06)."""
import pytest
from src.services.document_classifier import classify_document, detect_format


# ── Format detection ──────────────────────────────────────────────────────────

def test_detect_pdf():
    assert detect_format(b"%PDF-1.4 content", "resume.pdf") == "pdf"


def test_detect_docx():
    assert detect_format(b"PK\x03\x04more data", "cv.docx") == "docx"


def test_detect_jpeg():
    assert detect_format(b"\xff\xd8\xffbody", "photo.jpg") == "image"


def test_detect_png():
    assert detect_format(b"\x89PNGbody", "screenshot.png") == "image"


def test_detect_gif():
    assert detect_format(b"GIF89abody", "anim.gif") == "image"


def test_detect_webp():
    data = b"RIFF\x00\x00\x00\x00WEBPbody"
    assert detect_format(data, "image.webp") == "image"


def test_detect_eml():
    assert detect_format(b"From: sender@example.com\r\nSubject: Hi", "mail.eml") == "eml"


def test_detect_msg_by_extension():
    assert detect_format(b"\xd0\xcf\x11\xe0body", "outlook.msg") == "msg"


def test_detect_doc_compound():
    assert detect_format(b"\xd0\xcf\x11\xe0body", "word.doc") == "doc"


# ── Image classification ──────────────────────────────────────────────────────

def test_classify_image_png():
    r = classify_document(b"\x89PNGbody" + b"\x00" * 100, "screenshot.png")
    assert r.document_type == "image"
    assert r.confidence == 1.0
    assert len(r.suggested_actions) > 0


def test_classify_image_jpeg():
    r = classify_document(b"\xff\xd8\xffbody" + b"\x00" * 100, "photo.jpeg")
    assert r.document_type == "image"


# ── Email classification ──────────────────────────────────────────────────────

def test_classify_eml():
    r = classify_document(b"From: recruiter@agency.com\r\nSubject: Job Opportunity", "email.eml")
    assert r.document_type == "recruiter_email"
    assert r.confidence >= 0.70


# ── Content-based classification ──────────────────────────────────────────────

def _text(s: str) -> bytes:
    return s.encode()


def test_classify_cv():
    text = _text(
        "John Smith. Professional Summary: Experienced engineer seeking senior role. "
        "Work Experience: Software Engineer at TechCo 2018-2024. "
        "Education: BSc Computer Science, University of Dubai. "
        "Skills: Python, SQL, project management. "
        "Nationality: British. Date of birth: 1985. "
        "References available upon request. linkedin.com/in/johnsmith"
    )
    r = classify_document(text, "resume.txt")
    assert r.document_type == "cv"
    assert any(a["label"] == "Confirm and save to profile" for a in r.suggested_actions)


def test_classify_job_description():
    text = _text(
        "Job Title: Senior Data Scientist. Department: Analytics. Reporting to: VP Data. "
        "Key Responsibilities: You will build ML models and present insights. "
        "Requirements: Must have 5+ years Python experience. Should have SQL skills. "
        "We are looking for a motivated individual. Apply now. "
        "Salary: AED 25000 per month. Benefits: Health insurance, annual leave. "
        "About the company: Leading fintech in the UAE."
    )
    r = classify_document(text, "jd.txt")
    assert r.document_type == "job_description"
    assert any("Score" in a["label"] for a in r.suggested_actions)


def test_classify_contract():
    text = _text(
        "EMPLOYMENT AGREEMENT. This Agreement is entered into by the parties. "
        "The employee hereby agrees to the terms and conditions hereinafter. "
        "Governing law: UAE. Termination of employment requires 30 days notice. "
        "Confidentiality and non-disclosure obligations apply indefinitely. "
        "Indemnification clause: employee shall indemnify the company. "
        "In witness whereof the parties have signed this agreement."
    )
    r = classify_document(text, "contract.txt")
    assert r.document_type == "contract"
    assert any("Summarize" in a["label"] for a in r.suggested_actions)


def test_classify_offer_letter():
    text = _text(
        "We are pleased to offer you the position of Product Manager. "
        "Start date: 1 July 2026. Base salary: AED 18000 per month. "
        "Annual salary package includes health insurance and annual leave entitlement. "
        "Please countersign and return this offer letter. "
        "We look forward to welcoming you to the team."
    )
    r = classify_document(text, "offer.txt")
    assert r.document_type == "offer_letter"
    assert any("Summarize" in a["label"] for a in r.suggested_actions)


def test_classify_certificate():
    text = _text(
        "This is to certify that John Smith has successfully completed the "
        "NEBOSH Certificate in Occupational Health and Safety. "
        "Awarded to by accredited body. Certified by NEBOSH UK. "
        "Valid until December 2027. In recognition of outstanding performance."
    )
    r = classify_document(text, "cert.txt")
    assert r.document_type == "certificate"
    assert any("Add to profile" in a["label"] for a in r.suggested_actions)


def test_classify_cover_letter():
    text = _text(
        "Dear Hiring Manager, I am writing to apply for the Software Engineer position. "
        "Application for the role of Senior Developer. "
        "I believe my experience makes me a strong candidate. "
        "I look forward to hearing from you. "
        "Yours sincerely, Jane Doe"
    )
    r = classify_document(text, "cover.txt")
    assert r.document_type == "cover_letter"


def test_classify_identity_document():
    text = _text(
        "PASSPORT. Passport Number: P12345678. "
        "National ID Number: 784-1985-1234567-1. "
        "Place of birth: Abu Dhabi. Issuing authority: UAE Ministry."
    )
    r = classify_document(text, "passport.txt")
    assert r.document_type == "identity_document"
    # No actions should be returned for identity docs
    assert r.suggested_actions == []


def test_classify_unknown_returns_fallback_actions():
    r = classify_document(b"Lorem ipsum dolor sit amet.", "random.txt")
    assert r.document_type == "unknown"
    assert len(r.suggested_actions) > 0


# ── Confidence scores present ─────────────────────────────────────────────────

def test_confidence_scores_non_zero():
    text = _text("Work experience, skills, education, seeking a position at university.")
    r = classify_document(text, "cv.txt")
    assert r.confidence > 0
    assert isinstance(r.confidence_scores, dict)
    assert r.confidence_scores.get("cv", 0) > 0


# ── to_dict ───────────────────────────────────────────────────────────────────

def test_to_dict_shape():
    r = classify_document(b"\x89PNGbody" + b"\x00" * 20, "img.png")
    d = r.to_dict()
    assert "document_type" in d
    assert "confidence" in d
    assert "confidence_scores" in d
    assert "suggested_actions" in d
    assert "display_label" in d
    assert "file_format" in d
    assert isinstance(d["confidence"], float)
