"""
tests/unit/test_image_extractor.py

Vision-model image→text extractor (HF Inference Router). Mocks the HTTP call —
no live vision request, no quota burn. Verifies the extractor is graceful
(returns None) on every failure mode so the upload pipeline degrades cleanly.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.services import image_extractor as ie

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _clear_tokens(monkeypatch):
    for k in ("HF_API_TOKEN", "HF_TOKEN", "HF_API_KEY", "HUGGINGFACE_API_KEY"):
        monkeypatch.delenv(k, raising=False)


def test_no_token_returns_none(monkeypatch):
    _clear_tokens(monkeypatch)
    assert ie.is_available() is False
    assert ie.extract_text_from_image(_PNG, "x.png") is None


def test_empty_and_oversized_return_none(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    assert ie.extract_text_from_image(b"", "x.png") is None
    big = b"\x89PNG" + b"\x00" * (ie._MAX_IMAGE_BYTES + 1)
    assert ie.extract_text_from_image(big, "x.png") is None


def test_successful_extraction(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "choices": [{"message": {"content": "  Crypto.com — Product Design Manager  "}}]
    }
    with patch("src.services.image_extractor.requests.post", return_value=resp) as post:
        out = ie.extract_text_from_image(_PNG, "job.png")

    assert out == "Crypto.com — Product Design Manager"
    args, kwargs = post.call_args
    assert "router.huggingface.co/v1/chat/completions" in args[0]
    assert kwargs["headers"]["Authorization"] == "Bearer hf_test"
    assert kwargs["json"]["model"]  # a vision model id is sent
    content = kwargs["json"]["messages"][0]["content"]
    assert any(p.get("type") == "image_url" for p in content)
    assert content[-1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_non_200_and_exception_return_none(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    with patch("src.services.image_extractor.requests.post",
               return_value=MagicMock(status_code=503)):
        assert ie.extract_text_from_image(_PNG, "x.png") is None
    with patch("src.services.image_extractor.requests.post",
               side_effect=Exception("network down")):
        assert ie.extract_text_from_image(_PNG, "x.png") is None


def test_empty_content_returns_none(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"choices": [{"message": {"content": "   "}}]}
    with patch("src.services.image_extractor.requests.post", return_value=resp):
        assert ie.extract_text_from_image(_PNG, "x.png") is None


def test_content_returned_as_parts_list(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "choices": [{"message": {"content": [
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "World"},
        ]}}]
    }
    with patch("src.services.image_extractor.requests.post", return_value=resp):
        assert ie.extract_text_from_image(_PNG, "x.png") == "Hello World"


def test_mime_detection():
    assert ie._mime(b"\x89PNG\r\n\x1a\n") == "image/png"
    assert ie._mime(b"\xff\xd8\xff\xe0") == "image/jpeg"
    assert ie._mime(b"GIF89a") == "image/gif"
    assert ie._mime(b"BM\x00\x00") == "image/bmp"
    assert ie._mime(b"RIFF\x00\x00\x00\x00WEBP") == "image/webp"
