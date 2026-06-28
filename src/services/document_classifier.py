"""
Universal Document Intelligence — CAREER-OS-06

Every uploaded file is classified BEFORE any pipeline executes.
The CV extraction pipeline only runs for confirmed CVs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────────
# Magic-byte → format detection
# ─────────────────────────────────────────────────────────────────
_MAGIC_TABLE: list[tuple[bytes, str]] = [
    (b"%PDF",             "pdf"),
    (b"PK\x03\x04",      "docx"),        # ZIP container (DOCX/XLSX/PPTX)
    (b"\xff\xd8\xff",    "image"),       # JPEG
    (b"\x89PNG",         "image"),       # PNG
    (b"GIF87a",          "image"),       # GIF
    (b"GIF89a",          "image"),
    (b"BM",              "image"),       # BMP
    (b"\xd0\xcf\x11\xe0", "compound"),  # Compound Doc — .doc or .msg
    (b"MZ",              "executable"),  # DOS/Windows EXE/DLL — always rejected
]
_WEBP_RIFF   = b"RIFF"
_WEBP_MARKER = b"WEBP"

# Minimum extractable characters for a text-bearing document (PDF / Word / text)
# to be classified by content. Below this, the file has no usable text layer —
# e.g. a screenshot or scan exported as a PDF, or an empty file — and must NOT be
# pushed through CV extraction (it would only yield a misleading "poor quality"
# CV preview). Such files are tagged "no_text" so the router can route them away
# from the CV pipeline. (OCR/vision for these is handled separately, out of scope.)
_MIN_TEXT_CHARS = 25

# Minimum raw byte size for a near-empty file to be treated as a real "no_text"
# document (a screenshot / scan exported as a PDF carries image data and is at
# least several KB). Below this, a near-empty file is a tiny stub or corrupt
# upload, not a real image-only document — it is left to flow through the normal
# pipeline rather than being labelled no_text.
_MIN_DOC_BYTES = 1024


def detect_format(data: bytes, filename: str = "") -> str:
    """Return a format slug based on magic bytes, with filename extension as tiebreaker."""
    head = data[:16]

    # WebP: RIFF????WEBP
    if len(data) >= 12 and head[:4] == _WEBP_RIFF and data[8:12] == _WEBP_MARKER:
        return "image"

    for magic, fmt in _MAGIC_TABLE:
        if head[: len(magic)] == magic:
            if fmt == "compound":
                ext = Path(filename).suffix.lower().lstrip(".")
                return "msg" if ext == "msg" else "doc"
            return fmt

    # Fall back to extension
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext in {"jpg", "jpeg", "png", "gif", "bmp", "webp"}:
        return "image"
    if ext == "eml":
        return "eml"
    if ext == "msg":
        return "msg"
    return "text"


# ─────────────────────────────────────────────────────────────────
# Signal banks — used for content-based classification
# ─────────────────────────────────────────────────────────────────
_SIGNALS: dict[str, list[str]] = {
    "cv": [
        "work experience", "employment history", "professional experience", "career history",
        "education", "academic background", "university", "qualification", "degree",
        "skills", "competencies", "areas of expertise", "technical skills",
        "objective", "career objective", "professional summary", "personal profile",
        "curriculum vitae", " cv ", "resume", "curriculum",
        "nationality", "date of birth", "visa status", "driving license", "marital status",
        "references available", "linkedin.com/in/", "github.com/",
        "seeking", "seeking a position", "open to opportunities",
        "key achievements", "notable projects", "internship",
    ],
    "job_description": [
        "job title", "position:", "role:", "department:", "reporting to",
        "key responsibilities", "your responsibilities", "responsibilities include", "you will",
        "requirements:", "qualifications:", "must have", "should have", "nice to have",
        "we are looking for", "we're looking for", "we are seeking", "ideal candidate",
        "apply now", "how to apply", "to apply for", "application deadline",
        "salary:", "compensation:", "benefits:", "perks:", "package:", "salary range",
        "about the company", "about the role", "about us", "about the position",
        "equal opportunity employer", "job description", "position summary",
        "minimum experience", "preferred qualifications", "essential requirements",
    ],
    "cover_letter": [
        "dear hiring manager", "dear sir", "dear madam", "to whom it may concern",
        "dear recruiter", "i am writing to apply", "i am writing to express",
        "i am applying", "i wish to apply", "please find attached", "enclosed please find",
        "yours sincerely", "yours faithfully", "kind regards", "best regards",
        "application for the position", "for the role of", "i believe my experience",
        "i am confident", "i would welcome", "thank you for considering",
        "i look forward to hearing", "i look forward to an opportunity",
        "i am excited to apply", "my enclosed resume",
    ],
    "offer_letter": [
        "we are pleased to offer", "we are delighted to offer", "we would like to offer",
        "offer of employment", "job offer", "employment offer", "letter of offer",
        "start date:", "commencement date:", "joining date:", "effective date:",
        "base salary", "annual salary", "monthly salary", "total compensation", "salary package",
        "upon acceptance", "please sign", "countersign", "please accept this offer",
        "probation period", "notice period", "terms of employment",
        "benefit package", "health insurance", "annual leave entitlement",
        "we look forward to welcoming you",
    ],
    "contract": [
        "this agreement", "this contract", "employment agreement", "service agreement",
        "whereas ", "hereby agree", "parties agree", "the parties",
        "terms and conditions", "hereinafter", "referred to as the",
        "governing law", "jurisdiction", "dispute resolution", "arbitration",
        "termination of employment", "severance payment", "force majeure",
        "confidentiality", "non-disclosure agreement", "intellectual property",
        "indemnification", "limitation of liability", "breach of contract",
        "witnessed by", "signed and sealed", "in witness whereof",
        "schedule", "exhibit", "appendix",
    ],
    "recruiter_email": [
        "i am reaching out", "i came across your profile", "found your profile",
        "exciting opportunity", "excellent opportunity", "great opportunity", "unique opportunity",
        "job opportunity", "career opportunity", "position available", "open role",
        "would you be interested", "are you open to", "would you like to discuss",
        "on behalf of our client", "our client is looking", "my client",
        "talent acquisition", "headhunter", "executive search", "staffing",
        "from:", "to:", "subject:", "date:", "reply-to:",
        "mime-version:", "content-type:", "message-id:",
    ],
    "certificate": [
        "this is to certify", "we hereby certify", "it is hereby certified",
        "certificate of", "awarded to", "has successfully completed",
        "accredited by", "issued by", "certified by", "authorized by",
        "valid until", "expires on", "expiry date", "expiration date:",
        "accreditation number", "diploma", "professional development",
        "in recognition of", "this certifies that", "completion of",
        "awarded this", "presented to",
    ],
    "invoice": [
        "invoice #", "invoice no", "invoice no.", "invoice number", "invoice date",
        "bill to", "billing address", "ship to", "sold to",
        "total amount due", "amount due", "payment due", "balance due",
        "subtotal", "tax amount", "vat", "grand total", "total:",
        "payment terms", "bank details", "account number", "iban", "swift",
        "unit price", "quantity", "line items", "description of services",
        "purchase order", "po number", "due date:",
    ],
    "identity_document": [
        "passport number", "passport no", "passport no.", "emirates id",
        "eid no", "eid number", "national id", "national id number",
        "identity card number", "machine readable zone", "mrz",
        "place of birth", "issuing authority", "رقم جواز السفر",
        "الهوية الإماراتية", "رقم بطاقة الهوية",
    ],
    "company_profile": [
        "company profile", "corporate profile", "company overview", "corporate overview",
        "our mission", "our vision", "our values", "our culture",
        "core services", "service portfolio", "sectors served", "industries served",
        "client base", "why choose us", "why clients choose", "our clients",
        "founded in", "established in", "years in business",
        "global presence", "offices worldwide", "subsidiaries", "group of companies",
        "management team", "board of directors", "executive team",
    ],
}

_DISPLAY_LABELS: dict[str, str] = {
    "cv":                "Resume / CV",
    "job_description":   "Job Description",
    "cover_letter":      "Cover Letter",
    "offer_letter":      "Offer Letter",
    "contract":          "Employment Contract",
    "recruiter_email":   "Recruiter Email",
    "certificate":       "Certificate / License",
    "identity_document": "Identity Document",
    "company_profile":   "Company Profile",
    "invoice":           "Invoice",
    "image":             "Image",
    "no_text":           "Unreadable / Image-only Document",
    "unknown":           "Document",
}

_SUGGESTED_ACTIONS: dict[str, list[dict[str, str]]] = {
    "cv": [
        {"label": "Confirm and save to profile", "kind": "chat_continue",
         "message": "Yes, save this CV to my profile."},
        {"label": "Show what was extracted",     "kind": "chat_continue",
         "message": "Show me what you extracted from my CV."},
        {"label": "Identify gaps",               "kind": "chat_continue",
         "message": "What's missing or weak in my CV?"},
    ],
    "job_description": [
        {"label": "Score against my CV",   "kind": "chat_continue",
         "message": "Score this job description against my current CV."},
        {"label": "Generate tailored CV",  "kind": "chat_continue",
         "message": "Generate a tailored CV for this job."},
        {"label": "Generate cover letter", "kind": "chat_continue",
         "message": "Generate a cover letter for this job."},
        {"label": "Save as target job",    "kind": "chat_continue",
         "message": "Save this as a target job in my pipeline."},
    ],
    "cover_letter": [
        {"label": "Review and improve", "kind": "chat_continue",
         "message": "Review my cover letter and suggest improvements."},
        {"label": "Tailor for a job",   "kind": "chat_continue",
         "message": "Help me tailor this cover letter for a specific job."},
        {"label": "Tone check",         "kind": "chat_continue",
         "message": "Is the tone of my cover letter professional and engaging?"},
    ],
    "offer_letter": [
        {"label": "Summarize key terms",  "kind": "chat_continue",
         "message": "Summarize the key terms in this offer letter."},
        {"label": "Flag concerns",        "kind": "chat_continue",
         "message": "Are there any concerns or unusual clauses in this offer?"},
        {"label": "Compare with market",  "kind": "chat_continue",
         "message": "How does this compensation compare to UAE market rates?"},
    ],
    "contract": [
        {"label": "Summarize",               "kind": "chat_continue",
         "message": "Summarize the key points of this contract."},
        {"label": "Extract important dates", "kind": "chat_continue",
         "message": "What are the important dates and deadlines in this contract?"},
        {"label": "Flag risks",              "kind": "chat_continue",
         "message": "Are there risky or unusual clauses I should know about?"},
    ],
    "recruiter_email": [
        {"label": "Extract role details", "kind": "chat_continue",
         "message": "Extract the job role, company, salary, and deadline from this email."},
        {"label": "Draft a reply",        "kind": "chat_continue",
         "message": "Draft a professional reply to this recruiter."},
        {"label": "Save opportunity",     "kind": "chat_continue",
         "message": "Save this as an opportunity in my pipeline."},
    ],
    "certificate": [
        {"label": "Add to profile",            "kind": "chat_continue",
         "message": "Add this certificate to my professional profile."},
        {"label": "Extract issuer and expiry", "kind": "chat_continue",
         "message": "Extract the issuer, issue date, and expiry from this certificate."},
    ],
    "identity_document": [],  # Blocked for security — no actions offered
    "no_text": [],            # No readable text — router returns a needs-text message
    "company_profile": [
        {"label": "Summarize",              "kind": "chat_continue",
         "message": "Summarize this company profile."},
        {"label": "Research for interview", "kind": "chat_continue",
         "message": "Use this company profile to prepare me for an interview."},
    ],
    "invoice": [
        {"label": "Summarize",      "kind": "chat_continue",
         "message": "Summarize this invoice."},
        {"label": "Extract totals", "kind": "chat_continue",
         "message": "Extract the total amounts and payment terms from this invoice."},
    ],
    "image": [
        {"label": "Describe this image", "kind": "chat_continue",
         "message": "Describe what's in this image."},
        {"label": "Extract text (OCR)",  "kind": "chat_continue",
         "message": "Extract any visible text from this image."},
        # Finding 3: job-screenshot → save/score actions. Handler checks for
        # extracted_text and guides user to extract first if not yet read.
        {"label": "Save as target job",    "kind": "chat_continue",
         "message": "Save this as a target job in my pipeline."},
        {"label": "Score against my CV",   "kind": "chat_continue",
         "message": "Score this job description against my current CV."},
    ],
    "unknown": [
        {"label": "Summarize",               "kind": "chat_continue",
         "message": "Summarize this document for me."},
        {"label": "Extract key information", "kind": "chat_continue",
         "message": "Extract the most important information from this document."},
    ],
}


# ─────────────────────────────────────────────────────────────────
# Result model
# ─────────────────────────────────────────────────────────────────
@dataclass
class ClassificationResult:
    document_type: str
    confidence: float                            # 0.0 – 1.0
    confidence_scores: dict[str, float]          # all type→score pairs (non-zero only)
    suggested_actions: list[dict[str, str]]
    display_label: str
    file_format: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_type":    self.document_type,
            "confidence":       round(self.confidence, 3),
            "confidence_scores": {k: round(v, 3) for k, v in self.confidence_scores.items()},
            "suggested_actions": self.suggested_actions,
            "display_label":    self.display_label,
            "file_format":      self.file_format,
            "metadata":         self.metadata,
        }


# ─────────────────────────────────────────────────────────────────
# Classifier
# ─────────────────────────────────────────────────────────────────
class DocumentClassifier:
    """
    Classify an uploaded file from its bytes alone — no pipeline assumptions.

    Returns a ClassificationResult with document_type, confidence (0–1),
    per-type score breakdown, suggested actions, and display label.
    """

    # CV pipeline only runs when the top classification is cv AND confidence ≥ this.
    CV_THRESHOLD = 0.50

    def classify(self, data: bytes, filename: str = "") -> ClassificationResult:
        file_format = detect_format(data, filename)

        # Executables are always rejected — return as a distinct type so the
        # router can return 422 without attempting any content extraction.
        if file_format == "executable":
            return self._make(
                "executable", 1.0, {"executable": 1.0}, file_format,
                metadata={"filename": filename},
            )

        # Images are trivially classified — no text to extract.
        if file_format == "image":
            return self._make(
                "image", 1.0, {"image": 1.0}, file_format,
                metadata={"filename": filename},
            )

        # Email containers are classified by format before text analysis.
        if file_format in ("eml", "msg"):
            text = self._extract_text(data, file_format)
            # Check content for stronger signal
            if text and any(s in text.lower() for s in _SIGNALS["recruiter_email"][:5]):
                conf = 0.88
            else:
                conf = 0.75
            return self._make(
                "recruiter_email", conf, {"recruiter_email": conf}, file_format,
                metadata={"chars": len(text)},
            )

        text = self._extract_text(data, file_format)

        # No-text / image-only documents: a screenshot or scan exported as a PDF.
        # There is no text layer to classify or extract, so the CV parser would only
        # produce a misleading "poor quality" CV preview (#674 residual). Tag these
        # distinctly so the router never routes them into CV extraction. Only real
        # documents (>= _MIN_DOC_BYTES of image data) qualify — tiny stubs / corrupt
        # uploads are left to the normal pipeline.
        if len(text.strip()) < _MIN_TEXT_CHARS and len(data) >= _MIN_DOC_BYTES:
            return self._make(
                "no_text", 0.9, {"no_text": 0.9}, file_format,
                metadata={"chars": len(text)},
            )

        return self._classify_text(text, file_format, filename)

    # ── Text extraction ───────────────────────────────────────────

    def _extract_text(self, data: bytes, file_format: str) -> str:
        if file_format == "pdf":
            return self._extract_pdf(data)
        if file_format in ("docx", "doc"):
            return self._extract_docx(data)
        # Plain text (txt, eml, unknown)
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                return data.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return data.decode("utf-8", errors="ignore")

    def _extract_pdf(self, data: bytes) -> str:
        try:
            import fitz  # type: ignore[import]
            doc = fitz.open(stream=data, filetype="pdf")
            return "\n".join(page.get_text() for page in doc)
        except Exception:
            pass
        return data.decode("latin-1", errors="ignore")

    def _extract_docx(self, data: bytes) -> str:
        try:
            import docx  # type: ignore[import]
            import io
            doc = docx.Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            pass
        return data.decode("utf-8", errors="ignore")

    # ── Content classification ────────────────────────────────────

    def _classify_text(
        self, text: str, file_format: str, filename: str = ""
    ) -> ClassificationResult:
        lower = text.lower()

        raw_scores: dict[str, float] = {}
        for doc_type, signals in _SIGNALS.items():
            hits = sum(1 for s in signals if s in lower)
            raw_scores[doc_type] = hits / max(len(signals), 1)

        if not raw_scores or max(raw_scores.values()) == 0.0:
            return self._make(
                "unknown", 0.0, {}, file_format, metadata={"chars": len(text)}
            )

        # Boost identity_document slightly — it has fewer but very specific signals.
        if raw_scores.get("identity_document", 0) > 0:
            raw_scores["identity_document"] = min(
                raw_scores["identity_document"] * 2.0, 1.0
            )

        # Sort descending
        ranked = sorted(raw_scores.items(), key=lambda x: x[1], reverse=True)
        top_type, top_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0

        # Confidence = top score, penalized when runner-up is close.
        gap = top_score - second_score
        confidence = top_score * (0.65 + 0.35 * min(gap / 0.15, 1.0))
        confidence = round(min(confidence, 0.97), 3)

        # Hard override: identity_document with any signal + no CV signals wins.
        if (
            raw_scores.get("identity_document", 0) > 0.1
            and raw_scores.get("cv", 0) < 0.15
        ):
            top_type = "identity_document"
            confidence = 0.92

        non_zero = {k: round(v, 3) for k, v in raw_scores.items() if v > 0}
        return self._make(
            top_type, confidence, non_zero, file_format,
            metadata={"chars": len(text)},
        )

    # ── Factory ───────────────────────────────────────────────────

    def _make(
        self,
        doc_type: str,
        confidence: float,
        scores: dict[str, float],
        file_format: str,
        metadata: dict[str, Any] | None = None,
    ) -> ClassificationResult:
        return ClassificationResult(
            document_type=doc_type,
            confidence=confidence,
            confidence_scores=scores,
            suggested_actions=_SUGGESTED_ACTIONS.get(
                doc_type, _SUGGESTED_ACTIONS["unknown"]
            ),
            display_label=_DISPLAY_LABELS.get(doc_type, "Document"),
            file_format=file_format,
            metadata=metadata or {},
        )


# Module-level singleton
_classifier = DocumentClassifier()


def classify_document(data: bytes, filename: str = "") -> ClassificationResult:
    """Classify an uploaded file. Thread-safe — classifier is stateless."""
    return _classifier.classify(data, filename)
