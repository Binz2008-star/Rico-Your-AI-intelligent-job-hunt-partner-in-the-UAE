"""
src/rico_apply_ai.py
AI engine for per-job CV tailoring and cover letter generation.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

_MAX_CV_CHARS = 6000
_MAX_JD_CHARS = 3000


def _get_ai_client():
    try:
        from src.rico_openai_runtime import _build_client, _primary_model_for
        from src.rico_env import get_ai_provider
        provider = get_ai_provider()
        key_present = bool(os.getenv("DEEPSEEK_API_KEY")) if provider == "deepseek" else bool(os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_API"))
        if not key_present:
            return None, None, None
        model, _ = _primary_model_for(provider)
        client = _build_client(provider)
        return client, provider, model
    except Exception as exc:
        logger.warning("AI client unavailable for apply: %s", exc)
        return None, None, None


def _call_ai(client, provider: str, model: str, system: str, user: str) -> str:
    if provider == "openai":
        resp = client.responses.create(
            model=model,
            input=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_output_tokens=2000,
        )
        for item in getattr(resp, "output", []):
            for block in getattr(item, "content", []):
                if getattr(block, "type", "") == "output_text":
                    return block.text.strip()
        return str(resp)
    else:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=2000,
            temperature=0.4,
        )
        return resp.choices[0].message.content.strip()


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

    cv_system = (
        "You are an expert UAE resume writer. Rewrite the candidate's CV to maximise keyword "
        "alignment with the target job description. Rules:\n"
        "1. Keep all factual content true — never invent experience or dates.\n"
        "2. Mirror keywords and phrases from the job description naturally.\n"
        "3. Reorder bullet points to lead with the most relevant achievements.\n"
        "4. Keep the same section structure (Summary, Experience, Education, Skills).\n"
        "5. Output only the full rewritten CV text — no preamble, no markdown fences."
    )
    cv_user = (
        f"Target role: {title} at {company} ({location})\n\n"
        f"Job description:\n{description}\n\n"
        f"Candidate's current CV:\n{truncated_cv}"
    )
    cl_system = (
        "You are an expert UAE job application writer. Write a concise, compelling cover letter "
        "(3 short paragraphs, max 250 words). Rules:\n"
        "1. Opening: state the role and why this company specifically.\n"
        "2. Middle: 2-3 specific achievements from the CV that directly match the job requirements.\n"
        "3. Closing: call to action. Sign off as the candidate.\n"
        "4. Do not use generic filler phrases like 'I am a hard worker'.\n"
        "5. Output only the cover letter — no subject line, no preamble."
    )
    cl_user = (
        f"Candidate name: {name}\n"
        f"Target role: {title} at {company} ({location})\n"
        f"Target roles profile: {target_roles}\n\n"
        f"Job description:\n{description}\n\n"
        f"Candidate CV summary:\n{truncated_cv[:2000]}"
    )

    try:
        tailored_cv = _call_ai(client, provider, model, cv_system, cv_user)
        cover_letter = _call_ai(client, provider, model, cl_system, cl_user)
        return {"tailored_cv": tailored_cv, "cover_letter": cover_letter}
    except Exception as exc:
        logger.error("AI tailoring failed: %s — falling back", exc)
        return _keyword_fallback(cv_text, job)
