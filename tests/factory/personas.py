# -*- coding: utf-8 -*-
"""Deterministic synthetic persona and CV-fixture factory.

Produces the persona/CV matrix described in the Rico multi-user reliability
test program (PR1). Every value here is synthetic:

  * no real names, phone numbers, emails, Emirates IDs, passports, or
    addresses;
  * "nationality style" labels (e.g. ``jordanian_style``) select only a
    name-formatting / language / transliteration convention for testing
    Unicode, RTL, and localization handling — they carry no ranking or
    suitability meaning and MUST NOT be used as scoring or decision inputs
    anywhere outside these tests;
  * every persona/user id is namespaced under a caller-supplied ``run_id``
    so two test runs (or two concurrent workers) never collide on the same
    synthetic identity.

Nothing in this module performs I/O, network access, or database writes.
It only builds in-memory ``Persona`` / ``CvFixture`` records and synthetic
CV text content for use by harnesses such as ``tests.harness.chat_harness``
or future API/Playwright/load-test suites.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional


# --- Language variants -----------------------------------------------------

LANGUAGES: tuple[str, ...] = (
    "arabic",
    "english",
    "arabic_english_bilingual",
    "mixed_arabic_english",
    "arabic_with_diacritics",
    "gulf_colloquial_arabic",
    "typo_and_keyboard_layout",
)

# --- Document/naming-convention styles (localization test labels only) -----
#
# These select formatting conventions for synthetic names/dates/phones. They
# are NOT nationality, race, religion, or gender signals and must never be
# read as job-suitability input.

DOCUMENT_STYLES: tuple[str, ...] = (
    "uae_arabic_speaker",
    "uae_english_speaker",
    "jordanian_style",
    "emirati_style",
    "indian_english",
    "pakistani_english",
    "filipino_english",
    "egyptian_style",
    "syrian_style",
    "british_english",
    "french_influenced_english",
)

# --- Career personas ---------------------------------------------------------

CAREER_PERSONAS: tuple[str, ...] = (
    "hse_manager",
    "accountant",
    "software_engineer",
    "nurse",
    "sales_executive",
    "driver",
    "restaurant_manager",
    "fresh_graduate",
    "senior_executive",
    "career_changer",
    "employment_gap",
    "multiple_concurrent_roles",
)

# --- CV variant kinds (structural / lifecycle variants, not content) --------

CV_VARIANT_KINDS: tuple[str, ...] = (
    "single",
    "three_cvs",
    "ten_cvs",
    "duplicate_upload_same_file",
    "same_content_diff_filename",
    "diff_content_same_filename",
    "arabic_pdf",
    "english_pdf",
    "bilingual_pdf",
    "docx",
    "scanned_image_pdf",
    "image_only",
    "rotated_pages",
    "multi_column",
    "ats_friendly",
    "tables",
    "very_long",
    "almost_empty",
    "corrupted_pdf",
    "password_protected_pdf",
    "oversized_file",
    "docx_bomb_like_safe",
    "unsupported_extension",
    "unicode_filename_stress",
)

_SYNTHETIC_EMAIL_DOMAIN = "rico-synthetic-test.invalid"


def _stable_hash(*parts: str) -> str:
    """Short deterministic hex digest for namespacing synthetic ids."""
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class Persona:
    """One synthetic test user identity. No PII of any kind."""

    run_id: str
    index: int
    language: str
    document_style: str
    career: str

    @property
    def user_id(self) -> str:
        return f"synthetic-{self.run_id}-{self.index:04d}@{_SYNTHETIC_EMAIL_DOMAIN}"

    @property
    def display_name(self) -> str:
        """A synthetic, style-flavored display name — never a real identity."""
        return f"Test Persona {self.index:04d} ({self.document_style})"

    @property
    def fingerprint(self) -> str:
        """Deterministic id for correlating this persona across a run's fixtures."""
        return _stable_hash(self.run_id, str(self.index), self.language, self.document_style, self.career)


@dataclass(frozen=True)
class CvFixture:
    """A synthetic CV fixture: content + declared structural variant."""

    persona: Persona
    variant: str
    filename: str
    content: str
    extension: str = "txt"
    #: Set True for fixtures that MUST be rejected/handled as failure paths
    #: (corrupted, password-protected, oversized, unsupported extension, ...).
    expect_failure_path: bool = False

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8", errors="ignore")).hexdigest()


def build_personas(run_id: str, count: Optional[int] = None) -> list[Persona]:
    """Build the deterministic full persona matrix (or the first ``count``).

    Same ``run_id`` always yields the same ordered persona list. Different
    ``run_id`` values never share a ``user_id``, so concurrent test runs
    cannot collide on synthetic identity.
    """
    personas: list[Persona] = []
    index = 0
    for career in CAREER_PERSONAS:
        for style in DOCUMENT_STYLES:
            language = LANGUAGES[index % len(LANGUAGES)]
            personas.append(Persona(run_id=run_id, index=index, language=language, document_style=style, career=career))
            index += 1
            if count is not None and len(personas) >= count:
                return personas
    return personas


