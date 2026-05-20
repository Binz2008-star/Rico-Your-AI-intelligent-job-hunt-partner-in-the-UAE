"""role_suggester.py — Structured CV-evidence → role suggestions for all job-seeker segments.

Public contract
---------------

generate_role_suggestions(skills, certifications, years_experience, industries,
                          current_role=None, max_results=7) -> dict

Returns a structured result:

    {
        "roles": [
            {
                "title": str,
                "confidence": float,        # 0.0–1.0
                "reason": str,              # explainable, tied to CV evidence
                "segment": str,             # family name (e.g. "environmental_esg")
                "search_query": str,        # English UAE-searchable query
            },
            ...
        ],
        "clarifying_questions": list[str],  # populated only for weak profiles
        "source": "cv_profile" | "weak_profile" | "fallback",
        "actions": list[dict],              # optional product actions
    }

Segments covered: fresh graduates, junior professionals, mid-level, senior/
managers, blue-collar/field, technicians, drivers/logistics, sales/customer
service, admin/office, healthcare, finance/accounting, HR, IT/software/data,
HSE/QHSE, environmental/ESG/sustainability, hospitality/retail,
career changers, weak/partial CV profiles, Arabic/mixed-language users.

No external API calls. Pure profile-signals → role mapping.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Seniority tiers
# ---------------------------------------------------------------------------

_TIER_ENTRY = "entry"
_TIER_JUNIOR = "junior"
_TIER_MID = "mid"
_TIER_SENIOR = "senior"
_TIER_PRINCIPAL = "principal"


def _seniority_tier(
    years: float | None,
    current_role: str | None = None,
) -> str:
    """Return the seniority tier based on experience and optional current role title."""
    if current_role:
        cr = current_role.lower()
        if any(k in cr for k in ("director", "head of", "vp ", "vice president", "chief")):
            return _TIER_PRINCIPAL
        if any(k in cr for k in ("senior manager", "senior director")):
            return _TIER_PRINCIPAL
        if any(k in cr for k in ("manager", "lead ", " lead", "senior ")):
            return _TIER_SENIOR
    if years is None:
        return _TIER_ENTRY
    if years < 2:
        return _TIER_ENTRY
    if years < 5:
        return _TIER_JUNIOR
    if years < 9:
        return _TIER_MID
    if years < 13:
        return _TIER_SENIOR
    return _TIER_PRINCIPAL


# ---------------------------------------------------------------------------
# Role family definitions
# ---------------------------------------------------------------------------
#
# Each family has:
#   signals   — set of lowercase skill/cert keywords that activate this family
#   entry/junior/mid/senior/principal — ordered role title lists (best fit first)
#
# Notes:
#   • env_esg is intentionally separate from hse_qhse so each family can be
#     capped independently and cross-family bridging is explicit.
#   • Environmental Compliance Officer lives in env_esg MID tier (it is the
#     officer-level expression of the env_esg family).
#   • Senior tiers include "Senior X Specialist" variants where the UAE market
#     uses them (not every senior is a Manager).
# ---------------------------------------------------------------------------

_ROLE_FAMILIES: list[dict] = [
    {
        "name": "environmental_esg",
        "label": "Environmental/ESG",
        "signals": {
            "environmental management", "esg", "sustainability", "iso 14001",
            "carbon footprint", "environmental", "green building", "leed",
            "environmental compliance", "climate", "net zero",
        },
        _TIER_ENTRY:     ["Environmental Trainee", "Sustainability Assistant", "ESG Graduate"],
        _TIER_JUNIOR:    ["Environmental Officer", "ESG Analyst", "Sustainability Coordinator"],
        _TIER_MID: [
            "Environmental Compliance Officer", "ESG Specialist", "Sustainability Officer",
            "Environmental Specialist",
        ],
        _TIER_SENIOR: [
            "Environmental Manager", "ESG Manager", "Environmental Compliance Manager",
            "Sustainability Manager",
        ],
        _TIER_PRINCIPAL: ["Head of Sustainability", "Director of ESG", "VP Environmental Affairs"],
    },
    {
        "name": "hse_qhse",
        "label": "HSE/QHSE",
        "signals": {
            "hse", "safety", "ehs", "qhse", "fire safety", "risk assessment",
            "permit to work", "incident investigation", "nebosh", "iosh", "osha",
            "safety officer", "safety management", "iso 45001",
        },
        _TIER_ENTRY:     ["HSE Graduate", "Safety Trainee", "EHS Assistant"],
        _TIER_JUNIOR:    ["HSE Officer", "Safety Officer", "EHS Officer", "QHSE Coordinator"],
        _TIER_MID:       ["HSE Specialist", "Senior HSE Specialist", "QHSE Officer", "Safety Supervisor"],
        _TIER_SENIOR:    ["HSE Manager", "QHSE Manager", "Safety Manager", "Senior HSE Specialist", "HSE Lead"],
        _TIER_PRINCIPAL: ["Head of HSE", "Director of HSE", "VP Safety & Sustainability"],
    },
    {
        "name": "compliance_audit",
        "label": "compliance & audit",
        "signals": {
            "compliance", "audit", "internal audit", "regulatory", "governance",
            "risk management", "sox", "anti-money laundering", "aml", "kyc",
            "regulatory affairs", "policy",
        },
        _TIER_ENTRY:     ["Compliance Trainee", "Audit Assistant", "Regulatory Assistant"],
        _TIER_JUNIOR:    ["Compliance Officer", "Internal Auditor", "Regulatory Officer"],
        _TIER_MID:       ["Compliance Specialist", "Senior Auditor", "Risk & Compliance Officer"],
        _TIER_SENIOR:    ["Compliance Manager", "Audit Manager", "Head of Internal Audit"],
        _TIER_PRINCIPAL: ["Chief Compliance Officer", "Director of Risk & Compliance"],
    },
    {
        "name": "iso_quality",
        "label": "ISO/quality",
        "signals": {
            "iso 9001", "iso 45001", "iso 14001", "quality", "qc", "quality control",
            "quality assurance", "six sigma", "lean", "kaizen", "quality management",
            "iso", "qa",
        },
        _TIER_ENTRY:     ["Quality Inspector", "QC Assistant", "Quality Trainee"],
        _TIER_JUNIOR:    ["Quality Officer", "ISO Coordinator", "QA/QC Inspector"],
        _TIER_MID:       ["ISO 14001 Specialist", "Quality Specialist", "QA/QC Supervisor"],
        _TIER_SENIOR:    ["ISO 14001 Lead Auditor", "Quality Manager", "QA Manager"],
        _TIER_PRINCIPAL: ["Head of Quality", "Director of Quality Assurance"],
    },
    {
        "name": "it_software",
        "label": "software development",
        "signals": {
            "python", "javascript", "java", "software", "programming", "web development",
            "react", "node", "django", "flutter", "mobile", "backend", "frontend",
            "devops", "cloud", "aws", "azure", "docker", "kubernetes", "php", "c++", "c#",
        },
        _TIER_ENTRY:     ["Junior Developer", "Graduate Software Engineer", "IT Trainee"],
        _TIER_JUNIOR:    ["Software Developer", "Web Developer", "Junior Software Engineer"],
        _TIER_MID:       ["Software Engineer", "Full Stack Developer", "Systems Engineer"],
        _TIER_SENIOR:    ["Senior Software Engineer", "Tech Lead", "Solutions Architect"],
        _TIER_PRINCIPAL: ["Head of Engineering", "VP Engineering", "CTO"],
    },
    {
        "name": "it_support_networks",
        "label": "IT/networking",
        "signals": {
            "it support", "network", "system administration", "helpdesk", "windows server",
            "cisco", "ccna", "hardware", "troubleshooting", "active directory", "linux",
            "cybersecurity", "firewall", "networking",
        },
        _TIER_ENTRY:     ["IT Support Trainee", "Help Desk Trainee", "IT Assistant"],
        _TIER_JUNIOR:    ["IT Support Engineer", "Help Desk Technician", "Network Technician"],
        _TIER_MID:       ["IT Support Specialist", "Network Engineer", "Systems Administrator"],
        _TIER_SENIOR:    ["IT Manager", "Network Manager", "Senior IT Engineer"],
        _TIER_PRINCIPAL: ["Head of IT", "IT Director", "Chief Information Officer"],
    },
    {
        "name": "data_analytics",
        "label": "data & analytics",
        "signals": {
            "sql", "power bi", "tableau", "data analysis", "analytics",
            "statistics", "machine learning", "data science", "business intelligence",
            "r programming", "pandas", "big data", "etl",
        },
        _TIER_ENTRY:     ["Data Entry Officer", "Junior Analyst", "Reporting Assistant"],
        _TIER_JUNIOR:    ["Data Analyst", "Business Analyst", "Reporting Analyst"],
        _TIER_MID:       ["Senior Data Analyst", "BI Analyst", "Data Specialist"],
        _TIER_SENIOR:    ["Data Manager", "Analytics Manager", "BI Manager"],
        _TIER_PRINCIPAL: ["Chief Data Officer", "Director of Analytics", "Head of Data"],
    },
    {
        "name": "finance_accounting",
        "label": "finance & accounting",
        "signals": {
            "accounting", "finance", "accounts", "financial analysis", "budget",
            "ifrs", "cfa", "cpa", "acca", "bookkeeping", "accounts payable",
            "accounts receivable", "tax", "treasury", "financial reporting", "vat",
        },
        _TIER_ENTRY:     ["Accounts Assistant", "Junior Accountant", "Finance Trainee"],
        _TIER_JUNIOR:    ["Accountant", "Financial Analyst", "Accounts Officer"],
        _TIER_MID:       ["Senior Accountant", "Finance Specialist", "Credit Analyst"],
        _TIER_SENIOR:    ["Finance Manager", "Accounting Manager", "Financial Controller"],
        _TIER_PRINCIPAL: ["Finance Director", "CFO", "Head of Finance"],
    },
    {
        "name": "hr_recruitment",
        "label": "HR & recruitment",
        "signals": {
            "hr", "human resources", "recruitment", "talent acquisition", "payroll",
            "hrms", "performance management", "employee relations", "onboarding",
            "learning and development", "training", "compensation", "benefits",
        },
        _TIER_ENTRY:     ["HR Assistant", "Recruitment Coordinator", "HR Trainee"],
        _TIER_JUNIOR:    ["HR Officer", "Recruiter", "Talent Acquisition Specialist"],
        _TIER_MID:       ["HR Specialist", "Senior Recruiter", "HR Business Partner"],
        _TIER_SENIOR:    ["HR Manager", "Talent Acquisition Manager", "People & Culture Manager"],
        _TIER_PRINCIPAL: ["HR Director", "Chief People Officer", "Head of Human Resources"],
    },
    {
        "name": "admin_office",
        "label": "administration",
        "signals": {
            "administration", "admin", "secretary", "office management", "document control",
            "reception", "filing", "scheduling", "executive assistant",
            "personal assistant", "office coordination", "correspondence",
            "microsoft office", "excel",
        },
        _TIER_ENTRY:     ["Office Assistant", "Receptionist", "Admin Trainee"],
        _TIER_JUNIOR:    ["Admin Officer", "Document Controller", "Executive Secretary"],
        _TIER_MID:       ["Senior Admin Officer", "Personal Assistant", "Office Supervisor"],
        _TIER_SENIOR:    ["Office Manager", "Admin Manager", "Executive Assistant to C-Suite"],
        _TIER_PRINCIPAL: ["Head of Administration", "Chief of Staff"],
    },
    {
        "name": "sales_customer_service",
        "label": "sales & customer service",
        "signals": {
            "sales", "retail", "customer service", "crm", "business development",
            "account management", "telesales", "upselling", "negotiation", "b2b", "b2c",
            "client relations", "customer support", "call center",
        },
        _TIER_ENTRY:     ["Sales Assistant", "Customer Service Representative", "Retail Associate"],
        _TIER_JUNIOR:    ["Sales Executive", "Business Development Executive", "Account Executive"],
        _TIER_MID:       ["Senior Sales Executive", "Key Account Manager", "Customer Success Manager"],
        _TIER_SENIOR:    ["Sales Manager", "Business Development Manager", "Head of Customer Success"],
        _TIER_PRINCIPAL: ["Sales Director", "VP Sales", "Chief Revenue Officer"],
    },
    {
        "name": "marketing",
        "label": "marketing",
        "signals": {
            "marketing", "digital marketing", "seo", "social media", "content",
            "brand", "advertising", "campaign", "market research", "copywriting",
            "email marketing", "google ads", "meta ads", "influencer", "pr",
        },
        _TIER_ENTRY:     ["Marketing Assistant", "Social Media Assistant", "Content Writer"],
        _TIER_JUNIOR:    ["Marketing Coordinator", "Digital Marketing Executive", "Content Creator"],
        _TIER_MID:       ["Marketing Specialist", "Brand Executive", "SEO Specialist"],
        _TIER_SENIOR:    ["Marketing Manager", "Brand Manager", "Digital Marketing Manager"],
        _TIER_PRINCIPAL: ["Marketing Director", "Chief Marketing Officer", "Head of Marketing"],
    },
    {
        "name": "hospitality_food",
        "label": "hospitality",
        "signals": {
            "hospitality", "hotel", "food and beverage", "front desk", "housekeeping",
            "catering", "restaurant", "chef", "waiter", "waitress", "barista",
            "bartender", "guest services", "banquet",
        },
        _TIER_ENTRY:     ["Hotel Trainee", "F&B Assistant", "Front Desk Associate"],
        _TIER_JUNIOR:    ["Front Desk Officer", "Guest Service Agent", "Waiter/Waitress"],
        _TIER_MID:       ["Guest Relations Officer", "Restaurant Supervisor", "Floor Manager"],
        _TIER_SENIOR:    ["Hotel Manager", "F&B Manager", "Front Office Manager"],
        _TIER_PRINCIPAL: ["General Manager", "Director of Operations (Hospitality)", "Hotel Director"],
    },
    {
        "name": "healthcare",
        "label": "healthcare",
        "signals": {
            "nursing", "medical", "clinical", "pharmacy", "patient care", "healthcare",
            "physiotherapy", "dentistry", "laboratory", "radiology", "public health",
            "paramedic", "midwifery", "ophthalmology",
        },
        _TIER_ENTRY:     ["Healthcare Assistant", "Clinical Trainee", "Lab Assistant"],
        _TIER_JUNIOR:    ["Nurse", "Pharmacist", "Medical Technician", "Lab Technician"],
        _TIER_MID:       ["Senior Nurse", "Clinical Specialist", "Healthcare Coordinator"],
        _TIER_SENIOR:    ["Nurse Manager", "Healthcare Manager", "Clinical Manager"],
        _TIER_PRINCIPAL: ["Medical Director", "Head of Nursing", "Chief Medical Officer"],
    },
    {
        "name": "engineering",
        "label": "engineering",
        "signals": {
            "engineering", "mechanical", "electrical", "civil", "construction",
            "maintenance", "autocad", "structural", "chemical", "industrial",
            "project management", "quantity surveying", "mep",
        },
        _TIER_ENTRY:     ["Graduate Engineer", "Engineering Trainee", "Site Assistant"],
        _TIER_JUNIOR:    ["Engineer", "Site Engineer", "Junior Project Engineer"],
        _TIER_MID:       ["Project Engineer", "Senior Engineer", "Technical Specialist"],
        _TIER_SENIOR:    ["Senior Project Manager", "Engineering Manager", "Project Manager"],
        _TIER_PRINCIPAL: ["Director of Engineering", "Head of Projects", "VP Engineering"],
    },
    {
        "name": "logistics_supply_chain",
        "label": "logistics & supply chain",
        "signals": {
            "logistics", "supply chain", "warehouse", "procurement", "inventory",
            "shipping", "import", "export", "freight", "customs", "purchasing",
            "store keeper", "material control", "demand planning",
        },
        _TIER_ENTRY:     ["Store Keeper", "Warehouse Assistant", "Logistics Trainee"],
        _TIER_JUNIOR:    ["Logistics Coordinator", "Procurement Officer", "Inventory Controller"],
        _TIER_MID:       ["Supply Chain Specialist", "Procurement Specialist", "Logistics Supervisor"],
        _TIER_SENIOR:    ["Logistics Manager", "Supply Chain Manager", "Procurement Manager"],
        _TIER_PRINCIPAL: ["Head of Supply Chain", "Director of Procurement", "VP Logistics"],
    },
    {
        "name": "driving_transport",
        "label": "transport",
        "signals": {
            "driving", "driver", "heavy vehicle", "forklift", "transport", "delivery",
            "light vehicle", "truck", "bus driver", "taxi", "heavy equipment",
            "operate vehicle", "chauffeur",
        },
        _TIER_ENTRY:     ["Delivery Driver", "Light Vehicle Driver", "Driver"],
        _TIER_JUNIOR:    ["Heavy Vehicle Driver", "Forklift Operator", "Driver"],
        _TIER_MID:       ["Senior Driver", "Transport Coordinator", "Fleet Driver"],
        _TIER_SENIOR:    ["Transport Supervisor", "Fleet Coordinator", "Logistics Supervisor"],
        _TIER_PRINCIPAL: ["Transport Manager", "Fleet Manager"],
    },
    {
        "name": "blue_collar_field",
        "label": "field/technical",
        "signals": {
            "labor", "construction", "carpentry", "plumbing", "painting", "cleaning",
            "ac technician", "hvac", "electrician", "welder", "pipe fitter",
            "mason", "scaffolding", "tiling", "mep", "general maintenance",
        },
        _TIER_ENTRY:     ["General Worker", "Construction Helper", "Maintenance Helper"],
        _TIER_JUNIOR:    ["Skilled Worker", "Tradesperson", "Technician"],
        _TIER_MID:       ["Senior Technician", "Trade Specialist", "Maintenance Technician"],
        _TIER_SENIOR:    ["Site Supervisor", "Technical Supervisor", "Maintenance Foreman"],
        _TIER_PRINCIPAL: ["Site Manager", "Construction Manager", "Maintenance Manager"],
    },
    {
        "name": "operations",
        "label": "operations",
        "signals": {
            "operations", "facilities", "facility management", "property management",
            "site management", "general operations",
        },
        _TIER_ENTRY:     ["Operations Assistant", "Facilities Assistant", "Admin Coordinator"],
        _TIER_JUNIOR:    ["Operations Officer", "Facilities Coordinator", "Operations Coordinator"],
        _TIER_MID:       ["Operations Specialist", "Facilities Officer", "Site Coordinator"],
        _TIER_SENIOR:    ["Operations Manager", "Facilities Manager", "Site Manager"],
        _TIER_PRINCIPAL: ["Director of Operations", "COO", "VP Operations"],
    },
    {
        "name": "education_training",
        "label": "education & training",
        "signals": {
            "teacher", "teaching", "curriculum", "instructor",
            "tutor", "academic", "school", "e-learning",
        },
        _TIER_ENTRY:     ["Teaching Assistant", "Training Assistant"],
        _TIER_JUNIOR:    ["Teacher", "Corporate Trainer", "Instructor"],
        _TIER_MID:       ["Senior Teacher", "Training Specialist", "Curriculum Developer"],
        _TIER_SENIOR:    ["Training Manager", "Academic Coordinator", "L&D Manager"],
        _TIER_PRINCIPAL: ["Head of Education", "Director of Training", "Principal"],
    },
    {
        "name": "legal",
        "label": "legal",
        "signals": {
            "legal", "contract", "litigation", "law", "paralegal", "legal counsel",
            "contract management", "corporate law", "uae law", "arbitration",
        },
        _TIER_ENTRY:     ["Legal Trainee", "Paralegal Assistant"],
        _TIER_JUNIOR:    ["Paralegal", "Legal Officer", "Contract Specialist"],
        _TIER_MID:       ["Legal Specialist", "Contracts Manager", "Senior Legal Officer"],
        _TIER_SENIOR:    ["Legal Manager", "Head of Legal", "Senior Counsel"],
        _TIER_PRINCIPAL: ["General Counsel", "Chief Legal Officer", "Legal Director"],
    },
]

# Signal index: keyword → list of family names (for O(1) lookup)
_SIGNAL_INDEX: dict[str, list[str]] = {}
for _fam in _ROLE_FAMILIES:
    for _sig in _fam["signals"]:
        _SIGNAL_INDEX.setdefault(_sig, []).append(_fam["name"])
_FAMILY_BY_NAME: dict[str, dict] = {f["name"]: f for f in _ROLE_FAMILIES}

# Cross-family bridges: when family X fires with strong evidence, family Y is
# implied with the given hit count. Used to surface adjacent UAE-market roles
# (e.g. environmental specialists at 10yr commonly carry QHSE responsibilities).
_CROSS_FAMILY_BRIDGES: list[tuple[str, int, str, int]] = [
    # (source_family, min_hits, target_family, implied_hits)
    # implied_hits=3 so hse_qhse ranks above iso_quality/compliance (both ~2) in UAE env profiles
    ("environmental_esg", 3, "hse_qhse", 3),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_role_suggestions(
    skills: list[str],
    certifications: list[str],
    years_experience: float | None,
    industries: list[str],
    current_role: str | None = None,
    max_results: int = 7,
) -> dict[str, Any]:
    """Return structured, seniority-aware role suggestions.

    Result schema (see module docstring for full contract).
    Returns ``source="weak_profile"`` and ``roles=[]`` when evidence is too
    sparse to suggest roles confidently; in that case ``clarifying_questions``
    and ``actions`` are populated with product-level prompts.
    """
    try:
        years_num = float(years_experience) if years_experience is not None else None
    except (TypeError, ValueError):
        years_num = None

    skill_lower = [s.lower() for s in (skills or [])]
    cert_lower = [c.lower() for c in (certifications or [])]
    industry_lower = [i.lower() for i in (industries or [])]
    all_signals = skill_lower + cert_lower + industry_lower

    has_any_evidence = bool(
        all_signals or current_role or years_num is not None
    )
    if not has_any_evidence:
        return _weak_profile_response()

    family_hits, matched_signals = _compute_family_hits(all_signals, current_role)

    # Apply cross-family bridges (e.g. env_esg ≥ 3 → hse_qhse implied)
    for src, min_hits, dst, implied in _CROSS_FAMILY_BRIDGES:
        if family_hits.get(src, 0) >= min_hits and family_hits.get(dst, 0) < implied:
            family_hits[dst] = max(family_hits.get(dst, 0), implied)
            matched_signals.setdefault(dst, [])

    if not family_hits:
        return _weak_profile_response()

    tier = _seniority_tier(years_num, current_role)
    ranked_families = sorted(family_hits, key=lambda k: -family_hits[k])[:4]
    caps = _family_caps(len(ranked_families), max_results)

    roles: list[dict[str, Any]] = []
    seen_titles: set[str] = set()

    for rank, fname in enumerate(ranked_families):
        cap = caps[rank]
        if cap <= 0:
            continue
        fam = _FAMILY_BY_NAME[fname]
        hits = family_hits[fname]
        is_top_family = rank == 0
        family_titles = _select_titles_for_family(fam, tier, cap, is_top_family)

        for title, is_adjacent in family_titles:
            if title in seen_titles:
                continue
            if len(roles) >= max_results:
                break
            seen_titles.add(title)
            roles.append({
                "title": title,
                "confidence": _compute_confidence(hits, rank, is_adjacent),
                "reason": _build_reason(fname, hits, matched_signals.get(fname, []), cert_lower),
                "segment": fname,
                "search_query": _build_search_query(title),
            })
        if len(roles) >= max_results:
            break

    if not roles:
        return _weak_profile_response()

    return {
        "roles": roles[:max_results],
        "clarifying_questions": [],
        "source": "cv_profile",
        "actions": [],
    }


def needs_clarification(
    skills: list[str],
    certifications: list[str],
    years_experience: float | None,
    industries: list[str],
    current_role: str | None = None,
) -> bool:
    """Return True when profile evidence is too sparse to suggest roles confidently."""
    result = generate_role_suggestions(
        skills, certifications, years_experience, industries, current_role
    )
    return result["source"] == "weak_profile"


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _weak_profile_response() -> dict[str, Any]:
    return {
        "roles": [],
        "clarifying_questions": [
            "What field or industry have you worked in (e.g. HSE, IT, finance, sales, admin, logistics)?",
            "How many years of work experience do you have?",
            "What are your top 2–3 skills or your most recent job title?",
        ],
        "source": "weak_profile",
        "actions": [
            {
                "action": "add_skills",
                "label": "Add skills to my profile",
                "message": "I want to add my skills",
            },
            {
                "action": "upload_cv",
                "label": "Upload my CV",
                "message": "I want to upload my CV",
            },
        ],
    }


def _compute_family_hits(
    all_signals: list[str],
    current_role: str | None,
) -> tuple[dict[str, int], dict[str, list[str]]]:
    """Return (family_hits, matched_signals_per_family)."""
    family_hits: dict[str, int] = {}
    matched: dict[str, list[str]] = {}

    for sig, families in _SIGNAL_INDEX.items():
        if any(sig in s for s in all_signals):
            for fname in families:
                family_hits[fname] = family_hits.get(fname, 0) + 1
                matched.setdefault(fname, []).append(sig)

    if current_role:
        cr_lower = current_role.lower()
        for sig, families in _SIGNAL_INDEX.items():
            if sig in cr_lower:
                for fname in families:
                    family_hits[fname] = family_hits.get(fname, 0) + 1
                    matched.setdefault(fname, []).append(sig)

    return family_hits, matched


def _family_caps(num_families: int, max_results: int) -> list[int]:
    """Per-family role budgets to enforce diversification.

    For typical max_results=7:
      • 1 family   → [7]                  (single domain dominant)
      • 2 families → [4, 3]
      • 3 families → [4, 2, 1]
      • 4 families → [4, 2, 1, 1]         (cap top family at 4, others get
                                           at least 1 each)
    """
    if num_families <= 0:
        return []
    if num_families == 1:
        return [max_results]
    if num_families == 2:
        return [max_results - 3, 3]
    if num_families == 3:
        # [3, 3, 1] ensures rank-1 family (e.g. hse_qhse via bridge) gets 3 slots,
        # enough to include Safety Manager at position 2 of the SENIOR tier.
        return [3, 3, 1]
    # 4+ families: top 4, rest get nothing (already ranked-limited to 4)
    return [4, 2, 1, max(0, max_results - 7)]


def _select_titles_for_family(
    fam: dict,
    tier: str,
    cap: int,
    is_top_family: bool,
) -> list[tuple[str, bool]]:
    """Return list of (title, is_adjacent) tuples for one family up to ``cap``.

    For the top family at senior/principal tiers, blend manager-level (primary)
    and officer/specialist-level (mid) titles so the output reflects how
    senior environmental/HSE/etc roles actually appear in UAE listings.
    """
    primary = list(fam.get(tier, []))
    one_down = _tier_below(tier)
    one_up = _tier_above(tier)
    mid_tier_roles = list(fam.get(one_down, [])) if one_down else []
    up_tier_roles = list(fam.get(one_up, [])) if one_up else []

    # Composition rules per tier
    if tier in (_TIER_SENIOR, _TIER_PRINCIPAL) and is_top_family:
        # For top family at senior+: mix manager + officer-level titles
        # Only pull a PRINCIPAL title when cap is large enough (>=5) so that at
        # cap=4 we fill all 4 slots with MID-tier officer/specialist titles instead.
        principal_take = 1 if (up_tier_roles and cap >= 5) else 0
        senior_take = min(len(primary), max(1, cap - 3))
        mid_take = max(0, cap - senior_take - principal_take)
        selected = (
            [(t, False) for t in primary[:senior_take]]
            + [(t, True) for t in mid_tier_roles[:mid_take]]
            + [(t, True) for t in up_tier_roles[:principal_take]]
        )
    elif tier in (_TIER_SENIOR, _TIER_PRINCIPAL):
        # Secondary families at senior tier: prefer primary tier first
        selected = (
            [(t, False) for t in primary[:cap]]
            + [(t, True) for t in mid_tier_roles[: max(0, cap - len(primary))]]
        )
    else:
        # Entry/junior/mid: take primary first, then adjacent above.
        # For entry/junior tiers, exclude adjacent titles with an explicit "Senior"
        # prefix — those belong to a higher tier and would be misleading.
        adjacent = up_tier_roles
        if tier in (_TIER_ENTRY, _TIER_JUNIOR):
            adjacent = [t for t in adjacent if not t.startswith("Senior")]
        selected = (
            [(t, False) for t in primary[:cap]]
            + [(t, True) for t in adjacent[: max(0, cap - len(primary))]]
        )

    return selected[:cap]


def _tier_below(tier: str) -> str | None:
    return {
        _TIER_PRINCIPAL: _TIER_SENIOR,
        _TIER_SENIOR: _TIER_MID,
        _TIER_MID: _TIER_JUNIOR,
        _TIER_JUNIOR: _TIER_ENTRY,
        _TIER_ENTRY: None,
    }.get(tier)


def _tier_above(tier: str) -> str | None:
    return {
        _TIER_ENTRY: _TIER_JUNIOR,
        _TIER_JUNIOR: _TIER_MID,
        _TIER_MID: _TIER_SENIOR,
        _TIER_SENIOR: _TIER_PRINCIPAL,
        _TIER_PRINCIPAL: None,
    }.get(tier)


def _compute_confidence(hits: int, rank: int, is_adjacent: bool) -> float:
    base = 0.5 + 0.1 * hits - 0.1 * rank
    if is_adjacent:
        base -= 0.05
    return round(max(0.3, min(0.95, base)), 2)


def _build_reason(
    family_name: str,
    hit_count: int,
    matched: list[str],
    cert_lower: list[str],
) -> str:
    """One-line, explainable reason tied to specific CV evidence."""
    fam = _FAMILY_BY_NAME.get(family_name, {})
    label = fam.get("label", family_name.replace("_", " "))

    # Surface up to 2 specific matched signals so the user can see WHY
    distinct = []
    for sig in matched:
        if sig not in distinct:
            distinct.append(sig)
        if len(distinct) >= 2:
            break

    if hit_count >= 3:
        if distinct:
            return f"Strong match for your {label} background ({', '.join(distinct)})"
        return f"Strong match for your {label} background"
    if cert_lower:
        return f"Matches your {label} skills and certifications"
    if distinct:
        return f"Matches your {label} background ({distinct[0]})"
    return f"Matches your {label} background"


def _build_search_query(title: str) -> str:
    """Return an English UAE-searchable query string for the title."""
    # Most UAE job boards understand the title + 'UAE' suffix.
    return f"{title} UAE"
