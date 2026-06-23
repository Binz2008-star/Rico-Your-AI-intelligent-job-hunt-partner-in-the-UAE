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


def test_disabled_via_env_kill_switch(monkeypatch):
    # RICO_ENABLE_VISION=false → no network call at all, graceful None, even with
    # a token present. The instant, no-deploy off switch (cost guard).
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    monkeypatch.setenv("RICO_ENABLE_VISION", "false")
    assert ie.is_available() is False
    with patch("src.services.image_extractor.requests.post") as post:
        assert ie.extract_text_from_image(_PNG, "x.png") is None
    assert post.call_count == 0


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


def test_serverless_ocr_fallback_when_vlm_unavailable(monkeypatch):
    # Free account with no Inference Provider enabled → VLM 400 → serverless OCR.
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    vlm = MagicMock(status_code=400)  # "model not supported by any provider you have enabled"
    ocr = MagicMock(status_code=200)
    ocr.json.return_value = [{"generated_text": "  Crypto.com Product Design Manager Dubai  "}]
    with patch("src.services.image_extractor.requests.post", side_effect=[vlm, ocr]) as post:
        out = ie.extract_text_from_image(_PNG, "job.png")

    assert out == "Crypto.com Product Design Manager Dubai"
    assert post.call_count == 2
    # Second call is the serverless hf-inference endpoint with the raw image bytes.
    second = post.call_args_list[1]
    assert "hf-inference/models/" in second.args[0]
    assert second.kwargs["data"] == _PNG
    assert second.kwargs["headers"]["Content-Type"] == "image/png"


def test_serverless_ocr_accepts_bare_dict_shape(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    vlm = MagicMock(status_code=503)
    ocr = MagicMock(status_code=200)
    ocr.json.return_value = {"generated_text": "Hello OCR"}
    with patch("src.services.image_extractor.requests.post", side_effect=[vlm, ocr]):
        assert ie.extract_text_from_image(_PNG, "x.png") == "Hello OCR"


def test_serverless_ocr_empty_returns_none(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    vlm = MagicMock(status_code=400)
    ocr = MagicMock(status_code=200)
    ocr.json.return_value = [{"generated_text": "   "}]
    with patch("src.services.image_extractor.requests.post", side_effect=[vlm, ocr]):
        assert ie.extract_text_from_image(_PNG, "x.png") is None


def test_serverless_ocr_disabled_when_model_blank(monkeypatch):
    # Operator can pin HF_OCR_MODEL="" to disable the OCR fallback entirely.
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    monkeypatch.setenv("HF_OCR_MODEL", "")
    vlm = MagicMock(status_code=400)
    with patch("src.services.image_extractor.requests.post", side_effect=[vlm]) as post:
        assert ie.extract_text_from_image(_PNG, "x.png") is None
    assert post.call_count == 1  # only the VLM attempt, no serverless call