_CAREER_SUMMARY = {
    "hse_manager": "HSE Manager with 8 years experience leading safety programs across UAE construction sites.",
    "accountant": "Accountant with 5 years experience in reconciliation, VAT filing, and financial reporting.",
    "software_engineer": "Software Engineer with 4 years experience building backend services and APIs.",
    "nurse": "Registered Nurse with 6 years experience in acute care and patient management.",
    "sales_executive": "Sales Executive with 3 years experience in B2B enterprise sales across the GCC.",
    "driver": "Professional Driver with a valid UAE license and 10 years of commercial driving experience.",
    "restaurant_manager": "Restaurant Manager with 7 years experience in F&B operations and staff scheduling.",
    "fresh_graduate": "Fresh Graduate in Business Administration seeking an entry-level role.",
    "senior_executive": "Senior Executive with 15 years experience in strategy and P&L ownership.",
    "career_changer": "Career changer transitioning from teaching to project coordination.",
    "employment_gap": "Professional with a two-year employment gap for caregiving, returning to the workforce.",
    "multiple_concurrent_roles": "Professional holding two concurrent part-time roles in logistics and retail.",
}

_ARABIC_HEADER = "السيرة الذاتية"


def _synthetic_body(persona: Persona) -> str:
    summary = _CAREER_SUMMARY[persona.career]
    if persona.language in ("arabic", "gulf_colloquial_arabic", "arabic_with_diacritics"):
        return f"{_ARABIC_HEADER}\n{persona.display_name}\n{summary}\nمعرف الاختبار: {persona.fingerprint}\n"
    if persona.language in ("arabic_english_bilingual", "mixed_arabic_english"):
        return f"{_ARABIC_HEADER} / CV\n{persona.display_name}\n{summary}\nTest fingerprint: {persona.fingerprint}\n"
    return f"CV\n{persona.display_name}\n{summary}\nTest fingerprint: {persona.fingerprint}\n"


def build_cv_fixture(persona: Persona, variant: str) -> CvFixture:
    """Build one synthetic CV fixture for ``persona`` at the given ``variant``.

    ``variant`` must be one of ``CV_VARIANT_KINDS``. This never reads or
    writes a real file; content is generated in-memory and is safe to persist
    to a disposable, staging-only scratch path if a test needs bytes on disk.
    """
    if variant not in CV_VARIANT_KINDS:
        raise ValueError(f"Unknown CV variant kind: {variant!r}")

    base = _synthetic_body(persona)
    filename = f"cv-{persona.fingerprint}.txt"
    extension = "txt"
    content = base
    expect_failure_path = False

    if variant == "very_long":
        content = base + ("Relevant experience detail line.\n" * 500)
    elif variant == "almost_empty":
        content = persona.display_name
    elif variant == "duplicate_upload_same_file":
        content = base  # identical bytes intended; caller uploads twice
    elif variant == "same_content_diff_filename":
        filename = f"cv-{persona.fingerprint}-alt.txt"
    elif variant == "diff_content_same_filename":
        content = base + "\nAlternate revision content.\n"
    elif variant in ("arabic_pdf", "english_pdf", "bilingual_pdf", "scanned_image_pdf"):
        extension = "pdf"
        filename = f"cv-{persona.fingerprint}.pdf"
        # Not a real PDF — deliberately not %PDF-prefixed placeholder text so
        # parser-failure paths (no_text / unsupported) can be exercised safely.
        content = base
    elif variant == "docx":
        extension = "docx"
        filename = f"cv-{persona.fingerprint}.docx"
    elif variant == "image_only":
        extension = "png"
        filename = f"cv-{persona.fingerprint}.png"
        content = ""
        expect_failure_path = True
    elif variant == "corrupted_pdf":
        extension = "pdf"
        filename = f"cv-{persona.fingerprint}-corrupt.pdf"
        content = "%PDF-1.4\n%%CORRUPTED-SYNTHETIC-FIXTURE\n"
        expect_failure_path = True
    elif variant == "password_protected_pdf":
        extension = "pdf"
        filename = f"cv-{persona.fingerprint}-locked.pdf"
        content = "%PDF-1.4\n%%SYNTHETIC-PASSWORD-PROTECTED-PLACEHOLDER\n"
        expect_failure_path = True
    elif variant == "oversized_file":
        content = base + ("X" * (1024 * 1024))  # 1MB synthetic filler, safe/local
        expect_failure_path = True
    elif variant == "docx_bomb_like_safe":
        extension = "docx"
        filename = f"cv-{persona.fingerprint}-bomb.docx"
        # Bounded repetition only — a real zip-bomb is out of scope for a
        # laboratory-safe fixture; this exists to exercise size/ratio guards.
        content = base * 200
        expect_failure_path = True
    elif variant == "unsupported_extension":
        extension = "xyz"
        filename = f"cv-{persona.fingerprint}.xyz"
        expect_failure_path = True
    elif variant == "unicode_filename_stress":
        filename = f"سيرة ذاتية 😀 {persona.fingerprint}..final.v2.txt"
    elif variant in ("multi_column", "ats_friendly", "tables", "rotated_pages"):
        content = base + f"\n[layout-variant:{variant}]\n"

    return CvFixture(
        persona=persona,
        variant=variant,
        filename=filename,
        content=content,
        extension=extension,
        expect_failure_path=expect_failure_path,
    )


def build_cv_matrix(personas: list[Persona], variants: Optional[tuple[str, ...]] = None) -> list[CvFixture]:
    """Cartesian-ish helper: one fixture per (persona, variant) pair."""
    chosen = variants or CV_VARIANT_KINDS
    return [build_cv_fixture(p, v) for p in personas for v in chosen]
