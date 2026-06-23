"""
tests/unit/test_image_extractor.py

Free image→text extractor: a vision-language model via an OpenAI-compatible chat
endpoint (OpenRouter preferred, else HF Inference Router) with an OCR.space free
fallback. Mocks the HTTP call — no live request, no quota burn. Verifies the
extractor is graceful (returns None) on every failure mode so the upload pipeline
degrades cleanly, and that provider selection / request shape are correct.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.services import image_extractor as ie

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

_ALL_KEYS = (
    "OPENROUTER_API_KEY", "OPENROUTER_VISION_MODEL",
    "HF_API_TOKEN", "HF_TOKEN", "HF_API_KEY", "HUGGINGFACE_API_KEY",
    "HF_VISION_MODEL", "OCRSPACE_API_KEY",
)


def _clear_keys(monkeypatch):
    for k in _ALL_KEYS:
        monkeypatch.delenv(k, raising=False)


def _vlm_ok(text: str) -> MagicMock:
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"choices": [{"message": {"content": text}}]}
    return resp


def _ocrspace_ok(text: str) -> MagicMock:
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"IsErroredOnProcessing": False, "ParsedResults": [{"ParsedText": text}]}
    return resp


# ── Availability / guards ─────────────────────────────────────────────────────

def test_no_provider_returns_none(monkeypatch):
    _clear_keys(monkeypatch)
    assert ie.is_available() is False
    assert ie.extract_text_from_image(_PNG, "x.png") is None


def test_is_available_true_for_any_key(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("OCRSPACE_API_KEY", "ocr_test")
    assert ie.is_available() is True


def test_empty_and_oversized_return_none(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    assert ie.extract_text_from_image(b"", "x.png") is None
    big = b"\x89PNG" + b"\x00" * (ie._MAX_IMAGE_BYTES + 1)
    assert ie.extract_text_from_image(big, "x.png") is None


# ── VLM via HF ────────────────────────────────────────────────────────────────

def test_hf_vlm_success(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    with patch("src.services.image_extractor.requests.post", return_value=_vlm_ok("  Crypto.com — PM  ")) as post:
        out = ie.extract_text_from_image(_PNG, "job.png")
    assert out == "Crypto.com — PM"
    args, kwargs = post.call_args
    assert "router.huggingface.co/v1/chat/completions" in args[0]
    assert kwargs["headers"]["Authorization"] == "Bearer hf_test"
    assert kwargs["json"]["model"] == ie._DEFAULT_HF_VISION_MODEL
    content = kwargs["json"]["messages"][0]["content"]
    assert content[-1]["image_url"]["url"].startswith("data:image/png;base64,")


# ── VLM via OpenRouter (preferred when keyed) ─────────────────────────────────

def test_openrouter_preferred_over_hf(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or_test")
    monkeypatch.setenv("HF_TOKEN", "hf_test")  # present but OpenRouter wins
    with patch("src.services.image_extractor.requests.post", return_value=_vlm_ok("Hello")) as post:
        out = ie.extract_text_from_image(_PNG, "job.png")
    assert out == "Hello"
    args, kwargs = post.call_args
    assert "openrouter.ai/api/v1/chat/completions" in args[0]
    assert kwargs["headers"]["Authorization"] == "Bearer or_test"
    assert kwargs["json"]["model"] == ie._DEFAULT_OPENROUTER_VISION_MODEL


def test_openrouter_custom_model(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or_test")
    monkeypatch.setenv("OPENROUTER_VISION_MODEL", "qwen/qwen2.5-vl-72b-instruct:free")
    with patch("src.services.image_extractor.requests.post", return_value=_vlm_ok("x text here")) as post:
        ie.extract_text_from_image(_PNG, "job.png")
    assert post.call_args.kwargs["json"]["model"] == "qwen/qwen2.5-vl-72b-instruct:free"


def test_vlm_content_returned_as_parts_list(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"choices": [{"message": {"content": [
        {"type": "text", "text": "Hello"}, {"type": "text", "text": "World"},
    ]}}]}
    with patch("src.services.image_extractor.requests.post", return_value=resp):
        assert ie.extract_text_from_image(_PNG, "x.png") == "Hello World"


def test_vlm_non200_no_fallback_returns_none(monkeypatch):
    """VLM fails and no OCR key set → None (graceful)."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    with patch("src.services.image_extractor.requests.post", return_value=MagicMock(status_code=503)):
        assert ie.extract_text_from_image(_PNG, "x.png") is None
    with patch("src.services.image_extractor.requests.post", side_effect=Exception("network down")):
        assert ie.extract_text_from_image(_PNG, "x.png") is None


# ── OCR.space fallback ────────────────────────────────────────────────────────

def test_vlm_unavailable_falls_back_to_ocrspace(monkeypatch):
    """VLM 400 (model/provider not enabled) → OCR.space fallback succeeds."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    monkeypatch.setenv("OCRSPACE_API_KEY", "ocr_test")
    vlm = MagicMock(status_code=400)
    ocr = _ocrspace_ok("  Crypto.com Product Design Manager Dubai  ")
    with patch("src.services.image_extractor.requests.post", side_effect=[vlm, ocr]) as post:
        out = ie.extract_text_from_image(_PNG, "job.png")
    assert out == "Crypto.com Product Design Manager Dubai"
    assert post.call_count == 2
    second = post.call_args_list[1]
    assert "api.ocr.space/parse/image" in second.args[0]
    assert second.kwargs["headers"]["apikey"] == "ocr_test"
    assert second.kwargs["data"]["base64Image"].startswith("data:image/png;base64,")


def test_ocrspace_only_no_vlm(monkeypatch):
    """No VLM key, only OCR.space → goes straight to OCR.space."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("OCRSPACE_API_KEY", "ocr_test")
    with patch("src.services.image_extractor.requests.post", return_value=_ocrspace_ok("Hello OCR")) as post:
        assert ie.extract_text_from_image(_PNG, "x.png") == "Hello OCR"
    assert post.call_count == 1
    assert "api.ocr.space" in post.call_args.args[0]


def test_ocrspace_provider_error_returns_none(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("OCRSPACE_API_KEY", "ocr_test")
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"IsErroredOnProcessing": True, "ErrorMessage": ["bad"]}
    with patch("src.services.image_extractor.requests.post", return_value=resp):
        assert ie.extract_text_from_image(_PNG, "x.png") is None


def test_ocrspace_empty_returns_none(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("OCRSPACE_API_KEY", "ocr_test")
    with patch("src.services.image_extractor.requests.post", return_value=_ocrspace_ok("   ")):
        assert ie.extract_text_from_image(_PNG, "x.png") is None


# ── MIME detection ────────────────────────────────────────────────────────────

def test_mime_detection():
    assert ie._mime(b"\x89PNG\r\n\x1a\n") == "image/png"
    assert ie._mime(b"\xff\xd8\xff\xe0") == "image/jpeg"
    assert ie._mime(b"GIF89a") == "image/gif"
    assert ie._mime(b"BM\x00\x00") == "image/bmp"
    assert ie._mime(b"RIFF\x00\x00\x00\x00WEBP") == "image/webp"
