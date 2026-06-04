"""Unit tests for UAE/GCC role normalizer variants."""
import pytest
from src.agent.intelligence.normalizer import normalize_role


@pytest.mark.parametrize("raw,expected", [
    # HSE / Safety / Compliance
    ("hse manager",         "HSE Manager"),
    ("hse officer",         "HSE Officer"),
    ("hse engineer",        "HSE Engineer"),
    ("hse advisor",         "HSE Advisor"),
    ("hse coordinator",     "HSE Coordinator"),
    ("qhse manager",        "QHSE Manager"),
    ("qhse officer",        "QHSE Officer"),
    ("ehs manager",         "EHS Manager"),
    ("ehs officer",         "EHS Officer"),
    ("ehs engineer",        "EHS Engineer"),
    ("safety manager",      "Safety Manager"),
    ("safety officer",      "Safety Officer"),
    ("safety engineer",     "Safety Engineer"),
    ("environmental manager", "Environmental Manager"),
    ("environmental officer", "Environmental Officer"),
    ("compliance manager",  "Compliance Manager"),
    ("compliance officer",  "Compliance Officer"),
    # Typo variants
    ("saftey manager",      "Safety Manager"),
    ("saftey officer",      "Safety Officer"),
    ("enviromental manager", "Environmental Manager"),
    ("complince manager",   "Compliance Manager"),
    ("oprations manager",   "Operations Manager"),
    # Construction / Built environment
    ("mep engineer",        "MEP Engineer"),
    ("quantity surveyor",   "Quantity Surveyor"),
    ("qs",                  "Quantity Surveyor"),
    ("civil engineer",      "Civil Engineer"),
    ("site engineer",       "Site Engineer"),
    ("site manager",        "Site Manager"),
    ("document controller", "Document Controller"),
    # UAE market
    ("country manager",     "Country Manager"),
    ("general manager",     "General Manager"),
    ("gm",                  "General Manager"),
    ("procurement manager", "Procurement Manager"),
    ("supply chain manager","Supply Chain Manager"),
    ("warehouse manager",   "Warehouse Manager"),
    ("real estate agent",   "Real Estate Agent"),
    ("property consultant", "Property Consultant"),
    ("vat specialist",      "VAT Specialist"),
    ("internal auditor",    "Internal Auditor"),
    ("esg manager",         "ESG Manager"),
    ("sustainability manager", "Sustainability Manager"),
    # People / Admin
    ("executive assistant", "Executive Assistant"),
    ("pa",                  "Personal Assistant"),
    ("office manager",      "Office Manager"),
    ("admin manager",       "Administration Manager"),
    # Finance
    ("treasury manager",    "Treasury Manager"),
    ("audit manager",       "Audit Manager"),
    ("tax manager",         "Tax Manager"),
])
def test_normalize_uae_role_variants(raw, expected):
    assert normalize_role(raw) == expected, f"normalize_role({raw!r}) expected {expected!r}"


def test_senior_prefix_stripped():
    """Senior prefix should be stripped before variant lookup."""
    assert normalize_role("senior hse manager") == "HSE Manager"


def test_unknown_role_title_cased():
    """Unknown role should be title-cased, not returned as-is."""
    result = normalize_role("some unknown specialist")
    assert result[0].isupper(), "First char should be uppercase"
