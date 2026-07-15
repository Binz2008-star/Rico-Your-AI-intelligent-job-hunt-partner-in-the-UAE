"""Security regression test: smoke-test scripts must refuse to run without env vars.

Verifies that scripts/subscription_smoke_test.py, scripts/production_smoke_test.py,
and scripts/stripe_runtime_diagnostic.py all exit with code 2 and print the missing
env var name when RICO_SMOKE_TEST_EMAIL or RICO_SMOKE_TEST_PASSWORD is not set.

This prevents credentials from being hard-coded back into the scripts.
"""
import subprocess
import sys
import os
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

SCRIPTS = [
    "subscription_smoke_test.py",
    "production_smoke_test.py",
    "stripe_runtime_diagnostic.py",
]

SENSITIVE_PATTERNS = [
    "SmokeTest2026!",
    "smoke_test_2026@ricohunt.com",
]


def _run_script(script_name: str, env_overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.pop("RICO_SMOKE_TEST_EMAIL", None)
    env.pop("RICO_SMOKE_TEST_PASSWORD", None)
    if env_overrides:
        env.update(env_overrides)
    script_path = SCRIPTS_DIR / script_name
    return subprocess.run(
        [sys.executable, str(script_path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )


class TestScriptsRefuseWithoutEnvVars:
    """Each script must fail closed when credentials are not in the environment."""

    def test_subscription_smoke_refuses_without_email(self):
        result = _run_script("subscription_smoke_test.py", {"RICO_SMOKE_TEST_PASSWORD": "x"})
        assert result.returncode == 2
        assert "RICO_SMOKE_TEST_EMAIL" in result.stderr

    def test_subscription_smoke_refuses_without_password(self):
        result = _run_script("subscription_smoke_test.py", {"RICO_SMOKE_TEST_EMAIL": "x"})
        assert result.returncode == 2
        assert "RICO_SMOKE_TEST_PASSWORD" in result.stderr

    def test_subscription_smoke_refuses_without_both(self):
        result = _run_script("subscription_smoke_test.py")
        assert result.returncode == 2
        assert "RICO_SMOKE_TEST_EMAIL" in result.stderr
        assert "RICO_SMOKE_TEST_PASSWORD" in result.stderr

    def test_production_smoke_refuses_without_email(self):
        result = _run_script("production_smoke_test.py", {"RICO_SMOKE_TEST_PASSWORD": "x"})
        assert result.returncode == 2
        assert "RICO_SMOKE_TEST_EMAIL" in result.stderr

    def test_production_smoke_refuses_without_password(self):
        result = _run_script("production_smoke_test.py", {"RICO_SMOKE_TEST_EMAIL": "x"})
        assert result.returncode == 2
        assert "RICO_SMOKE_TEST_PASSWORD" in result.stderr

    def test_stripe_diagnostic_refuses_without_email(self):
        result = _run_script("stripe_runtime_diagnostic.py", {"RICO_SMOKE_TEST_PASSWORD": "x"})
        assert result.returncode == 2
        assert "RICO_SMOKE_TEST_EMAIL" in result.stderr

    def test_stripe_diagnostic_refuses_without_password(self):
        result = _run_script("stripe_runtime_diagnostic.py", {"RICO_SMOKE_TEST_EMAIL": "x"})
        assert result.returncode == 2
        assert "RICO_SMOKE_TEST_PASSWORD" in result.stderr

    def test_no_script_prints_password_value(self):
        """Even in the error message, the password value must never appear."""
        result = _run_script(
            "subscription_smoke_test.py",
            {"RICO_SMOKE_TEST_EMAIL": "x", "RICO_SMOKE_TEST_PASSWORD": "supersecret123"},
        )
        # The script should NOT exit 2 here since both are set.
        # But if it does fail for another reason, the password must not appear.
        assert "supersecret123" not in result.stdout
        assert "supersecret123" not in result.stderr


class TestNoHardcodedCredentialsInScripts:
    """Static guard: the compromised credential strings must not appear in any script."""

    def test_no_compromised_password_in_any_script(self):
        for script_name in SCRIPTS:
            script_path = SCRIPTS_DIR / script_name
            content = script_path.read_text()
            for pattern in SENSITIVE_PATTERNS:
                assert pattern not in content, (
                    f"{script_name} still contains hardcoded credential: {pattern!r}"
                )
