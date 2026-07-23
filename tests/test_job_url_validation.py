"""Tests for validate_job_url — the canonical URL safety gate.

Verifies that unsafe schemes (javascript:, data:, file:, etc.), URLs with
credentials, control characters, and missing hostnames are rejected at
ingestion and all egress boundaries.
"""
from src.services.job_link_trust import validate_job_url


class TestValidateJobUrl:
    def test_valid_https(self):
        assert validate_job_url("https://example.com/jobs/123") == "https://example.com/jobs/123"

    def test_valid_http(self):
        assert validate_job_url("http://example.com/careers/456") == "http://example.com/careers/456"

    def test_javascript_scheme_rejected(self):
        assert validate_job_url("javascript:alert(1)") == ""

    def test_data_scheme_rejected(self):
        assert validate_job_url("data:text/html,<script>alert(1)</script>") == ""

    def test_file_scheme_rejected(self):
        assert validate_job_url("file:///etc/passwd") == ""

    def test_ftp_scheme_rejected(self):
        assert validate_job_url("ftp://example.com/file") == ""

    def test_empty_string(self):
        assert validate_job_url("") == ""

    def test_none(self):
        assert validate_job_url(None) == ""

    def test_non_string(self):
        assert validate_job_url(123) == ""

    def test_whitespace_only(self):
        assert validate_job_url("   ") == ""

    def test_strips_whitespace(self):
        assert validate_job_url("  https://example.com  ") == "https://example.com"

    def test_no_hostname(self):
        assert validate_job_url("https://") == ""

    def test_no_scheme(self):
        assert validate_job_url("example.com/jobs") == ""

    def test_credentials_rejected(self):
        assert validate_job_url("https://user:pass@example.com/jobs") == ""

    def test_control_chars_rejected(self):
        assert validate_job_url("https://example.com\x00/jobs") == ""

    def test_newline_rejected(self):
        assert validate_job_url("https://example.com\n/jobs") == ""

    def test_protocol_relative_rejected(self):
        assert validate_job_url("//example.com/jobs") == ""

    def test_uppercase_scheme_normalized(self):
        result = validate_job_url("HTTPS://example.com/jobs")
        assert result == "HTTPS://example.com/jobs"

    def test_valid_with_port(self):
        assert validate_job_url("https://example.com:8080/jobs") == "https://example.com:8080/jobs"

    def test_valid_with_query(self):
        assert validate_job_url("https://example.com/jobs?q=engineer&loc=dubai") == "https://example.com/jobs?q=engineer&loc=dubai"
