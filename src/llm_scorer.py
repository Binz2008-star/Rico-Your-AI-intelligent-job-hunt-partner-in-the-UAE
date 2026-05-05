"""
src/llm_scorer.py
Semantic job scoring using local sentence-transformers embeddings.
Model: sentence-transformers/all-MiniLM-L6-v2
Falls back to keyword scoring if model unavailable.
"""
from __future__ import annotations
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_FILE = BASE_DIR / "data" / "llm_score_cache.json"

# Candidate profile for semantic matching
_PROFILE_TEXT = """
ESG Manager Environmental Manager Sustainability HSE Compliance ISO 14001
waste management environmental operations UAE regulations health safety
environmental senior operations manager regulatory compliance
"""

# Global model instance (lazy loaded)
_model = None
_profile_embedding = None


def _get_model():
    """Lazy load sentence-transformers model."""
    global _model, _profile_embedding
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading sentence-transformers model...")
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            _profile_embedding = _model.encode(_PROFILE_TEXT, convert_to_tensor=True)
            logger.info("Model loaded successfully")
        except ImportError:
            logger.warning("sentence-transformers not installed, using keyword fallback")
            return None, None
        except Exception as e:
            logger.warning(f"Failed to load model: {e}, using keyword fallback")
            return None, None
    return _model, _profile_embedding


def _fp(job):
    """Generate fingerprint for caching."""
    k = "|".join([
        str(job.get("title", "")).lower(),
        str(job.get("company", "")).lower(),
        str(job.get("link", "")).strip()
    ])
    return hashlib.md5(k.encode()).hexdigest()


def _load_cache():
    """Load score cache from disk."""
    try:
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_cache(cache):
    """Save score cache to disk."""
    try:
        CACHE_FILE.parent.mkdir(exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache, indent=2))
    except Exception:
        pass


def _score_semantic(job):
    """Score job using semantic embeddings."""
    model, profile_embedding = _get_model()
    if model is None:
        return None

    try:
        # Create job text for embedding
        job_text = f"{job.get('title', '')} {job.get('description', '')[:500]}"

        # Get embedding
        job_embedding = model.encode(job_text, convert_to_tensor=True)

        # Calculate cosine similarity
        from sentence_transformers import util
        similarity = util.cos_sim(profile_embedding, job_embedding)[0]

        # Convert to 0-100 score with scaling
        score = max(0, min(100, int(float(similarity) * 100)))

        # Location boost
        loc = (str(job.get("location", "")) + str(job.get("company", ""))).lower()
        if any(x in loc for x in ["uae", "dubai", "abu dhabi", "ajman", "sharjah"]):
            score = min(100, score + 10)

        logger.debug(f"semantic_embed title={job.get('title')!r} similarity={float(similarity):.3f} score={score}")
        return score

    except Exception as e:
        logger.warning(f"semantic_score_failed error={e}")
        return None


def _kw(job):
    """Fallback keyword scoring."""
    try:
        from src.scoring import score_job
        return int(score_job(job))
    except Exception:
        return 0


def score_jobs_llm(jobs, use_cache=True):
    """
    Score jobs using semantic embeddings with keyword fallback.

    Args:
        jobs: List of job dictionaries
        use_cache: Whether to use score cache

    Returns:
        List of jobs with 'score' field added
    """
    if not jobs:
        return jobs

    cache = _load_cache() if use_cache else {}
    hits = semantic = kw = 0

    for job in jobs:
        fp = _fp(job)

        # Check cache
        if use_cache and fp in cache:
            job["score"] = cache[fp]
            job["score_source"] = "cache"
            hits += 1
            continue

        # Try semantic scoring
        s = _score_semantic(job)
        if s is None:
            # Fallback to keyword scoring
            s = _kw(job)
            job["score_source"] = "keyword"
            kw += 1
        else:
            job["score_source"] = "semantic"
            semantic += 1

        job["score"] = s
        cache[fp] = s

        # Small delay to avoid overwhelming resources
        time.sleep(0.05)

    # Save cache
    _save_cache(cache)

    logger.info(
        f"scoring_complete total={len(jobs)} cache={hits} semantic={semantic} keyword={kw}"
    )

    return jobs
