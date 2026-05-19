"""CV parser service for Rico AI.

Additive module: does not change the existing job automation pipeline.
Supports PDF, DOCX, TXT, and plain bytes. Cloud deployment should install
optional dependencies: pymupdf and python-docx.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


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

    def detect_document_type(self, text: str) -> str:
        """Detect if document is a CV, company profile, or unknown type."""
        lower = text.lower()

        # Personal markers are a strong veto against company_profile.
        has_personal_marker = any(m in lower for m in self.PERSONAL_MARKERS)

        company_score = sum(1 for s in self.COMPANY_SIGNALS if s in lower)
        cv_score = sum(1 for s in self.CV_SIGNALS if s in lower)

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

        if cv_score >= 2 or has_personal_marker:
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
        return self.parse_text(text)

    def parse_bytes(self, data: bytes, filename: str = "cv.txt") -> ParsedCV:
        suffix = Path(filename).suffix.lower()
        if suffix == ".pdf":
            text = self._parse_pdf(data)
        elif suffix in {".docx", ".doc"}:
            text = self._parse_docx(data)
        else:
            text = data.decode("utf-8", errors="ignore")
        return self.parse_text(text)

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
        )

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
        except Exception:
            return data.decode("utf-8", errors="ignore")

    def _parse_docx(self, data: bytes) -> str:
        try:
            from docx import Document
            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            return data.decode("utf-8", errors="ignore")
