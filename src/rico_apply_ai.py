"""
src/rico_apply_ai.py
AI engine for per-job CV tailoring and cover letter generation.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_MAX_CV_CHARS = 6000
_MAX_JD_CHARS = 3000
_MAX_COMBINED_OUTPUT_TOKENS = 3500

_CV_START = "[TAILORED_CV]"
_CV_END = "[/TAILORED_CV]"
_COVER_START = "[COVER_LETTER]"
_COVER_END = "[/COVER_LETTER]"


def _parse_tailored_output(text: str) -> Optional[Dict[str, str]]:
    """Extract tailored CV and cover letter from a single marked response.

    Returns None if either section is missing or empty.
    """
    cv_match = re.search(
        re.escape(_CV_START) + r"(.*?)" + re.escape(_CV_END),
        text,
        re.DOTALL,
    )
    cl_match = re.search(
        re.escape(_COVER_START) + r"(.*?)" + re.escape(_COVER_END),
        text,
        re.DOTALL,
    )
    if not cv_match or not cl_match:
        return None
    tailored_cv = cv_match.group(1).strip()
    cover_letter = cl_match.group(1).strip()
    if not tailored_cv or not cover_letter:
        return None
    return {"tailored_cv": tailored_cv, "cover_letter": cover_letter}


def _get_ai_client():
    try:
        from src.rico_openai_runtime import _build_client, _provider_key_present, _provider_models
        from src.rico_env import get_ai_provider
        provider = get_ai_provider()
        if provider not in ("openai", "deepseek") or not _provider_key_present(provider):
            return None, None, None
        model, _ = _provider_models(provider)
        client = _build_client(provider)
        return client, provider, model
    except Exception as exc:
        logger.warning("AI client unavailable for apply: %s", exc)
        return None, None, None


def _call_ai(client, provider: str, model: str, system: str, user: str, max_tokens: int = 2000) -> str:
    if provider == "openai":
        from src.rico_openai_runtime import _extract_response_text
        resp = client.responses.create(
            model=model,
            input=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_output_tokens=max_tokens,
        )
        text = _extract_response_text(resp)
        if not text:
            raise ValueError("OpenAI response contained no usable text")
        return text
    else:
        from src.rico_openai_runtime import _extract_chat_completion_text
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=0.4,
        )
        text = _extract_chat_completion_text(resp)
        if not text:
            raise ValueError("DeepSeek response contained no usable text")
        return text


def _keyword_fallback(cv_text: str, job: Dict[str, Any]) -> Dict[str, str]:
    title = job.get("title", "this position")
    company = job.get("company", "your company")
    cover = (
        f"Dear Hiring Manager,\n\n"
        f"I am writing to express my strong interest in the {title} role at {company}. "
        f"Based on my experience and skills, I believe I would be an excellent fit for this opportunity "
        f"and would welcome the chance to contribute to your team.\n\n"
        f"My background aligns well with the requirements outlined in the job description, and I am "
        f"confident in my ability to deliver results from day one.\n\n"
        f"I look forward to the opportunity to discuss how my experience can benefit {company}.\n\n"
        f"Sincerely,\n[Your Name]"
    )
    return {"tailored_cv": cv_text, "cover_letter": cover}


def tailor_application(cv_text: str, profile: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, str]:
    """
    Generate a tailored CV and cover letter for a specific job.
    Returns {"tailored_cv": str, "cover_letter": str}.
    Never raises.
    """
    title = job.get("title", "")
    company = job.get("company", "")
    description = (job.get("description") or job.get("why") or "")[:_MAX_JD_CHARS]
    location = job.get("location", "UAE")
    name = profile.get("name") or "the candidate"
    target_roles = ", ".join(profile.get("target_roles") or [title])
    truncated_cv = cv_text[:_MAX_CV_CHARS]

    client, provider, model = _get_ai_client()
    if client is None:
        logger.info("AI unavailable — using fallback for %s @ %s", title, company)
        return _keyword_fallback(cv_text, job)

    combined_system = (
        "You are an expert UAE job application writer. You will receive a candidate's CV "
        "and a job description. Produce two outputs:\n"
        "1. A tailored CV: rewrite the candidate's CV to align with the job, keeping all "
        "facts true, mirroring keywords naturally, reordering bullets, and preserving the "
        "section structure (Summary, Experience, Education, Skills).\n"
        "2. A concise, compelling cover letter (3 short paragraphs, max 250 words): open "
        "with the role and company, match 2-3 specific achievements from the CV, close with "
        "a call to action, and sign off as the candidate.\n\n"
        "Use EXACTLY these section markers and nothing else:\n"
        f"{_CV_START}...{_CV_END}\n"
        f"{_COVER_START}...{_COVER_END}\n\n"
        "Do not output any other text, preamble, or markdown fences."
    )
    combined_user = (
        f"Candidate name: {name}\n"
        f"Target role: {title} at {company} ({location})\n"
        f"Target roles profile: {target_roles}\n\n"
        f"Job description:\n{description}\n\n"
        f"Candidate's current CV:\n{truncated_cv}\n\n"
        f"Instructions:\n"
        f"1. Output the tailored CV inside {_CV_START}...{_CV_END}.\n"
        f"2. Output the cover letter inside {_COVER_START}...{_COVER_END}.\n"
        f"3. Do not invent experience, dates, skills, or achievements.\n"
        f"4. Sign the cover letter as {name}."
    )

    try:
        raw_output = _call_ai(
            client, provider, model, combined_system, combined_user,
            max_tokens=_MAX_COMBINED_OUTPUT_TOKENS,
        )
        parsed = _parse_tailored_output(raw_output)
        if parsed:
            logger.info("tailor_application source=ai job=%s @ %s", title, company)
            return parsed
        logger.warning("tailor_application parse_failed for %s @ %s — falling back", title, company)
    except Exception as exc:
        logger.error("AI tailoring failed: %s — falling back", exc)

    return _keyword_fallback(cv_text, job)
