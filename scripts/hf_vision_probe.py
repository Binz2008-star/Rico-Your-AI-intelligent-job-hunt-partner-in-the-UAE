"""
scripts/hf_vision_probe.py  —  THROWAWAY one-shot diagnostic for PR #736.

Sends ONE tiny self-generated screenshot through the exact production decision
path (HF vision-language model first, then the serverless hf-inference OCR
fallback) using the repo's HF_TOKEN, and prints a STATUS-ONLY report.

Privacy / cost rules (match the PR's guards):
  * Never prints HF_TOKEN (or its length) and never prints raw image bytes,
    base64, or the transcribed text — only status codes, model ids, booleans,
    sizes, and the re-classified document_type.
  * One image, one attempt per endpoint — no batch, no retries, no retry storm.
  * Hard per-request timeout; quota / billing / provider-disabled responses are
    treated as EXPECTED (the script still exits 0) so they read as graceful
    fallback, not failure.

Not wired into the app and not on the PR branch; safe to delete with the branch.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys

import requests

_CHAT = "https://router.huggingface.co/v1/chat/completions"
_SERVERLESS = "https://router.huggingface.co/hf-inference/models/"
# `or default` also covers the set-but-empty case (an unset repo var renders as "").
_VLM_MODEL = os.getenv("HF_VISION_MODEL", "").strip() or "Qwen/Qwen2.5-VL-7B-Instruct"
_OCR_MODEL = os.getenv("HF_OCR_MODEL", "").strip() or "microsoft/trocr-base-printed"
_TIMEOUT = 35


def _tiny_job_screenshot() -> bytes:
    """A few-KB PNG that looks like a one-line job posting (synthetic, no PII)."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (760, 90), "white")
    draw = ImageDraw.Draw(img)
    draw.text(
        (12, 34),
        "Senior Product Manager at Acme - Dubai, UAE. Apply now. Posted 2025.",
        fill="black",
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _safe_err(resp: requests.Response) -> str:
    """A short, token-free snippet of an error body (explains provider/quota)."""
    try:
        return json.dumps(resp.json())[:300]
    except Exception:
        return (resp.text or "")[:300]


def main() -> int:
    token = os.getenv("HF_TOKEN", "").strip()
    if not token:
        print("HF_TOKEN: NOT SET in this repo's Actions secrets — cannot probe")
        return 1
    # Presence only — never the value or length.
    print("HF_TOKEN: present (value masked)")

    data = _tiny_job_screenshot()
    print(f"probe_image: {len(data)} bytes, image/png (synthetic, single line)")
    print("-" * 48)

    # ── 1) Vision-language model via the Inference Providers chat endpoint ──
    vlm_text = None
    vlm_status = None
    vlm_provider = "n/a"
    b64 = base64.b64encode(data).decode("ascii")
    payload = {
        "model": _VLM_MODEL,
        "max_tokens": 256,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Transcribe all visible text."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            }
        ],
    }
    try:
        r = requests.post(
            _CHAT,
            json=payload,
            headers={"Authorization": "Bearer " + token},
            timeout=_TIMEOUT,
        )
        vlm_status = r.status_code
        print(f"VLM status: {vlm_status}  model={_VLM_MODEL}")
        if vlm_status == 200:
            body = r.json()
            vlm_provider = body.get("provider") or body.get("model") or "n/a"
            content = (body.get("choices") or [{}])[0].get("message", {}).get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    p.get("text", "") for p in content if isinstance(p, dict)
                )
            vlm_text = (content or "").strip() or None
            print(f"VLM provider: {vlm_provider}")
        else:
            print(f"VLM not-200 (expected on a free account with no provider enabled): {_safe_err(r)}")
    except Exception as exc:
        print(f"VLM exception: {type(exc).__name__}")

    print("-" * 48)

    # ── 2) Serverless hf-inference OCR fallback (token only, no provider) ──
    ocr_text = None
    ocr_status = None
    try:
        r = requests.post(
            _SERVERLESS + _OCR_MODEL,
            data=data,
            headers={"Authorization": "Bearer " + token, "Content-Type": "image/png"},
            timeout=_TIMEOUT,
        )
        ocr_status = r.status_code
        print(f"OCR status: {ocr_status}  model={_OCR_MODEL}")
        if ocr_status == 200:
            body = r.json()
            item = body[0] if isinstance(body, list) and body else body
            ocr_text = (
                item.get("generated_text", "").strip() if isinstance(item, dict) else ""
            ) or None
        else:
            print(f"OCR not-200 (model warming / quota / unavailable): {_safe_err(r)}")
    except Exception as exc:
        print(f"OCR exception: {type(exc).__name__}")

    # ── Report (status only — never the transcribed text) ──
    final = vlm_text or ocr_text
    path = "VLM" if vlm_text else ("serverless-OCR" if ocr_text else "none")
    print("=" * 48)
    print("REPORT")
    print(f"  vlm_status            : {vlm_status}")
    print(f"  vlm_provider          : {vlm_provider}")
    print(f"  ocr_status            : {ocr_status}")
    print(f"  text_extracted        : {bool(final)} (via {path})")
    print(f"  extracted_char_count  : {len(final or '')}")
    if final:
        try:
            sys.path.insert(0, os.getcwd())
            from src.services.document_classifier import classify_document

            cls = classify_document(final.encode("utf-8"), "image-text.txt")
            print(f"  reclassified_as       : {cls.document_type} (was 'image')")
        except Exception as exc:
            print(f"  reclassify_error      : {type(exc).__name__}")
    print(
        "  graceful_fallback     : extract_text_from_image returns None on "
        "quota/provider error -> upload falls back to format-only image (no crash)"
    )
    # Quota/provider errors are expected, not workflow failures.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
