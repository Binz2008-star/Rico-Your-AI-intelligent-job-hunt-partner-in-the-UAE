"""src/agent/intelligence/normalizer.py

Role normalization layer for Rico Agent OS.

Maps various role title variants to canonical forms:
- sales man → Sales Representative
- dev → Software Engineer
- PM → Product Manager
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

_ROLE_TOKEN_CASES: Dict[str, str] = {
    # Core technology / product
    "ai": "AI",
    "api": "API",
    "aws": "AWS",
    "azure": "Azure",
    "bi": "BI",
    "crm": "CRM",
    "cto": "CTO",
    "dataops": "DataOps",
    "devops": "DevOps",
    "erp": "ERP",
    "gcp": "GCP",
    "ios": "iOS",
    "it": "IT",
    "ml": "ML",
    "qa": "QA",
    "sre": "SRE",
    "ui": "UI",
    "ux": "UX",

    # Admin, sales, service, and operations
    "b2b": "B2B",
    "b2c": "B2C",
    "bpo": "BPO",
    "cx": "CX",
    "ecommerce": "eCommerce",
    "fb": "F&B",
    "fmcg": "FMCG",
    "fnb": "F&B",
    "f&b": "F&B",
    "gm": "GM",
    "pa": "PA",
    "pr": "PR",
    "vip": "VIP",

    # Healthcare / medical licensing
    "acls": "ACLS",
    "bls": "BLS",
    "dha": "DHA",
    "doh": "DOH",
    "haad": "HAAD",
    "hcpc": "HCPC",
    "icu": "ICU",
    "moh": "MOH",
    "mohap": "MOHAP",
    "nclex": "NCLEX",
    "ot": "OT",
    "pals": "PALS",
    "rn": "RN",

    # HSE / sustainability / compliance
    "ehs": "EHS",
    "esg": "ESG",
    "hse": "HSE",
    "hseq": "HSEQ",
    "hsse": "HSSE",
    "iso": "ISO",
    "iosh": "IOSH",
    "nebosh": "NEBOSH",
    "osha": "OSHA",
    "qhse": "QHSE",
    "qc": "QC",

    # Business, finance, people, projects
    "acca": "ACCA",
    "aml": "AML",
    "ca": "CA",
    "cfa": "CFA",
    "cfo": "CFO",
    "cma": "CMA",
    "cpa": "CPA",
    "cips": "CIPS",
    "cipd": "CIPD",
    "cisa": "CISA",
    "cism": "CISM",
    "cissp": "CISSP",
    "cva": "CVA",
    "fcpa": "FCPA",
    "ifrs": "IFRS",
    "hr": "HR",
    "kpi": "KPI",
    "kyc": "KYC",
    "llb": "LLB",
    "llm": "LLM",
    "mba": "MBA",
    "mcips": "MCIPS",
    "pmp": "PMP",
    "pmo": "PMO",
    "supplychain": "Supply Chain",
    "vat": "VAT",

    # Engineering / built environment / UAE market
    "adnoc": "ADNOC",
    "ashrae": "ASHRAE",
    "bim": "BIM",
    "cad": "CAD",
    "cctv": "CCTV",
    "dewa": "DEWA",
    "dm": "DM",
    "elv": "ELV",
    "feewa": "FEWA",
    "gcc": "GCC",
    "hvac": "HVAC",
    "leed": "LEED",
    "mep": "MEP",
    "mro": "MRO",
    "nakheel": "Nakheel",
    "rera": "RERA",
    "sewa": "SEWA",
    "sira": "SIRA",
    "uae": "UAE",

    # Education, aviation, logistics, and language credentials
    "celta": "CELTA",
    "iata": "IATA",
    "ielts": "IELTS",
    "khda": "KHDA",
    "lms": "LMS",
    "pgce": "PGCE",
    "sen": "SEN",
    "scm": "SCM",
    "stcw": "STCW",
    "tefl": "TEFL",
    "tesol": "TESOL",
    "toefl": "TOEFL",
    "wms": "WMS",
}

# Common typo corrections applied before variant mapping
_TYPO_CORRECTIONS: Dict[str, str] = {
    "opration": "operation",
    "opertion": "operation",
    "enviromental": "environmental",
    "complince": "compliance",
    "saftey": "safety",
}

# Common role variants mapping to canonical forms
_ROLE_VARIANTS: Dict[str, str] = {
    # Sales roles
    "sales man": "Sales Representative",
    "salesman": "Sales Representative",
    "sales rep": "Sales Representative",
    "salesperson": "Sales Representative",
    "account executive": "Sales Representative",
    "ae": "Sales Representative",
    "business development": "Business Development Representative",
    "bdr": "Business Development Representative",
    "sales executive": "Sales Executive",

    # Engineering roles
    "dev": "Software Engineer",
    "developer": "Software Engineer",
    "software dev": "Software Engineer",
    "swe": "Software Engineer",
    "backend dev": "Backend Engineer",
    "frontend dev": "Frontend Engineer",
    "fullstack": "Full Stack Engineer",
    "full stack": "Full Stack Engineer",
    "fullstack dev": "Full Stack Engineer",
    "web dev": "Web Developer",
    "web developer": "Web Developer",
    "mobile dev": "Mobile Developer",
    "ios dev": "iOS Developer",
    "android dev": "Android Developer",

    # Product roles
    "pm": "Product Manager",
    "product owner": "Product Manager",
    "product lead": "Product Lead",
    "apm": "Associate Product Manager",
    "senior pm": "Senior Product Manager",
    "head of product": "Head of Product",

    # Data roles
    "data scientist": "Data Scientist",
    "data science": "Data Scientist",
    "ml engineer": "Machine Learning Engineer",
    "machine learning engineer": "Machine Learning Engineer",
    "data analyst": "Data Analyst",
    "data engineer": "Data Engineer",

    # Design roles
    "ux designer": "UX Designer",
    "ui designer": "UI Designer",
    "product designer": "Product Designer",
    "graphic designer": "Graphic Designer",
    "design lead": "Design Lead",

    # Marketing roles
    "marketing manager": "Marketing Manager",
    "digital marketing": "Digital Marketing Specialist",
    "growth marketer": "Growth Marketer",
    "content writer": "Content Writer",
    "seo specialist": "SEO Specialist",

    # Operations roles
    "ops": "Operations Manager",
    "operations": "Operations Manager",
    "devops": "DevOps Engineer",
    "devops engineer": "DevOps Engineer",
    "sre": "Site Reliability Engineer",
    "site reliability engineer": "Site Reliability Engineer",

    # HR roles
    "hr": "Human Resources Manager",
    "human resources": "Human Resources Manager",
    "recruiter": "Recruiter",
    "talent acquisition": "Talent Acquisition Specialist",

    # Finance roles
    "accountant": "Accountant",
    "finance manager": "Finance Manager",
    "financial analyst": "Financial Analyst",

    # HSE / Safety / Compliance roles (with typo variants)
    "hse manager": "HSE Manager",
    "qhse manager": "QHSE Manager",
    "ehs manager": "EHS Manager",
    "safety manager": "Safety Manager",
    "environmental manager": "Environmental Manager",
    "compliance manager": "Compliance Manager",
    "saftey manager": "Safety Manager",
    "enviromental manager": "Environmental Manager",
    "complince manager": "Compliance Manager",
    "oprations manager": "Operations Manager",
    "opertions manager": "Operations Manager",
}

# Common prefixes to strip
_PREFIXES: Set[str] = {
    "senior ",
    "sr ",
    "lead ",
    "principal ",
    "staff ",
    "junior ",
    "jr ",
    "associate ",
    "mid-level ",
    "mid level ",
    "head of ",
    "vp of ",
    "vice president of ",
    "chief ",
    "cto ",
    "ceo ",
    "cfo ",
    "coo ",
}

# Common suffixes to strip
_SUFFIXES: Set[str] = {
    " i",
    " ii",
    " iii",
    " iv",
    " 1",
    " 2",
    " 3",
    " (remote)",
    " (hybrid)",
    " (onsite)",
}


class RoleNormalizer:
    """
    Normalizes role titles to canonical forms.

    Handles:
    - Variant mapping (sales man → Sales Representative)
    - Prefix/suffix stripping (Senior Software Engineer → Software Engineer)
    - Case normalization (software engineer → Software Engineer)
    - Special character handling
    """

    def __init__(self):
        self._cache: Dict[str, str] = {}

    def normalize(self, role: str) -> str:
        """
        Normalize a role title to its canonical form.

        Args:
            role: Raw role title (e.g., "senior sales man")

        Returns:
            Canonical role title (e.g., "Sales Representative")
        """
        try:
            if not role or not isinstance(role, str):
                return "Unknown"

            # Check cache
            role_lower = role.lower().strip()
            if role_lower in self._cache:
                return self._cache[role_lower]

            # Step 1: Clean the input
            cleaned = self._clean_input(role)
            cleaned_lower = cleaned.lower()

            # Step 1b: Apply typo corrections
            for typo, correction in _TYPO_CORRECTIONS.items():
                if typo in cleaned_lower:
                    cleaned_lower = cleaned_lower.replace(typo, correction)
                    cleaned = cleaned_lower

            # Step 2: Check direct variant mapping
            if cleaned_lower in _ROLE_VARIANTS:
                canonical = _ROLE_VARIANTS[cleaned.lower()]
                self._cache[role_lower] = canonical
                return canonical

            # Step 3: Strip prefixes and suffixes
            base_role = self._strip_prefixes_suffixes(cleaned)

            # Step 4: Check variant mapping on base role
            if base_role.lower() in _ROLE_VARIANTS:
                canonical = _ROLE_VARIANTS[base_role.lower()]
                self._cache[role_lower] = canonical
                return canonical

            # Step 5: Capitalize properly
            canonical = self._capitalize_properly(base_role)

            self._cache[role_lower] = canonical
            return canonical
        except Exception as e:
            logger.warning(f"Role normalization failed for '{role}': {e}")
            return self._capitalize_properly(role) if role else "Unknown"

    def _clean_input(self, role: str) -> str:
        """Clean the raw role input."""
        try:
            if not role:
                return ""
            # Remove special characters
            cleaned = re.sub(r"[^\w\s\-]", "", role)
            # Normalize whitespace
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            return cleaned
        except Exception as e:
            logger.warning(f"Input cleaning failed for '{role}': {e}")
            return role or ""

    def _strip_prefixes_suffixes(self, role: str) -> str:
        """Strip common prefixes and suffixes."""
        result = role

        # Strip prefixes
        for prefix in sorted(_PREFIXES, key=len, reverse=True):
            if result.lower().startswith(prefix):
                result = result[len(prefix):].strip()
                break

        # Strip suffixes
        for suffix in sorted(_SUFFIXES, key=len, reverse=True):
            if result.lower().endswith(suffix):
                result = result[:-len(suffix)].strip()
                break

        return result

    def _capitalize_properly(self, role: str) -> str:
        """Capitalize the role title properly."""
        try:
            if not role:
                return ""
            words = role.split()
            capitalized = []
            for word in words:
                if word:
                    token_case = _ROLE_TOKEN_CASES.get(word.lower())
                    if token_case:
                        capitalized.append(token_case)
                    else:
                        capitalized.append(word[0].upper() + word[1:].lower())
            return " ".join(capitalized)
        except Exception as e:
            logger.warning(f"Capitalization failed for '{role}': {e}")
            return role.title() if role else ""

    def get_variants(self, canonical_role: str) -> List[str]:
        """
        Get all known variants for a canonical role.

        Args:
            canonical_role: Canonical role title

        Returns:
            List of variant titles that map to this canonical role
        """
        variants = []
        canonical_lower = canonical_role.lower()

        for variant, canonical in _ROLE_VARIANTS.items():
            if canonical.lower() == canonical_lower:
                variants.append(variant)

        return sorted(variants)


# Module-level singleton
_role_normalizer = RoleNormalizer()


def normalize_role(role: str) -> str:
    """
    Convenience function to normalize a role title.

    Uses the singleton RoleNormalizer instance.
    """
    return _role_normalizer.normalize(role)


def get_role_variants(canonical_role: str) -> List[str]:
    """
    Convenience function to get role variants.

    Uses the singleton RoleNormalizer instance.
    """
    return _role_normalizer.get_variants(canonical_role)
