"""
CV Parse Quality Contract (#1118)

Shared contract for CV parse quality validation across upload and confirmation.
Provides conservative signals based on parser outcome, not just character count.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class ParseOutcome(str, Enum):
    """Parser outcome states."""
    PARSED = "parsed"  # Parser completed successfully with meaningful content
    NO_TEXT = "no_text"  # No extractable text (scanned, image-only)
    UNREADABLE = "unreadable"  # Text extracted but below meaningful threshold
    PARSE_FAILED = "parse_failed"  # Parser exception or format error


@dataclass
class ParseQualityResult:
    """Result of parse quality validation."""
    outcome: ParseOutcome
    is_readable: bool
    extracted_chars: int
    printable_ratio: float  # Ratio of printable ASCII to total bytes
    message: str | None = None


def validate_parse_quality(
    *,
    text: str,
    extracted_chars: int,
    extraction_quality: str | None = None,
    parser_exception: Exception | None = None,
) -> ParseQualityResult:
    """
    Validate CV parse quality using conservative signals.

    Args:
        text: Extracted text from parser
        extracted_chars: Number of characters extracted
        extraction_quality: Quality rating from parser (poor/partial/good)
        parser_exception: Exception if parser failed

    Returns:
        ParseQualityResult with outcome and validation details
    """
    # Parser exception → parse_failed
    if parser_exception is not None:
        return ParseQualityResult(
            outcome=ParseOutcome.PARSE_FAILED,
            is_readable=False,
            extracted_chars=0,
            printable_ratio=0.0,
            message="CV parsing failed",
        )

    # No text → no_text
    if not text or extracted_chars == 0:
        return ParseQualityResult(
            outcome=ParseOutcome.NO_TEXT,
            is_readable=False,
            extracted_chars=0,
            printable_ratio=0.0,
            message="No extractable text",
        )

    # Calculate printable ratio (conservative signal for garbage detection)
    printable = sum(1 for c in text if c.isprintable() and not c.isspace())
    printable_ratio = printable / len(text) if text else 0.0

    # Conservative threshold: require both minimum chars AND reasonable printable ratio
    # This prevents binary garbage from passing even if it has enough "characters"
    # Parser quality labels inform the decision but do not override these thresholds
    _MIN_READABLE_CHARS = 50
    _MIN_PRINTABLE_RATIO = 0.3  # At least 30% printable characters

    if extracted_chars < _MIN_READABLE_CHARS or printable_ratio < _MIN_PRINTABLE_RATIO:
        return ParseQualityResult(
            outcome=ParseOutcome.UNREADABLE,
            is_readable=False,
            extracted_chars=extracted_chars,
            printable_ratio=printable_ratio,
            message="Not enough readable text",
        )

    # Passed all checks → parsed
    return ParseQualityResult(
        outcome=ParseOutcome.PARSED,
        is_readable=True,
        extracted_chars=extracted_chars,
        printable_ratio=printable_ratio,
        message=None,
    )


def validate_artifact_quality(cv_text: str | None) -> ParseQualityResult:
    """
    Validate artifact cv_text for confirmation defense-in-depth.

    This is a safety net in case the upload gate is bypassed or a bug
    allows garbage through. Must not rely on client-supplied data.

    Args:
        cv_text: Text from the artifact

    Returns:
        ParseQualityResult with outcome
    """
    if cv_text is None:
        return ParseQualityResult(
            outcome=ParseOutcome.PARSE_FAILED,
            is_readable=False,
            extracted_chars=0,
            printable_ratio=0.0,
            message="Artifact has no cv_text",
        )

    return validate_parse_quality(
        text=cv_text,
        extracted_chars=len(cv_text.strip()),
        extraction_quality=None,
        parser_exception=None,
    )
