"""Regression test for Python stdlib `profile` module shadow fix.

`src/profile.py` collided with Python's standard-library `profile` module,
which `cProfile` imports internally via `spacy` and other packages.
Renaming it to `src/candidate_profile.py` must restore stdlib `profile`
while keeping Rico candidate-profile imports working.
"""

import importlib
import sys


def test_stdlib_profile_module_is_not_shadowed_by_src_profile():
    """With src/ on sys.path, importing cProfile must resolve the stdlib profile."""
    # Force Python to re-evaluate the module resolution instead of using a cache
    # left over from a previous import attempt in the same process.
    for mod_name in ("profile", "cProfile"):
        sys.modules.pop(mod_name, None)

    import cProfile  # noqa: F401
    import profile as stdlib_profile  # noqa: F401

    assert hasattr(stdlib_profile, "run"), "stdlib profile module missing 'run'"
    assert callable(stdlib_profile.run), "stdlib profile.run is not callable"


def test_candidate_profile_import_works_under_new_name():
    """Rico candidate-profile functions remain importable from src.candidate_profile."""
    from src.candidate_profile import (
        get_candidate_profile,
        get_target_roles,
    )

    profile = get_candidate_profile()
    assert isinstance(profile, dict)
    assert "target_roles" in profile
    assert isinstance(get_target_roles(), list)
