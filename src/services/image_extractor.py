"""
src/services/image_extractor.py
Image -> text extraction for Rico (CAREER-OS-06 extension).

Reads the text content of an uploaded image (a job-posting screenshot, a
recruiter-message screenshot, or a photographed career document) so Rico can
understand it instead of only recognising "this is an image".

Free + zero-dependency by design. Render runs Rico on the *native* python
runtime (no apt, ~512MB), so a local OCR engine is not an option: Tesseract
needs a system binary and RapidOCR/onnxruntime needs ``libGL`` — neither is
installable there. Instead this calls free HTTP services (no extra pip package),
trying two free mechanisms in order:

  1. A vision-language model via an OpenAI-compatible chat endpoint. Best quality
     (reads OCR + layout + meaning in one call, handles "no longer available").
     Uses OpenRouter when ``OPENROUTER_API_KEY`` is set (free ``:free`` vision
     models), otherwise the Hugging Face Inference Router with ``HF_TOKEN``.
  2. OCR.space (``OCRSPACE_API_KEY``) — a free hosted OCR API. Pure HTTP, works
     with just a free key, so it covers accounts with no chat-VLM provider.

Never raises: returns ``None`` on any failure (no key, model unavailable,
timeout, oversized image, empty result), so callers degrade gracefully to the
existing format-only image response.

Environment:
  OPENROUTER_API_KEY       -- OpenRouter key; enables the free OpenRouter VLM path
  OPENROUTER_VISION_MODEL  -- vision model id
                              (default: meta-llama/llama-3.2-11b-vision-instruct:free)
  HF_API_TOKEN / HF_TOKEN / HF_API_KEY / HUGGINGFACE_API_KEY -- HF token (any of)
  HF_VISION_MODEL          -- HF vision model id
                              (default: Qwen/Qwen2.5-VL-7B-Instruct)
  OCRSPACE_API_KEY         -- OCR.space key; enables the free OCR fallback
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_HF_ROUTER_CHAT = "https://router.huggingface.co/v1/chat/completions"
_OPENROUTER_CHAT = "https://openrouter.ai/api/v1/chat/completions"
_OCRSPACE_URL = "https://api.ocr.space/parse/image"

_DEFAULT_HF_VISION_MODEL = "Qwen/Qwen2.5-VL-7B-Instruct"
_DEFAULT_OPENROUTER_VISION_MODEL = "meta-llama/llama-3.2-11b-vision-instruct:free"

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


def _env(*names: str) -> str:
    for name in names:
        val = os.getenv(name, "").strip()
        if val:
            return val
    return ""


def _hf_token() -> str:
    return _env("HF_API_TOKEN", "HF_TOKEN", "HF_API_KEY", "HUGGINGFACE_API_KEY")


def _openrouter_key() -> str:
    return _env("OPENROUTER_API_KEY")


def _ocrspace_key() -> str:
    return _env("OCRSPACE_API_KEY")


def _mime(data: bytes) -> str:
    head = data[:12]
    if len(data) >= 12 and head[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    for magic, mime in _MIME_BY_MAGIC:
        if head[: len(magic)] == magic:
            return mime
    return "image/png"


def is_available() -> bool:
    """True when any vision/OCR provider is configured (a model can be called)."""
    return bool(_openrouter_key() or _hf_token() or _ocrspace_key())


def _vlm_route() -> Optional[tuple[str, str, str]]:
    """Resolve the chat-VLM endpoint as (url, token, model).

    Prefers OpenRouter (free ``:free`` vision models) when its key is set,
    otherwise the HF Inference Router. ``None`` when neither is configured.
    """
    or_key = _openrouter_key()
    if or_key:
        model = (
            os.getenv("OPENROUTER_VISION_MODEL", _DEFAULT_OPENROUTER_VISION_MODEL).strip()
            or _DEFAULT_OPENROUTER_VISION_MODEL
        )
        return (_OPENROUTER_CHAT, or_key, model)
    hf = _hf_token()
    if hf:
        model = (
            os.getenv("HF_VISION_MODEL", _DEFAULT_HF_VISION_MODEL).strip()
            or _DEFAULT_HF_VISION_MODEL
        )
        return (_HF_ROUTER_CHAT, hf, model)
    return None


def _extract_via_chat(url: str, token: str, model: str, data: bytes, mime: str) -> Optional[str]:
    """Best-quality path: a vision-language model via an OpenAI-compatible chat
    endpoint (OpenRouter or HF). Returns ``None`` (not an error) on any failure —
    e.g. the model is not enabled for the account — so the caller falls through
    to the OCR path."""
    b64 = base64.b64encode(data).decode("ascii")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        ],
        "max_tokens": 800,
        "temperature": 0,
    }
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"Authorization": "Bearer " + token},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.debug("image_extract.vlm: non_ok status=%s model=%s", resp.status_code, model)
            return None
        body = resp.json()
        content = (body.get("choices") or [{}])[0].get("message", {}).get("content", "")
        # Some providers return content as a list of typed parts rather than a string.
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        text = (content or "").strip()
        return text or None
    except Exception as exc:  # network error, JSON error, shape mismatch — all soft
        logger.debug("image_extract.vlm: error=%s model=%s", exc, model)
        return None


def _extract_via_ocrspace(data: bytes, mime: str) -> Optional[str]:
    """Free OCR fallback via OCR.space. Pure HTTP, works with only a free key.

    Posts the image as a base64 data-URI and joins the parsed text regions.
    Returns ``None`` on any failure (no key, provider error, empty result).
    """
    key = _ocrspace_key()
    if not key:
        return None
    b64 = base64.b64encode(data).decode("ascii")
    try:
        resp = requests.post(
            _OCRSPACE_URL,
            data={
                "base64Image": f"data:{mime};base64,{b64}",
                "OCREngine": "2",
                "scale": "true",
                "isOverlayRequired": "false",
            },
            headers={"apikey": key},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.debug("image_extract.ocrspace: non_ok status=%s", resp.status_code)
            return None
        body = resp.json()
        if isinstance(body, dict) and body.get("IsErroredOnProcessing"):
            logger.debug("image_extract.ocrspace: provider_error")
            return None
        results = (body.get("ParsedResults") if isinstance(body, dict) else None) or []
        text = " ".join(
            (r.get("ParsedText") or "").strip() for r in results if isinstance(r, dict)
        ).strip()
        return text or None
    except Exception as exc:  # network error, JSON error, shape mismatch — all soft
        logger.debug("image_extract.ocrspace: error=%s", exc)
        return None


def extract_text_from_image(data: bytes, filename: str = "") -> Optional[str]:
    """Return text read from an image via a free model/OCR, or ``None``.

    Tries a vision-language model first (OpenRouter or HF, best quality) and falls
    back to OCR.space (free hosted OCR). Never raises. Returns ``None`` when no
    provider is configured, the image is empty or oversized, or no path yields
    usable text — so the caller falls back to the format-only image response.
    """
    if not is_available():
        logger.debug("image_extract: no vision/OCR provider configured")
        return None
    if not data or len(data) > _MAX_IMAGE_BYTES:
        logger.debug("image_extract: empty or oversized image bytes=%d", len(data or b""))
        return None

    mime = _mime(data)
    route = _vlm_route()
    if route is not None:
        text = _extract_via_chat(route[0], route[1], route[2], data, mime)
        if text:
            return text
    return _extract_via_ocrspace(data, mime)
