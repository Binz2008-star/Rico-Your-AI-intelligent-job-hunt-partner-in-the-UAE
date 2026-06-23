"""
src/services/image_extractor.py
Image -> text extraction for Rico (CAREER-OS-06 extension).

Reads the text content of an uploaded image (a job-posting screenshot, a
recruiter-message screenshot, or a photographed career document) so Rico can
understand it instead of only recognising "this is an image".

Free + zero-dependency by design. Render runs Rico on the *native* python
runtime (no apt, ~512MB), so a local OCR engine is not an option: Tesseract
needs a system binary and RapidOCR/onnxruntime needs ``libGL`` — neither is
installable there. Instead this calls Hugging Face (the SAME host + token as
``src/rico_hf_client.py``, so there is no OpenAI dependency and no extra pip
package), trying two free mechanisms in order:

  1. A vision-language model via the HF Inference Router's OpenAI-compatible
     chat endpoint (``HF_VISION_MODEL``). Best quality. Active once a (free)
     Inference Provider is enabled on the HF account.
  2. A serverless ``hf-inference`` image-to-text/OCR model (``HF_OCR_MODEL``).
     Works with no provider enabled, so it covers the zero-config case.

Never raises: returns ``None`` on any failure (missing token, model
unavailable, timeout, oversized image, empty result), so callers degrade
gracefully to the existing format-only image response.

Environment:
  HF_API_TOKEN / HF_TOKEN / HF_API_KEY / HUGGINGFACE_API_KEY  -- token (any of)
  HF_VISION_MODEL  -- vision-language model id for the chat endpoint
                      (default: Qwen/Qwen2.5-VL-7B-Instruct)
  HF_OCR_MODEL     -- serverless image-to-text model id
                      (default: microsoft/trocr-base-printed)
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_HF_ROUTER_CHAT = "https://router.huggingface.co/v1/chat/completions"
_HF_ROUTER_SERVERLESS = "https://router.huggingface.co/hf-inference/models/"
_DEFAULT_VISION_MODEL = "Qwen/Qwen2.5-VL-7B-Instruct"
_DEFAULT_OCR_MODEL = "microsoft/trocr-base-printed"
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
    """True when an HF token is configured (a model can be called)."""
    return bool(_token())


def _extract_via_vlm(data: bytes, token: str, mime: str) -> Optional[str]:
    """Best-quality path: a vision-language model via the chat endpoint.

    Returns ``None`` (not an error) when no Inference Provider is enabled for
    the account — that is the common free-tier case — so the caller falls
    through to the serverless OCR path.
    """
    model = os.getenv("HF_VISION_MODEL", _DEFAULT_VISION_MODEL).strip()
    if not model:
        return None
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
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
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
            logger.debug("image_extract.vlm: non_ok status=%s model=%s", resp.status_code, model)
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
        logger.debug("image_extract.vlm: error=%s model=%s", exc, model)
        return None


def _extract_via_serverless_ocr(data: bytes, token: str, mime: str) -> Optional[str]:
    """Zero-config free path: a serverless ``hf-inference`` image-to-text model.

    Works without enabling an Inference Provider, so it covers HF accounts that
    have only a token. Posts the raw image bytes (the HF image-task contract)
    and reads the ``generated_text`` field. Returns ``None`` on any failure.
    """
    model = os.getenv("HF_OCR_MODEL", _DEFAULT_OCR_MODEL).strip()
    if not model:
        return None
    try:
        resp = requests.post(
            _HF_ROUTER_SERVERLESS + model,
            data=data,
            headers={"Authorization": "Bearer " + token, "Content-Type": mime},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.debug("image_extract.ocr: non_ok status=%s model=%s", resp.status_code, model)
            return None
        body = resp.json()
        # image-to-text → [{"generated_text": "..."}]; tolerate a bare dict too.
        item = body[0] if isinstance(body, list) and body else body
        text = (item.get("generated_text", "") if isinstance(item, dict) else "").strip()
        return text or None
    except Exception as exc:  # network error, JSON error, shape mismatch — all soft
        logger.debug("image_extract.ocr: error=%s model=%s", exc, model)
        return None


def extract_text_from_image(data: bytes, filename: str = "") -> Optional[str]:
    """Return text read from an image via a free HF model, or ``None``.

    Tries the vision-language model first (best quality) and falls back to a
    serverless OCR model (works with no Inference Provider enabled). Never
    raises. Returns ``None`` when no token is configured, the image is empty or
    oversized, or no path yields usable text — so the caller falls back to the
    format-only image response.
    """
    token = _token()
    if not token:
        logger.debug("image_extract: no HF token configured")
        return None
    if not data or len(data) > _MAX_IMAGE_BYTES:
        logger.debug("image_extract: empty or oversized image bytes=%d", len(data or b""))
        return None

    mime = _mime(data)
    text = _extract_via_vlm(data, token, mime)
    if text:
        return text
    return _extract_via_serverless_ocr(data, token, mime)
