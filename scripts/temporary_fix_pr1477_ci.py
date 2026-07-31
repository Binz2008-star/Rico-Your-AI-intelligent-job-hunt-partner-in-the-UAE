from pathlib import Path

TEST_PATH = Path("tests/test_ai_grounding_contract.py")
WORKFLOW_PATH = Path(".github/workflows/temporary-pr1477-ci-fix.yml")
SELF_PATH = Path("scripts/temporary_fix_pr1477_ci.py")

old = '''    def test_primary_provider_prompt_is_unchanged_by_the_extraction(self):
        """The refactor that made the contract shareable must not have altered
        what the primary provider receives."""
        primary = get_rico_system_prompt()
        for marker in (
            "Safety rules (non-negotiable):",
            "9. Identity integrity:",
            "10. Untrusted metadata rule:",
            "Evidence contract (non-negotiable",
            "Uploaded files (My Files):",
            "When calling tools:",
        ):
            assert marker in primary, marker
        # Rules stay in their numbered positions in the primary prompt.
        assert primary.index("9. Identity integrity:") < primary.index("10. Untrusted metadata rule:")
'''

new = '''    def test_primary_provider_prompt_is_unchanged_by_the_extraction(self):
        """The primary provider must receive every shared grounding rule in
        the same numbered order as the provider-agnostic contract."""
        primary = get_rico_system_prompt()
        for marker in (
            "Safety rules (non-negotiable):",
            "9. Identity integrity:",
            "10. External-draft identity rule:",
            "11. Untrusted metadata rule:",
            "12. User safety constraints:",
            "Evidence contract (non-negotiable",
            "Uploaded files (My Files):",
            "When calling tools:",
        ):
            assert marker in primary, marker
        # Shared grounding rules stay in their numbered order in the primary prompt.
        ordered_markers = (
            "9. Identity integrity:",
            "10. External-draft identity rule:",
            "11. Untrusted metadata rule:",
            "12. User safety constraints:",
        )
        assert [primary.index(marker) for marker in ordered_markers] == sorted(
            primary.index(marker) for marker in ordered_markers
        )
'''

text = TEST_PATH.read_text(encoding="utf-8")
if text.count(old) != 1:
    raise SystemExit("Expected exactly one stale primary-prompt assertion block")
TEST_PATH.write_text(text.replace(old, new), encoding="utf-8")

WORKFLOW_PATH.unlink()
SELF_PATH.unlink()
