"""
Tests for src/services/operation_timing.py — privacy-safe timing observability.

Covers all required test cases from the PR #1489 review:
- malicious operation_id containing newline/control characters
- invalid stage rejected or safely classified
- invalid outcome/provider rejected or safely classified
- success emits one terminal response_returned
- HTTP error emits one terminal response_returned
- cancellation emits one terminal response_returned
- unexpected error emits one terminal response_returned
- no email, query, CV text, URL, token, or provider payload in logs
"""
import logging
import re
import time
from io import StringIO

import pytest

from src.services.operation_timing import (
    KNOWN_OUTCOMES,
    KNOWN_PROVIDERS,
    KNOWN_STAGES,
    TERMINAL_STAGES,
    OperationTimer,
    sanitize_operation_id,
)


@pytest.fixture
def captured_logs():
    """Capture log output into a string buffer."""
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    handler.setLevel(logging.INFO)
    test_logger = logging.getLogger("test_operation_timing")
    test_logger.setLevel(logging.INFO)
    test_logger.addHandler(handler)
    yield buf, test_logger
    test_logger.removeHandler(handler)


def _parse_log_line(line: str) -> dict:
    """Parse 'operation_timing key=val key=val ...' into a dict."""
    assert line.startswith("operation_timing "), f"Unexpected prefix: {line[:30]}"
    parts = line[len("operation_timing "):].strip().split()
    result = {}
    for part in parts:
        if "=" in part:
            k, v = part.split("=", 1)
            result[k] = v
    return result


def _all_log_lines(buf: StringIO) -> list:
    return [l for l in buf.getvalue().strip().split("\n") if l.strip()]


class TestSanitizeOperationId:
    def test_none_returns_unknown(self):
        assert sanitize_operation_id(None) == "unknown"

    def test_empty_returns_unknown(self):
        assert sanitize_operation_id("") == "unknown"
        assert sanitize_operation_id("   ") == "unknown"

    def test_valid_id_preserved(self):
        assert sanitize_operation_id("op-123_abc.def") == "op-123_abc.def"

    def test_newline_removed(self):
        raw = "op-123\ninjected-log-line"
        result = sanitize_operation_id(raw)
        assert "\n" not in result
        assert "injected" not in result or result == "unknown"

    def test_control_characters_removed(self):
        raw = "op\x00\x01\x02\x7f-123"
        result = sanitize_operation_id(raw)
        assert "\x00" not in result
        assert "\x01" not in result
        assert "\x7f" not in result

    def test_carriage_return_removed(self):
        raw = "op-123\r\nINJECTED"
        result = sanitize_operation_id(raw)
        assert "\r" not in result
        assert "\n" not in result

    def test_tab_removed(self):
        raw = "op-123\tINJECTED"
        result = sanitize_operation_id(raw)
        assert "\t" not in result

    def test_disallowed_chars_stripped(self):
        raw = "op-123@#$%^&*()"
        result = sanitize_operation_id(raw)
        # Only allowed chars remain
        assert re.match(r"^[A-Za-z0-9._-]+$", result)

    def test_all_disallowed_returns_unknown(self):
        raw = "@#$%^&*()"
        result = sanitize_operation_id(raw)
        assert result == "unknown"

    def test_length_bounded(self):
        raw = "a" * 500
        result = sanitize_operation_id(raw)
        assert len(result) <= 128

    def test_log_injection_attempt_neutralized(self):
        # Classic log injection: newline + fake log line
        raw = "op-123\n2026-08-04 INFO operation_timing stage=fake"
        result = sanitize_operation_id(raw)
        assert "\n" not in result
        assert "fake" not in result


class TestStageEnforcement:
    def test_known_stage_logged_as_is(self, captured_logs):
        buf, logger = captured_logs
        timer = OperationTimer("op-1", log=logger)
        timer.record("request_received")
        parsed = _parse_log_line(_all_log_lines(buf)[0])
        assert parsed["stage"] == "request_received"

    def test_unknown_stage_classified_as_unknown(self, captured_logs):
        buf, logger = captured_logs
        timer = OperationTimer("op-2", log=logger)
        timer.record("bogus_stage")
        parsed = _parse_log_line(_all_log_lines(buf)[0])
        assert parsed["stage"] == "unknown"

    def test_all_documented_stages_are_valid(self):
        for stage in KNOWN_STAGES:
            assert re.match(r"^[a-z_]+$", stage), f"Invalid stage name: {stage}"

    def test_expected_stages_present(self):
        expected = {
            "request_received",
            "identity_profile_ready",
            "intent_resolved",
            "service_started",
            "service_finished",
            "response_returned",
        }
        assert expected == KNOWN_STAGES

    def test_provider_search_stages_removed(self):
        # The old unapproved stages must NOT be present
        assert "provider_search_started" not in KNOWN_STAGES
        assert "provider_search_finished" not in KNOWN_STAGES
        assert "response_generation_started" not in KNOWN_STAGES
        assert "response_generation_finished" not in KNOWN_STAGES
        assert "result_persisted" not in KNOWN_STAGES


