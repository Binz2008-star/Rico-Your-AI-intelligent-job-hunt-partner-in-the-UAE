"""role_suggester.py — CV-evidence to role suggestions for all job-seeker segments.

Segments covered:
  fresh graduates, junior professionals, mid-level, senior/managers,
  blue-collar/field, technicians, drivers/logistics, sales/customer service,
  admin/office, healthcare, finance/accounting, HR, IT/software/data,
  HSE/QHSE, environmental/ESG/sustainability, hospitality/retail,
  career changers, weak/partial CV profiles, Arabic/mixed-language users

No external API calls. Pure skill+cert+experience → role mapping.
"""
from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# Seniority tiers
# ---------------------------------------------------------------------------

_TIER_ENTRY = "entry"       # 0–2 yrs / fresh graduate
_TIER_JUNIOR = "junior"     # 2–5 yrs
_TIER_MID = "mid"           # 5–9 yrs
_TIER_SENIOR = "senior"     # 9–13 yrs
_TIER_PRINCIPAL = "principal"  # 13+ yrs / director/VP/head


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
# Each family has:
#   signals   — set of lowercase skill/cert keywords that activate this family
#   entry/junior/mid/senior/principal — ordered role title lists (best fit first)
# ---------------------------------------------------------------------------

_ROLE_FAMILIES: list[dict] = [
    {
        "name": "hse_safety",
        "signals": {
            "hse", "safety", "ehs", "qhse", "fire safety", "risk assessment",
            "permit to work", "incident investigation", "nebosh", "iosh", "osha",
            "safety officer", "safety management",
        },
        _TIER_ENTRY:     ["HSE Graduate", "Safety Trainee", "EHS Assistant"],
        _TIER_JUNIOR:    ["HSE Officer", "Safety Officer", "EHS Officer", "QHSE Coordinator"],
        _TIER_MID:       ["HSE Specialist", "QHSE Officer", "Safety Supervisor", "HSE Coordinator"],
        _TIER_SENIOR:    ["HSE Manager", "QHSE Manager", "Safety Manager", "HSE Lead"],
        _TIER_PRINCIPAL: ["Head of HSE", "Director of HSE", "VP Safety & Sustainability"],
    },
    {
        "name": "environmental_esg",
        "signals": {
            "environmental management", "esg", "sustainability", "iso 14001",
            "carbon footprint", "environmental", "green building", "leed",
            "environmental compliance", "climate", "net zero",
        },
        _TIER_ENTRY:     ["Environmental Trainee", "Sustainability Assistant", "ESG Graduate"],
        _TIER_JUNIOR:    ["Environmental Officer", "ESG Analyst", "Sustainability Coordinator"],
        _TIER_MID:       [
            "Environmental Specialist", "ESG Specialist", "Environmental Compliance Officer",
            "Sustainability Officer", "QHSE Manager",
        ],
        _TIER_SENIOR:    [
            "Environmental Manager", "ESG Manager", "Environmental Compliance Manager",
            "Sustainability Manager", "HSE Manager",
        ],
        _TIER_PRINCIPAL: ["Head of Sustainability", "Director of ESG", "VP Environmental Affairs"],
    },
    {
        "name": "compliance_audit",
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
        "signals": {
            "iso 14001", "iso 9001", "iso 45001", "quality", "qc", "quality control",
            "quality assurance", "six sigma", "lean", "kaizen", "quality management",
            "iso", "qa",
        },
        _TIER_ENTRY:     ["Quality Inspector", "QC Assistant", "Quality Trainee"],
        _TIER_JUNIOR:    ["Quality Officer", "ISO Coordinator", "QA/QC Inspector"],
        _TIER_MID:       ["Quality Specialist", "ISO 14001 Specialist", "QA/QC Supervisor"],
        _TIER_SENIOR:    ["Quality Manager", "ISO 14001 Lead Auditor", "QA Manager"],
        _TIER_PRINCIPAL: ["Head of Quality", "Director of Quality Assurance"],
    },
    {
        "name": "it_software",
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
        "signals": {
            "sql", "excel", "power bi", "tableau", "data analysis", "analytics",
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
        "signals": {
            "administration", "admin", "secretary", "office management", "document control",
            "reception", "filing", "scheduling", "executive assistant",
            "personal assistant", "office coordination", "correspondence",
        },
        _TIER_ENTRY:     ["Office Assistant", "Receptionist", "Admin Trainee"],
        _TIER_JUNIOR:    ["Admin Officer", "Document Controller", "Executive Secretary"],
        _TIER_MID:       ["Senior Admin Officer", "Personal Assistant", "Office Supervisor"],
        _TIER_SENIOR:    ["Office Manager", "Admin Manager", "Executive Assistant to C-Suite"],
        _TIER_PRINCIPAL: ["Head of Administration", "Chief of Staff"],
    },
    {
        "name": "sales_customer_service",
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
        "signals": {
            "engineering", "mechanical", "electrical", "civil", "construction",
            "maintenance", "autocad", "structural", "chemical", "industrial",
            "project management", "quantity surveying", "mep",
        },
        _TIER_ENTRY:     ["Graduate Engineer", "Engineering Trainee", "Site Assistant"],
        _TIER_JUNIOR:    ["Engineer", "Site Engineer", "Junior Project Engineer"],
        _TIER_MID:       ["Project Engineer", "Senior Engineer", "Technical Specialist"],
        _TIER_SENIOR:    ["Project Manager", "Engineering Manager", "Senior Project Manager"],
        _TIER_PRINCIPAL: ["Director of Engineering", "Head of Projects", "VP Engineering"],
    },
    {
        "name": "logistics_supply_chain",
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
        "signals": {
            "operations", "facilities", "facility management", "property management",
            "site management", "general operations", "office management", "coordination",
        },
        _TIER_ENTRY:     ["Operations Assistant", "Facilities Assistant", "Admin Coordinator"],
        _TIER_JUNIOR:    ["Operations Officer", "Facilities Coordinator", "Operations Coordinator"],
        _TIER_MID:       ["Operations Specialist", "Facilities Officer", "Site Coordinator"],
        _TIER_SENIOR:    ["Operations Manager", "Facilities Manager", "Site Manager"],
        _TIER_PRINCIPAL: ["Director of Operations", "COO", "VP Operations"],
    },
    {
        "name": "education_training",
        "signals": {
            "teacher", "teaching", "training", "education", "curriculum", "instructor",
            "tutor", "academic", "school", "learning and development", "e-learning",
        },
        _TIER_ENTRY:     ["Teaching Assistant", "Training Assistant"],
        _TIER_JUNIOR:    ["Teacher", "Corporate Trainer", "Instructor"],
        _TIER_MID:       ["Senior Teacher", "Training Specialist", "Curriculum Developer"],
        _TIER_SENIOR:    ["Training Manager", "Academic Coordinator", "L&D Manager"],
        _TIER_PRINCIPAL: ["Head of Education", "Director of Training", "Principal"],
    },
    {
        "name": "legal",
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
) -> list[dict[str, str]]:
    """Return seniority-aware, segment-aware role suggestions ranked by evidence strength.

    Returns a list of dicts with keys: label, reason.
    Returns an empty list when evidence is too weak to make confident suggestions.
    """
    try:
        years_num = float(years_experience) if years_experience is not None else None
    except (TypeError, ValueError):
        years_num = None

    tier = _seniority_tier(years_num, current_role)
    skill_lower = [s.lower() for s in skills]
    cert_lower = [c.lower() for c in certifications]
    all_signals = skill_lower + cert_lower + [i.lower() for i in industries]

    # Count how many signals each family matched — higher = stronger evidence
    family_hits: dict[str, int] = {}
    for sig in _SIGNAL_INDEX:
        if any(sig in s for s in all_signals):
            for fname in _SIGNAL_INDEX[sig]:
                family_hits[fname] = family_hits.get(fname, 0) + 1

    # Also check current_role text against family signals
    if current_role:
        cr_lower = current_role.lower()
        for sig in _SIGNAL_INDEX:
            if sig in cr_lower:
                for fname in _SIGNAL_INDEX[sig]:
                    family_hits[fname] = family_hits.get(fname, 0) + 1

    if not family_hits:
        return []

    # Rank families by hit count, take top 3 most relevant
    ranked_families = sorted(family_hits, key=lambda k: -family_hits[k])[:3]

    suggestions: list[dict[str, str]] = []
    seen_labels: set[str] = set()

    for fname in ranked_families:
        fam = _FAMILY_BY_NAME[fname]
        roles_for_tier: list[str] = fam.get(tier, [])
        # Always include adjacent tier as adjacent options
        adjacent_roles: list[str] = []
        if tier == _TIER_ENTRY:
            adjacent_roles = fam.get(_TIER_JUNIOR, [])[:1]
        elif tier == _TIER_JUNIOR:
            adjacent_roles = fam.get(_TIER_MID, [])[:1]
        elif tier == _TIER_MID:
            adjacent_roles = fam.get(_TIER_JUNIOR, [])[:1] + fam.get(_TIER_SENIOR, [])[:1]
        elif tier == _TIER_SENIOR:
            adjacent_roles = fam.get(_TIER_MID, [])[:1] + fam.get(_TIER_PRINCIPAL, [])[:1]

        hit_count = family_hits[fname]
        reason = _build_reason(fname, hit_count, skills, certifications)

        for role in roles_for_tier + adjacent_roles:
            if role not in seen_labels and len(suggestions) < max_results:
                seen_labels.add(role)
                suggestions.append({"label": role, "reason": reason})

    return suggestions[:max_results]


def needs_clarification(
    skills: list[str],
    certifications: list[str],
    years_experience: float | None,
    industries: list[str],
    current_role: str | None = None,
) -> bool:
    """Return True when profile evidence is too sparse to suggest roles confidently."""
    has_evidence = bool(
        skills
        or certifications
        or industries
        or current_role
        or years_experience is not None
    )
    if not has_evidence:
        return True
    suggestions = generate_role_suggestions(
        skills, certifications, years_experience, industries, current_role
    )
    return len(suggestions) == 0


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _build_reason(
    family_name: str,
    hit_count: int,
    skills: list[str],
    certifications: list[str],
) -> str:
    """Build a one-line human-readable reason string."""
    _FRIENDLY_NAMES = {
        "hse_safety":          "HSE/Safety",
        "environmental_esg":   "Environmental/ESG",
        "compliance_audit":    "compliance & audit",
        "iso_quality":         "ISO/quality",
        "it_software":         "software development",
        "it_support_networks": "IT/networking",
        "data_analytics":      "data & analytics",
        "finance_accounting":  "finance & accounting",
        "hr_recruitment":      "HR & recruitment",
        "admin_office":        "administration",
        "sales_customer_service": "sales & customer service",
        "marketing":           "marketing",
        "hospitality_food":    "hospitality",
        "healthcare":          "healthcare",
        "engineering":         "engineering",
        "logistics_supply_chain": "logistics & supply chain",
        "driving_transport":   "transport",
        "blue_collar_field":   "field/technical",
        "operations":          "operations",
        "education_training":  "education & training",
        "legal":               "legal",
    }
    label = _FRIENDLY_NAMES.get(family_name, family_name.replace("_", " "))
    if hit_count >= 3:
        return f"Strong match for your {label} background"
    if certifications:
        return f"Matches your {label} skills and certifications"
    return f"Matches your {label} background"
