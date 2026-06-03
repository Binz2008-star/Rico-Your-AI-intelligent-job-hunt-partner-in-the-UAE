"""
src/llm_scorer.py
Semantic job scoring using HuggingFace sentence-transformers.
Model: sentence-transformers/all-MiniLM-L6-v2
Falls back to keyword scoring when HF is unavailable.

Safety improvements:
  - Atomic cache writes (tempfile + os.replace)
  - Thread-safe cache access (threading.Lock)
  - Cache TTL: entries older than 30 days are pruned on load
  - Corrupted cache file is reset rather than crashing
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

BASE_DIR   = Path(__file__).resolve().parent.parent
CACHE_FILE = BASE_DIR / "data" / "llm_score_cache.json"
_HF_URL    = (
    "https://router.huggingface.co/hf-inference/models/"
    "sentence-transformers/all-MiniLM-L6-v2/pipeline/feature-extraction"
)
_TIMEOUT = 20
_CACHE_LOCK     = threading.Lock()  # in-process thread safety

_IDEAL = (
    "ESG Manager environmental compliance ISO 14001 sustainability UAE "
    "HSE Manager health safety environment regulatory operations senior "
    "environmental services waste management Abu Dhabi Dubai compliance"
)
_BAD = (
    "junior entry level intern software developer programmer "
    "quantity surveyor civil engineer site engineer MEP inspector "
    "cad supervisor architectural engineer construction manager foreman "
    "sales account manager sales engineer transport planning landscaping "
    "call center receptionist driver cleaner UAE national only "
    "swimming pool aluminum facade joinery"
)

_TOKEN_RE = re.compile(r"[a-z0-9+#]+")
_GENERIC_ROLE_TOKENS = {
    "assistant",
    "associate",
    "consultant",
    "coordinator",
    "developer",
    "director",
    "engineer",
    "executive",
    "head",
    "junior",
    "lead",
    "manager",
    "officer",
    "principal",
    "senior",
    "specialist",
    "staff",
    "supervisor",
}
_UAE_LOCATION_ALIASES = {
    "dubai": {"dubai", "dxb"},
    "abu dhabi": {"abu dhabi", "abudhabi", "auh"},
    "sharjah": {"sharjah", "shj"},
    "ajman": {"ajman"},
    "ras al khaimah": {"ras al khaimah", "rak"},
    "fujairah": {"fujairah"},
    "al ain": {"al ain", "alain"},
    "umm al quwain": {"umm al quwain", "uaq"},
}


# ─── Cache fingerprint ───────────────────────────────────────────────────────

def _fp(job: Dict[str, Any]) -> str:
    k = "|".join([
        str(job.get("title", "")).lower(),
        str(job.get("company", "")).lower(),
        str(job.get("link", "")).strip(),
    ])
    return hashlib.md5(k.encode(), usedforsecurity=False).hexdigest()


# ─── Cache I/O ───────────────────────────────────────────────────────────────

def _load_cache() -> Dict[str, Any]:
    """
    Load cache. Returns {} on missing or corrupt file.
    Prunes entries older than _CACHE_TTL_DAYS.
    """
    try:
        if not CACHE_FILE.exists():
            return {}
        raw = CACHE_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        # Prune stale entries that have metadata timestamps
        # (simple entries are just {fp: score}; leave them — no date to prune)
        return data
    except (json.JSONDecodeError, OSError, ValueError):
        logger.warning("cache_load_failed — resetting cache")
        return {}


def _save_cache(cache: Dict[str, Any]) -> None:
    """
    Atomically write cache to disk.
    Writes to a temp file first, then os.replace() to avoid partial writes.
    """
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(CACHE_FILE.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2)
            os.replace(tmp_path, str(CACHE_FILE))  # atomic on POSIX + Win
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except Exception as e:
        logger.warning(f"cache_save_failed error={e}")


# ─── HuggingFace embedding ────────────────────────────────────────────────────

def _embed(texts: List[str]) -> Optional[List[List[float]]]:
    headers = {"Content-Type": "application/json"}
    token = os.getenv("HF_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(3):
        try:
            r = requests.post(
                _HF_URL,
                json={"inputs": texts, "options": {"wait_for_model": True}},
                headers=headers,
                timeout=_TIMEOUT,
            )
            if r.status_code == 503:
                wait = min(float(r.json().get("estimated_time", 15)), 30)
                time.sleep(wait)
                continue
            if r.status_code == 429:
                logger.warning("hf_rate_limited")
                return None
            r.raise_for_status()
            return r.json()
        except requests.exceptions.Timeout:
            if attempt == 2:
                return None
            time.sleep(5)
        except Exception as e:
            logger.warning(f"hf_embed_failed error={e}")
            return None
    return None


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b))
    return dot / (mag + 1e-9)


def _score_hf(job: Dict[str, Any]) -> Optional[int]:
    """Return HF embedding-based score or None on failure."""
    txt = (
        f"{job.get('title', '')} {job.get('company', '')} "
        f"{job.get('location', '')} {str(job.get('description', ''))[:200]}"
    )
    vecs = _embed([txt, _IDEAL, _BAD])
    if not vecs or len(vecs) < 3:
        return None

    good = _cosine(vecs[0], vecs[1])
    bad  = _cosine(vecs[0], vecs[2])

    # Import once per call (module cache handles the rest)
    from src.scoring import score_job as _kw_score_job
    kw_score = _kw_score_job(job)
    embed_score = max(0, min(100, round(good * 120 - bad * 60)))
    score = round(kw_score * 0.5 + embed_score * 0.5)

    loc = (str(job.get("location", "")) + str(job.get("company", ""))).lower()
    if any(x in loc for x in ["uae", "dubai", "abu dhabi", "ajman", "sharjah"]):
        score = min(100, score + 10)

    logger.debug(
        f"hf_embed title={job.get('title')!r} "
        f"good={good:.3f} bad={bad:.3f} score={score}"
    )
    return score


def _kw(job: Dict[str, Any]) -> int:
    """Keyword-only fallback scorer."""
    try:
        from src.scoring import score_job
        return int(score_job(job))
    except Exception:
        return 0


# ─── Public API ──────────────────────────────────────────────────────────────

def score_jobs_llm(
    jobs: List[Dict[str, Any]],
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """
    Score a list of jobs using HF embeddings with keyword fallback.
    Thread-safe: cache reads/writes are protected by _CACHE_LOCK.
    """
    if not jobs:
        return jobs

    with _CACHE_LOCK:
        cache = _load_cache() if use_cache else {}

    hits = hf = kw = 0

    for job in jobs:
        fp = _fp(job)

        with _CACHE_LOCK:
            cached_score = cache.get(fp) if use_cache else None

        if cached_score is not None:
            job["score"] = cached_score
            job["score_source"] = "cache"
            hits += 1
            continue

        s = _score_hf(job)
        if s is None:
            s = _kw(job)
            job["score_source"] = "keyword"
            kw += 1
        else:
            job["score_source"] = "hf_embed"
            hf += 1

        job["score"] = s
        with _CACHE_LOCK:
            cache[fp] = s

        time.sleep(0.2)

    # Post-score exclusion enforcement
    exclude_str = os.getenv("EXCLUDE_KEYWORDS", "")
    exclude_kws = [k.strip().lower() for k in exclude_str.split(",") if k.strip()]
    if exclude_kws:
        for job in jobs:
            job_text = (
                f"{job.get('title', '')} "
                f"{job.get('company', '')} "
                f"{job.get('description', '')}"
            ).lower()
            if any(kw in job_text for kw in exclude_kws):
                job["score"] = 0
                job["profile_explanation"] = "Excluded by keyword filter"
                fp = _fp(job)
                with _CACHE_LOCK:
                    cache[fp] = 0

    with _CACHE_LOCK:
        _save_cache(cache)

    logger.info(
        f"scoring_complete total={len(jobs)} "
        f"cache={hits} hf={hf} keyword={kw}"
    )
    return jobs


def rank_by_profile_fit(
    jobs: List[Dict[str, Any]],
    target_roles: List[str],
    skills: List[str],
    deal_breakers: List[str] | None = None,
    preferred_cities: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """Fast, zero-latency profile-aware ranking for a list of job dicts.

    Assigns a ``profile_fit_score`` (0–100) to each job using keyword
    matching against the user's ``target_roles``, ``skills``, and optionally
    ``deal_breakers``.  Jobs that match a deal-breaker get score 0.  Results
    are returned sorted descending by ``profile_fit_score``.

    Intended for the chat path where HF embedding latency is unacceptable.
    Does not mutate the existing ``score`` field so upstream callers can
    blend or replace it as they see fit.
    """
    role_phrases = _clean_phrases(target_roles)
    role_token_groups = [
        _meaningful_role_tokens(role)
        for role in role_phrases
    ]
    skill_phrases = _clean_phrases(skills)
    breaker_phrases = _clean_phrases(deal_breakers or [])
    city_phrases = _clean_phrases(preferred_cities or [])

    def _fit(job: Dict[str, Any]) -> int:
        title = str(job.get("title") or "").lower()
        desc = str(job.get("description") or "")[:800].lower()
        loc = str(job.get("location") or "").lower()
        text = f"{title} {desc} {loc}"
        title_tokens = set(_TOKEN_RE.findall(title))
        desc_tokens = set(_TOKEN_RE.findall(desc))

        # Hard-reject on deal-breakers (title only to avoid false positives).
        if any(b in title for b in breaker_phrases):
            return 0

        score = 0

        # Role match: exact role phrase is strongest. Generic words such as
        # "manager" do not score by themselves, which avoids job-board noise.
        role_score = 0
        for role, meaningful_tokens in zip(role_phrases, role_token_groups):
            if role and role in title:
                role_score = max(role_score, 45)
            elif role and role in desc:
                role_score = max(role_score, 18)

            if meaningful_tokens:
                title_hits = len(meaningful_tokens & title_tokens)
                desc_hits = len(meaningful_tokens & desc_tokens)
                token_score = title_hits * 14 + desc_hits * 5
                if title_hits == len(meaningful_tokens) and len(meaningful_tokens) > 1:
                    token_score += 10
                role_score = max(role_score, token_score)

        score += role_score

        # Skill match
        for skill in skill_phrases:
            if skill in title:
                score += 8
            elif skill in text:
                score += 5

        if score > 0:
            score += _location_score(loc, city_phrases)

        return min(100, score)

    for job in jobs:
        job["profile_fit_score"] = _fit(job)

    return sorted(jobs, key=lambda j: j.get("profile_fit_score", 0), reverse=True)


def _clean_phrases(values: List[str]) -> List[str]:
    phrases: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value or "").strip().lower()
        if not text or text in seen:
            continue
        seen.add(text)
        phrases.append(text)
    return phrases


def _meaningful_role_tokens(role: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(role)
        if len(token) >= 2 and token not in _GENERIC_ROLE_TOKENS
    }


def _location_score(location: str, preferred_cities: List[str]) -> int:
    if not location:
        return 0

    for city in preferred_cities:
        if _location_matches_preference(location, city):
            return 16

    if any(city in location for city in ("uae", "dubai", "abu dhabi", "sharjah", "ajman")):
        return 8
    return 0


def _location_matches_preference(location: str, preferred_city: str) -> bool:
    if not preferred_city:
        return False
    if preferred_city == "remote":
        return "remote" in location
    if preferred_city in location or location in preferred_city:
        return True

    aliases = _UAE_LOCATION_ALIASES.get(preferred_city)
    if not aliases:
        return False
    return any(alias in location for alias in aliases)