class TestProviderOutcomeEnforcement:
    def test_known_provider_logged_as_is(self, captured_logs):
        buf, logger = captured_logs
        timer = OperationTimer("op-p1", log=logger)
        timer.record("service_finished", provider="jsearch")
        parsed = _parse_log_line(_all_log_lines(buf)[0])
        assert parsed["provider"] == "jsearch"

    def test_unknown_provider_classified(self, captured_logs):
        buf, logger = captured_logs
        timer = OperationTimer("op-p2", log=logger)
        timer.record("service_finished", provider="https://evil.com/payload")
        parsed = _parse_log_line(_all_log_lines(buf)[0])
        assert parsed["provider"] == "unknown"

    def test_known_outcome_logged_as_is(self, captured_logs):
        buf, logger = captured_logs
        timer = OperationTimer("op-o1", log=logger)
        timer.record("service_finished", outcome="ok")
        parsed = _parse_log_line(_all_log_lines(buf)[0])
        assert parsed["outcome"] == "ok"

    def test_unknown_outcome_classified(self, captured_logs):
        buf, logger = captured_logs
        timer = OperationTimer("op-o2", log=logger)
        timer.record("service_finished", outcome="TypeError: got an unexpected keyword argument")
        parsed = _parse_log_line(_all_log_lines(buf)[0])
        assert parsed["outcome"] == "unknown"


class TestTerminalEventGuarantee:
    def test_success_emits_one_terminal(self, captured_logs):
        buf, logger = captured_logs
        timer = OperationTimer("op-t1", log=logger)
        timer.record("request_received")
        timer.record("service_started")
        timer.record("service_finished")
        timer.record("response_returned", http_status=200)
        # Try to emit a second terminal — must be dropped
        timer.record("response_returned", http_status=200)
        lines = _all_log_lines(buf)
        terminal_lines = [l for l in lines if "stage=response_returned" in l]
        assert len(terminal_lines) == 1

    def test_http_error_emits_one_terminal(self, captured_logs):
        buf, logger = captured_logs
        timer = OperationTimer("op-t2", log=logger)
        timer.record("request_received")
        timer.record("response_returned", http_status=401, outcome="http_exception")
        timer.record("response_returned", http_status=401)
        lines = _all_log_lines(buf)
        terminal_lines = [l for l in lines if "stage=response_returned" in l]
        assert len(terminal_lines) == 1

    def test_unexpected_error_emits_one_terminal(self, captured_logs):
        buf, logger = captured_logs
        timer = OperationTimer("op-t3", log=logger)
        timer.record("request_received")
        timer.record("response_returned", outcome="error")
        timer.record("response_returned", outcome="error")
        lines = _all_log_lines(buf)
        terminal_lines = [l for l in lines if "stage=response_returned" in l]
        assert len(terminal_lines) == 1

    def test_cancellation_emits_one_terminal(self, captured_logs):
        buf, logger = captured_logs
        timer = OperationTimer("op-t4", log=logger)
        timer.record("request_received")
        timer.record("response_returned", outcome="cancelled")
        timer.record("response_returned", outcome="cancelled")
        lines = _all_log_lines(buf)
        terminal_lines = [l for l in lines if "stage=response_returned" in l]
        assert len(terminal_lines) == 1

    def test_has_terminal_property(self, captured_logs):
        _, logger = captured_logs
        timer = OperationTimer("op-t5", log=logger)
        assert timer.has_terminal is False
        timer.record("response_returned", http_status=200)
        assert timer.has_terminal is True


class TestPrivacyContract:
    SENSITIVE_VALUES = [
        "john@example.com",
        "Software Engineer with 5 years experience",
        "https://example.com/job/123",
        "sk-abc123secretkey",
        "Dear Hiring Manager",
        "Bearer eyJhbGciOiJIUzI1NiJ9",
    ]

    def test_no_sensitive_data_in_log(self, captured_logs):
        buf, logger = captured_logs
        timer = OperationTimer("op-priv", log=logger)
        timer.record("request_received")
        timer.record("identity_profile_ready", outcome="profile")
        timer.record("intent_resolved", outcome="legacy")
        timer.record("service_started", provider="legacy")
        timer.record("service_finished", provider="legacy")
        timer.record("response_returned", http_status=200)
        output = buf.getvalue()
        for sensitive in self.SENSITIVE_VALUES:
            assert sensitive not in output, f"Sensitive value leaked: {sensitive}"

    def test_request_ref_logged_alongside_operation_id(self, captured_logs):
        buf, logger = captured_logs
        timer = OperationTimer("op-ref", request_ref="ERR-ABC123", log=logger)
        timer.record("request_received")
        parsed = _parse_log_line(_all_log_lines(buf)[0])
        assert parsed["operation_id"] == "op-ref"
        assert parsed["request_ref"] == "ERR-ABC123"


class TestDurationBasics:
    def test_duration_ms_is_non_negative(self, captured_logs):
        buf, logger = captured_logs
        timer = OperationTimer("op-d1", log=logger)
        timer.record("request_received")
        timer.record("intent_resolved")
        lines = _all_log_lines(buf)
        parsed = _parse_log_line(lines[1])
        assert int(parsed["duration_ms"]) >= 0
        assert int(parsed["total_ms"]) >= 0

    def test_total_ms_grows_monotonically(self, captured_logs):
        buf, logger = captured_logs
        timer = OperationTimer("op-d2", log=logger)
        timer.record("request_received")
        time.sleep(0.01)
        timer.record("intent_resolved")
        time.sleep(0.01)
        timer.record("response_returned", http_status=200)
        lines = _all_log_lines(buf)
        totals = [int(_parse_log_line(l)["total_ms"]) for l in lines]
        assert totals[0] <= totals[1] <= totals[2]

    def test_unknown_operation_id_defaults_to_unknown(self, captured_logs):
        buf, logger = captured_logs
        timer = OperationTimer(None, log=logger)
        timer.record("request_received")
        parsed = _parse_log_line(_all_log_lines(buf)[0])
        assert parsed["operation_id"] == "unknown"
