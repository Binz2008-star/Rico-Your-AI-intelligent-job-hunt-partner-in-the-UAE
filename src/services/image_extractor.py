"""
src/services/image_extractor.py
Vision-model image → text extraction for Rico (CAREER-OS-06 extension).

Reads the text content of an uploaded image (a job-posting screenshot, a
recruiter-message screenshot, or a photographed career document) so Rico can
understand it instead of only recognising "this is an image".

Uses the Hugging Face Inference Router's OpenAI-compatible chat-completions
endpoint with a vision-language model — the SAME host + token as
``src/rico_hf_client.py``, so there is no OpenAI dependency. Never raises:
returns ``None`` on any failure (missing token, model unavailable, timeout,
oversized image, empty result), so callers degrade gracefully to the existing
format-only image response.

Environment:
  HF_API_TOKEN / HF_TOKEN / HF_API_KEY / HUGGINGFACE_API_KEY  -- token (any of)
  HF_VISION_MODEL  -- vision-language model id
                      (default: Qwen/Qwen2.5-VL-7B-Instruct)
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_HF_ROUTER_CHAT = "https://router.huggingface.co/v1/chat/completions"
_DEFAULT_VISION_MODEL = "Qwen/Qwen2.5-VL-7B-Instruct"
_REQUEST_TIMEOUT = 35
# Screenshots are far smaller than this; the cap just guards the base64 payload.
_MAX_IMAGE_BYTES = 6 * 1024 * 1024

_PROMPT = (
    "You are reading an image a job-seeker uploaded. It is usually a screenshot of "
    "a job posting, a recruiter message, or a career document. Transcribe ALL "
    "visible text exactly as it appears — job title, company, location, status, "
    "dates, salary, responsibilities, and notices such as 'no longer available'. "
    "Output only the transcribed text, with no commentary. If there is no readable "
    "text, output nothing."
)

_MIME_BY_MAGIC: list[tuple[bytes, str]] = [
    (b"\x89PNG", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF8", "image/gif"),
    (b"BM", "image/bmp"),
]


def _token() -> str:
    return (
        os.getenv("HF_API_TOKEN", "").strip()
        or os.getenv("HF_TOKEN", "").strip()
        or os.getenv("HF_API_KEY", "").strip()
        or os.getenv("HUGGINGFACE_API_KEY", "").strip()
    )


def _mime(data: bytes) -> str:
    head = data[:12]
    if len(data) >= 12 and head[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    for magic, mime in _MIME_BY_MAGIC:
        if head[: len(magic)] == magic:
            return mime
    return "image/png"


def is_available() -> bool:
    """True when an HF token is configured (a vision model can be called)."""
    return bool(_token())


def extract_text_from_image(data: bytes, filename: str = "") -> Optional[str]:
    """Return text read from an image via the HF vision model, or ``None``.

    Never raises. Returns ``None`` when no token is configured, the image is
    empty or oversized, the model is unavailable/rate-limited, or the response
    carries no usable text — so the caller falls back to the format-only path.
    """
    token = _token()
    if not token:
        logger.debug("image_extract: no HF token configured")
        return None
    if not data or len(data) > _MAX_IMAGE_BYTES:
        logger.debug("image_extract: empty or oversized image bytes=%d", len(data or b""))
        return None

    model = os.getenv("HF_VISION_MODEL", _DEFAULT_VISION_MODEL)
    b64 = base64.b64encode(data).decode("ascii")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{_mime(data)};base64,{b64}"},
                    },
                ],
            }
        ],
        "max_tokens": 800,
        "temperature": 0,
    }

    try:
        resp = requests.post(
            _HF_ROUTER_CHAT,
            json=payload,
            headers={"Authorization": "Bearer " + token},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.debug("image_extract: non_ok status=%s model=%s", resp.status_code, model)
            return None
        body = resp.json()
        content = (
            (body.get("choices") or [{}])[0].get("message", {}).get("content", "")
        )
        # Some providers return content as a list of typed parts rather than a string.
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict)
            )
        text = (content or "").strip()
        return text or None
    except Exception as exc:  # network error, JSON error, shape mismatch — all soft
        logger.debug("image_extract: error=%s model=%s", exc, model)
        return None
