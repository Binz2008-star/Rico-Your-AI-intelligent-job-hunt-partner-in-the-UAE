"""
tests/test_no_import_time_env_mutation.py

Recurrence guard for the import-time environment-leak defect class.

WHY THIS EXISTS
---------------
pytest imports every test module during *collection*, before a single test
runs. Any statement at a test module's top level therefore executes once, for
the whole session, in the shared process — and unlike a fixture, nothing ever
undoes it.

``tests/test_password_reset.py`` did exactly that::

    os.environ["RICO_ENV"] = "development"     # module level, never restored

``_is_production()`` (``src/api/auth.py``) resolves
``RICO_ENV -> APP_ENV -> ENV -> ENVIRONMENT`` and takes the first non-empty
value, so that one line shadowed every *other* module that marks production via
a lower-precedence variable. Five production fail-closed guards — guest
capability secret, and the Telegram / Jotform / GitHub webhook secrets —
returned 200 where they assert 503 in a full-suite run, while still passing in
isolation and in CI (whose allowlist happens to exclude the poisoning module).

The guards were correct the whole time. What was broken was the suite's ability
to prove it. That is the class of defect this test exists to prevent, because it
fails *open*: it makes a red thing look green.

WHAT IS FORBIDDEN
-----------------
At a test module's import time (module level, including inside module-level
``if`` / ``try`` / ``with`` / loop bodies), these unconditionally overwrite or
remove whatever the environment already held:

    os.environ["X"] = ...        del os.environ["X"]
    os.environ.update(...)       os.environ.pop("X")        os.environ.clear()

Use a fixture instead, so the change is scoped and restored::

    @pytest.fixture(autouse=True)
    def _env(monkeypatch):
        monkeypatch.setenv("RICO_ENV", "development")   # restored after the test

WHAT IS DELIBERATELY STILL ALLOWED
----------------------------------
``os.environ.setdefault(...)`` at import time (196 occurrences across 88 files
at the time of writing). This is a narrower rule than "no import-time env
mutation at all", and the narrowing is intentional rather than incidental:
``setdefault`` never overwrites a value the environment already holds, so it
cannot shadow another module's explicit intent — which is precisely the
mechanism that caused the failure above. It can still leak a value into the
process, so it is not harmless, merely not *this* defect. Tightening it further
would require editing 88 files and is a separate decision.

``tests/conftest.py`` is exempt. It is not a test module; it is the designated
suite-wide setup file, and its own docstring documents the one variable it sets
(``RICO_OPERATION_STORE``) together with how tests opt back out via monkeypatch.
Centralised, documented setup in the file pytest reserves for it is the correct
pattern — the defect is unrestored setup hidden in an arbitrary test module.
"""
from __future__ import annotations

import ast
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parent

# Not a test module: the file pytest designates for suite-wide setup.
EXEMPT_FILES = {"conftest.py"}

# Statement forms that unconditionally overwrite or remove an existing value.
FORBIDDEN_METHODS = {"update", "pop", "clear"}

# Never descend into these — their bodies run when *called*, not when imported.
_DEFERS_EXECUTION = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Lambda,
)


def _is_environ(node: ast.AST) -> bool:
    """True for ``os.environ`` or a bare ``environ`` imported from ``os``."""
    if isinstance(node, ast.Attribute) and node.attr == "environ":
        return isinstance(node.value, ast.Name) and node.value.id == "os"
    return isinstance(node, ast.Name) and node.id == "environ"


def _import_time_nodes(nodes: list[ast.AST]):
    """Yield every AST node reachable at import time.

    Recurses through control flow that *does* execute on import (``if``,
    ``try``, ``with``, ``for``, ``while``) but prunes at any construct whose
    body is deferred until call time. Pruning a ``def`` also skips its
    decorators and parameter defaults, which do run at import — a deliberate
    trade for a simple rule, since neither is a plausible place to find a bare
    ``os.environ`` assignment.
    """
    for stmt in nodes:
        if isinstance(stmt, _DEFERS_EXECUTION):
            continue
        yield stmt
        # Recurse manually rather than with ast.walk, which would descend into
        # nested def/class/lambda bodies that do not run at import time.
        yield from _import_time_nodes(list(ast.iter_child_nodes(stmt)))


def _violations(tree: ast.Module) -> list[str]:
    found: list[str] = []
    for node in _import_time_nodes(tree.body):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and _is_environ(target.value):
                    found.append(f"line {node.lineno}: os.environ[...] = ...")
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and _is_environ(target.value):
                    found.append(f"line {node.lineno}: del os.environ[...]")
        elif isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr in FORBIDDEN_METHODS
                and _is_environ(func.value)
            ):
                found.append(f"line {node.lineno}: os.environ.{func.attr}(...)")
    return found


def _module_level_walk_stops_at_functions() -> None:
    """Self-check: the walker must not report mutations inside a function."""
    tree = ast.parse(
        "import os\n"
        "def f():\n"
        "    os.environ['INSIDE_FUNCTION'] = 'x'\n"
        "class C:\n"
        "    def m(self):\n"
        "        os.environ.pop('INSIDE_METHOD', None)\n"
    )
    assert _violations(tree) == []


def _module_level_walk_finds_nested_control_flow() -> None:
    """Self-check: control flow that runs on import must still be reported."""
    tree = ast.parse(
        "import os\n"
        "if True:\n"
        "    os.environ['LEAKED'] = 'x'\n"
    )
    assert len(_violations(tree)) == 1


def test_detector_is_calibrated():
    """The detector must distinguish import time from call time.

    Guards the guard: a walker that descended into function bodies would flag
    every legitimate test, and one that ignored module-level ``if`` blocks would
    miss real leaks.
    """
    _module_level_walk_stops_at_functions()
    _module_level_walk_finds_nested_control_flow()


def test_no_test_module_mutates_environ_at_import_time():
    """No test module may overwrite or remove an env var at import time.

    Such a write is never undone and applies to the whole session, so it can
    silently invert another module's assertions — including production
    fail-closed guards, where the failure mode is a false green.
    """
    offenders: dict[str, list[str]] = {}

    for path in sorted(TESTS_ROOT.rglob("*.py")):
        if path.name in EXEMPT_FILES:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            # Not parseable as Python: nothing executes at import time either.
            continue
        found = _violations(tree)
        if found:
            offenders[str(path.relative_to(TESTS_ROOT.parent))] = found

    assert not offenders, (
        "Test modules mutate os.environ at import time:\n"
        + "\n".join(
            f"  {name}\n    " + "\n    ".join(hits)
            for name, hits in sorted(offenders.items())
        )
        + "\n\nThis runs during pytest collection, before any test, and is never "
        "restored — it applies to the whole session and can invert another "
        "module's assertions.\nScope it in a fixture instead:\n\n"
        "    @pytest.fixture(autouse=True)\n"
        "    def _env(monkeypatch):\n"
        "        monkeypatch.setenv('NAME', 'value')   # restored after each test\n"
    )
