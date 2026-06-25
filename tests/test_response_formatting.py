"""Context-Aware Response Formatting (presentation layer).

Deterministic formatting only — no business logic, no LLM, no I/O. Covers the
six required behaviors:
  1. PR/CI status → table + bold final decision
  2. commands / SHAs / paths wrapped in code formatting
  3. casual Arabic reply is NOT over-formatted
  4. job summary uses structured fields; unverified apply link not over-promoted
  5. safe error never exposes raw internal error strings
  6. Arabic response stays Arabic (no silent switch to English)
"""
from __future__ import annotations

from src.services import response_formatting as rf


# 1. PR / CI status → table + bold final decision ─────────────────────────────

def test_status_report_uses_table_and_bold_decision():
    out = rf.format_status_report(
        "PR #749 status",
        rows=[
            ["Head", rf.inline_code("e097f8b")],
            ["CI", "green"],
        ],
        decision="READY",
        commands=["git push -u origin main"],
    )
    # Markdown table structure
    assert "| " in out and "| --- |" in out
    # Final decision is bold + recognized critical state → uppercase
    assert "**Decision**" in out
    assert "**READY**" in out
    # Commands rendered in a fenced bash block
    assert "```bash" in out and "git push -u origin main" in out


def test_do_not_merge_renders_uppercase_label():
    out = rf.format_status_report("X", rows=[["a", "b"]], decision="do not merge")
    assert "**DO NOT MERGE**" in out


# 2. commands / SHAs / paths in code formatting ───────────────────────────────

def test_inline_code_wraps_values():
    assert rf.inline_code("9628c4b") == "`9628c4b`"
    assert rf.inline_code("src/services/response_formatting.py") == "`src/services/response_formatting.py`"
    assert rf.inline_code("") == "—"  # empty cell never collapses


def test_code_block_fences_commands():
    block = rf.code_block("SELECT 1;", "sql")
    assert block.startswith("```sql\n") and block.endswith("\n```")
    assert "SELECT 1;" in block


def test_table_escapes_pipes_and_newlines():
    out = rf.md_table(["k", "v"], [["a", "x|y\nz"]])
    assert "x\\|y z" in out  # pipe escaped, newline flattened


# 3. casual Arabic reply is NOT over-formatted ────────────────────────────────

def test_casual_arabic_reply_passthrough():
    msg = "أهلاً! كيف أقدر أساعدك اليوم؟"
    out = rf.apply_context_formatting("casual", {"message": msg}, language="ar")
    assert out == msg
    # No structural markdown injected
    assert "|" not in out
    assert "##" not in out
    assert "**" not in out
    assert "```" not in out


def test_unknown_type_passes_message_through():
    assert rf.apply_context_formatting("chitchat", {"message": "hello"}, language="en") == "hello"


# 4. job summary: structured fields, unverified link not over-promoted ────────

def test_job_summary_unverified_link_not_promoted():
    job = {
        "title": "Backend Engineer", "company": "Acme", "location": "Dubai",
        "match": 82, "apply_status": "unverified",
        "apply_url": "https://example.com/job/1",
    }
    out = rf.format_job_summary(job)
    # Structured fields present
    assert "Role" in out and "Company" in out and "Match" in out
    assert "82%" in out
    # Unverified → neutral status label, URL not surfaced, not bolded
    assert "Unverified" in out
    assert "https://example.com/job/1" not in out
    assert "**Unverified**" not in out


def test_job_summary_verified_link_surfaced():
    job = {"title": "PM", "company": "Beta", "apply_status": "verified",
           "apply_url": "https://careers.beta.ae/pm"}
    out = rf.format_job_summary(job)
    assert "Verified" in out
    assert "https://careers.beta.ae/pm" in out  # only verified link is shown


def test_job_summary_missing_link_is_unavailable():
    out = rf.format_job_summary({"title": "Analyst", "company": "Gamma"})
    assert "Unavailable" in out


# 5. safe error never exposes raw internal error strings ──────────────────────

def test_safe_error_redacts_raw_internal_error():
    raw = 'Traceback (most recent call last): File "x.py", line 5, in <module> psycopg2.OperationalError'
    out = rf.format_safe_error(raw, reference="ERR-123")
    assert "Traceback" not in out
    assert "psycopg2" not in out
    assert "OperationalError" not in out
    assert "`ERR-123`" in out  # reference in code formatting
    assert out.startswith("**")  # main issue bolded


def test_safe_error_keeps_clean_message():
    out = rf.format_safe_error("Your file is too large.")
    assert "**Your file is too large.**" in out


# 6. Arabic stays Arabic (no silent switch to English) ────────────────────────

def test_arabic_status_report_uses_arabic_labels():
    out = rf.format_status_report(
        "حالة الطلب",
        rows=[["الفرع", rf.inline_code("main")]],
        decision="جاهز",
        language="ar",
    )
    assert "القرار" in out          # Arabic "Decision" label
    assert "Decision" not in out     # no English leak
    assert "حالة الطلب" in out


def test_arabic_job_summary_uses_arabic_labels():
    job = {"title": "مهندس", "company": "أكمي", "apply_status": "unverified"}
    out = rf.format_job_summary(job, language="ar")
    assert "الدور" in out and "الشركة" in out
    assert "غير مُتحقَّق" in out          # Arabic "Unverified"
    assert "Unverified" not in out
    assert "Role" not in out and "Company" not in out


def test_arabic_safe_error_is_arabic():
    out = rf.format_safe_error("psycopg2.OperationalError: boom", language="ar")
    assert "psycopg2" not in out
    # Falls back to the Arabic safe default, not the English one
    assert "Something went wrong" not in out
    assert rf._ARABIC_RE.search(out)


# Action steps ────────────────────────────────────────────────────────────────

def test_action_steps_numbered_with_commands_and_next():
    out = rf.format_action_steps(
        [
            "Open the Applications tab",
            ("Run the sync", "python -m src.run_daily"),
        ],
        next_action="Confirm the count incremented",
    )
    assert "1. Open the Applications tab" in out
    assert "2. Run the sync" in out
    assert "```bash" in out and "python -m src.run_daily" in out
    assert "**Next**: Confirm the count incremented" in out


def test_plain_text_fallback_when_markdown_disabled():
    out = rf.format_status_report(
        "S", rows=[["Head", "abc123"], ["CI", "green"]], markdown=False,
    )
    assert "|" not in out            # no markdown table
    assert "Head: abc123" in out and "CI: green" in out
