"""CV parser service for Rico AI.

Additive module: does not change the existing job automation pipeline.
Supports PDF, DOCX, TXT, and plain bytes. Cloud deployment should install
optional dependencies: pymupdf and python-docx.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ParsedCV:
    text: str
    skills: List[str]
    emails: List[str]
    phones: List[str]
    years_experience_hint: Optional[float]
    certifications: List[str]
    languages: List[str]
    extraction_quality: str = "unknown"
    extracted_chars: int = 0
    name: Optional[str] = None
    current_role: Optional[str] = None
    document_type: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CVParser:
    COMMON_SKILLS = [
        "hse", "qhse", "ehs", "safety", "risk assessment", "iso 9001", "iso 14001", "iso 45001",
        "audit", "compliance", "esg", "sustainability", "environmental management", "incident investigation",
        "marketing", "seo", "google ads", "meta ads", "crm", "salesforce", "excel", "power bi",
        "python", "sql", "project management", "operations", "leadership", "training",
    ]

    CERT_HINTS = ["nebosh", "iosh", "iso", "pmp", "six sigma", "osha", "first aid"]
    LANGUAGE_HINTS = ["english", "arabic", "hindi", "urdu", "french", "tagalog"]

    # Unambiguous identity-document markers: passport number, Emirates ID, etc.
    # A single hit classifies the document as identity_document ONLY when no CV-section
    # signals are also present — this prevents misclassifying UAE-format CVs that
    # include an "Emirates ID:" or "Passport:" personal-details field.
    IDENTITY_SIGNALS = [
        "passport number",
        "passport no",
        "emirates id",
        "eid no",
        "eid number",
        "national id number",
        "national id no",
        "identity card number",
        "national identity number",
        "machine readable zone",
        "رقم جواز السفر",       # passport number (Arabic)
        "الهوية الإماراتية",    # Emirates identity (Arabic)
        "رقم بطاقة الهوية",     # ID card number (Arabic)
    ]

    # Strong signals that only appear in company-profile documents, not personal CVs.
    # Deliberately excludes "llc", "our services", "our mission", "our vision", "about us"
    # because those appear routinely in employer names and job descriptions inside CVs.
    COMPANY_SIGNALS = [
        "company profile",
        "corporate profile",
        "core service portfolio",
        "sectors served",
        "why clients",
        "client base",
        "service portfolio",
        "company overview",
    ]

    CV_SIGNALS = [
        "curriculum vitae",
        "resume",
        "work experience",
        "employment history",
        "education",
        "professional experience",
        "career summary",
        "career objective",
        "objective",
        "skills",
        "contact information",
    ]

    # First-person personal markers: if any of these appear, the document is
    # almost certainly a personal CV, not a company profile.
    PERSONAL_MARKERS = [
        "i am",
        "my name",
        "my experience",
        "i have",
        "my skills",
        "my background",
        "i worked",
        "i was",
        "i led",
        "i managed",
    ]

    # Unambiguous cover-letter openers / closings that cannot appear in CVs.
    COVER_LETTER_STRONG_SIGNALS = [
        "dear hiring manager",
        "dear recruiter",
        "i am writing to apply",
        "i am applying for",
        "i would like to apply for",
        "please consider my application",
    ]

    # Supporting cover-letter phrases — require 2+ alongside a strong signal,
    # or 3+ on their own, to avoid false positives from formal CV summaries.
    COVER_LETTER_SUPPORTING_SIGNALS = [
        "dear sir",
        "dear madam",
        "to whom it may concern",
        "sincerely",
        "yours faithfully",
        "yours sincerely",
        "application for",
        "please find attached",
        "enclosed please find",
        "for the position of",
    ]

    def detect_document_type(self, text: str) -> str:
        """Detect whether text is a CV, cover letter, company profile, identity document, or unknown."""
        lower = text.lower()

        # Personal markers are a strong veto against company_profile.
        has_personal_marker = any(m in lower for m in self.PERSONAL_MARKERS)

        company_score = sum(1 for s in self.COMPANY_SIGNALS if s in lower)
        cv_score = sum(1 for s in self.CV_SIGNALS if s in lower)

        # Identity documents (passport, Emirates ID, national ID): one strong signal is
        # sufficient when no CV-section headers are present. The cv_score == 0 guard
        # prevents misclassifying UAE-format CVs that include an "Emirates ID:" field
        # alongside work-experience and skills sections.
        has_identity = any(s in lower for s in self.IDENTITY_SIGNALS)
        if has_identity and cv_score == 0:
            return "identity_document"

        # Require ≥3 strong company signals AND no personal first-person language
        # to avoid false-positives on CVs that quote employer mission statements.
        if not has_personal_marker and company_score >= 3:
            return "company_profile"

        # A single unambiguous company-profile phrase ("company profile" /
        # "corporate profile") with no personal markers is sufficient.
        strong_company = {"company profile", "corporate profile"}
        has_strong_company = any(s in lower for s in strong_company)
        if not has_personal_marker and has_strong_company and company_score >= 2:
            return "company_profile"

        # Cover letter: distinct salutation/closing patterns that don't appear in CVs.
        cl_strong = sum(1 for s in self.COVER_LETTER_STRONG_SIGNALS if s in lower)
        cl_support = sum(1 for s in self.COVER_LETTER_SUPPORTING_SIGNALS if s in lower)
        if cl_strong >= 2 or (cl_strong >= 1 and cl_support >= 1) or cl_support >= 3:
            return "cover_letter"

        if cv_score >= 2:
            return "cv"
        # Personal markers alone are not sufficient — require at least one CV-section
        # signal so that first-person company bios are not misclassified as CVs.
        if has_personal_marker and cv_score >= 1:
            return "cv"

        return "unknown"

    def parse_file(self, path: str | Path) -> ParsedCV:
        path = Path(path)
        suffix = path.suffix.lower()
        data = path.read_bytes()
        if suffix == ".pdf":
            text = self._parse_pdf(data)
        elif suffix in {".docx", ".doc"}:
            text = self._parse_docx(data)
        else:
            text = data.decode("utf-8", errors="ignore")
        result = self.parse_text(text)
        result.document_type = self.detect_document_type(text)
        return result

    def parse_bytes(self, data: bytes, filename: str = "cv.txt") -> ParsedCV:
        suffix = Path(filename).suffix.lower()
        if suffix == ".pdf":
            text = self._parse_pdf(data)
        elif suffix in {".docx", ".doc"}:
            text = self._parse_docx(data)
        else:
            text = data.decode("utf-8", errors="ignore")
        result = self.parse_text(text)
        result.document_type = self.detect_document_type(text)
        return result

    def parse_text(self, text: str) -> ParsedCV:
        cleaned = re.sub(r"\s+", " ", text or "").strip()
        lower = cleaned.lower()
        emails = sorted(set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", cleaned)))
        phones = sorted(set(re.findall(r"(?:\+?\d[\d\s().-]{7,}\d)", cleaned)))[:5]
        skills = [skill for skill in self.COMMON_SKILLS if skill in lower]
        certifications = [cert for cert in self.CERT_HINTS if cert in lower]
        languages = [lang for lang in self.LANGUAGE_HINTS if lang in lower]
        years = self._extract_years(lower)

        char_count = len(cleaned)

        if char_count < 300:
            quality = "poor"
        elif char_count < 1000:
            quality = "partial"
        else:
            quality = "good"

        return ParsedCV(
            text=cleaned,
            skills=skills,
            emails=emails,
            phones=phones,
            years_experience_hint=years,
            certifications=certifications,
            languages=languages,
            extraction_quality=quality,
            extracted_chars=char_count,
            name=self._extract_name(text),
            current_role=self._extract_current_role(text),
        )

    _NAME_SECTION_KEYWORDS = frozenset({
        "objective", "summary", "profile", "education", "experience", "skills",
        "certifications", "languages", "contact", "address", "email", "phone",
        "curriculum", "vitae", "resume", "personal", "details", "linkedin",
        "nationality", "references", "declaration", "date", "birth",
    })

    def _extract_name(self, text: str) -> Optional[str]:
        """Return the candidate name from the first lines of a CV, or None."""
        for line in text.split("\n")[:30]:
            line = line.strip()
            if not line or len(line) > 60:
                continue
            if any(ch in line for ch in "@:0123456789+/\\"):
                continue
            words = line.split()
            if not (2 <= len(words) <= 4):
                continue
            # Require most words to start with uppercase
            if sum(1 for w in words if w and w[0].isupper()) < len(words) - 1:
                continue
            lower_words = {w.lower().rstrip(".,;") for w in words}
            if lower_words & self._NAME_SECTION_KEYWORDS:
                continue
            # Only alphabetic characters (hyphens and apostrophes allowed inside)
            clean = re.sub(r"['\-]", "", line.replace(" ", ""))
            if not clean.isalpha():
                continue
            return line
        return None

    _ROLE_TITLE_KEYWORDS = frozenset({
        "officer", "manager", "engineer", "specialist", "coordinator", "analyst",
        "director", "lead", "head", "consultant", "advisor", "executive",
        "supervisor", "technician", "administrator", "auditor", "associate",
        "inspector", "controller", "planner", "strategist",
    })

    def _extract_current_role(self, text: str) -> Optional[str]:
        """Return the most recent job title from a CV, or None."""
        # Pattern 1: explicit "Current Role: X" or "Present Position: X" markers
        explicit = re.search(
            r"(?:current(?:ly)?|present)\s*(?:role|position|title|job)[\s:]+([A-Za-z][A-Za-z\s&/,.\-]{3,60})",
            text, re.IGNORECASE,
        )
        if explicit:
            return explicit.group(1).strip().title()

        # Pattern 2: scan backwards from a line containing "Present" for a role title.
        # Require the candidate to contain a recognized role keyword to avoid returning
        # company names (e.g. "Green Holdings UAE") instead of titles.
        lines = text.split("\n")
        present_re = re.compile(r"\bpresent\b", re.IGNORECASE)
        for i, line in enumerate(lines):
            if not present_re.search(line):
                continue
            for back in range(1, 5):
                idx = i - back
                if idx < 0:
                    break
                candidate = lines[idx].strip()
                if not candidate or not candidate[0].isalpha():
                    continue
                words = candidate.split()
                if not (1 <= len(words) <= 6):
                    continue
                clean = re.sub(r"['\-&/,.]", "", candidate.replace(" ", ""))
                if not (clean.isalpha() and candidate[0].isupper()):
                    continue
                # Must contain a recognized role keyword — skips company/location lines
                if any(kw in candidate.lower() for kw in self._ROLE_TITLE_KEYWORDS):
                    return candidate
        return None

    def _extract_years(self, text: str) -> Optional[float]:
        matches = re.findall(r"(\d+(?:\.\d+)?)\+?\s*(?:years|yrs|year)", text)
        if not matches:
            return None
        return max(float(x) for x in matches)

    def _parse_pdf(self, data: bytes) -> str:
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=data, filetype="pdf")
            return "\n".join(page.get_text() for page in doc)
        except Exception as exc:
            logger.warning("cv_parser: PyMuPDF failed, falling back to raw UTF-8 decode: %s", exc)
            return data.decode("utf-8", errors="ignore")

    def _parse_docx(self, data: bytes) -> str:
        try:
            from docx import Document
            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as exc:
            logger.warning("cv_parser: python-docx failed, falling back to raw UTF-8 decode: %s", exc)
            return data.decode("utf-8", errors="ignore")
