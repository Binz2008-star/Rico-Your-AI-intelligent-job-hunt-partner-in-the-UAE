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
At a test module's import time — module level, including inside module-level
``if`` / ``try`` / ``with`` / loop bodies *and class bodies*, all of which
execute on import — these unconditionally overwrite or remove whatever the
environment already held:

    os.environ["X"] = ...        del os.environ["X"]
    os.environ.update(...)       os.environ.pop("X")        os.environ.clear()
    os.putenv("X", ...)          os.unsetenv("X")

``os.putenv`` / ``os.unsetenv`` are included because they change the real
process environment while leaving the ``os.environ`` mapping untouched. That
makes them strictly worse than an ``os.environ`` write: the leak is invisible to
any code that inspects ``os.environ``, including this detector's own subject
matter. They were considered, not overlooked.

Use a fixture instead, so the change is scoped and restored::

    @pytest.fixture(autouse=True)
    def _env(monkeypatch):
        monkeypatch.setenv("RICO_ENV", "development")   # restored after the test

WHAT IS DELIBERATELY STILL ALLOWED
----------------------------------
``os.environ.setdefault(...)`` at import time (196 occurrences across 88 files
at the time of writing).

**Status: accepted technical debt, with a release condition — not "fine", and
not rejected as a non-issue.** ``setdefault`` cannot shadow a value the
environment already holds, so it is not the defect documented above and does not
block. But it is still a mutation executed at collection time: when a variable
is *unset*, the first module to import decides the value every later test sees.
That is a genuine second-order leak, merely a weaker one.

The release condition: **this must be cleaned up, or consolidated into a single
central bootstrap, before the full suite is ever made a required merge gate.**
Until then the 196-across-88 churn buys no proportionate safety, so it stays.
A live example of the weaker form is in ``tests/test_security_audit.py``, where
``os.environ.setdefault("JWT_SECRET", "x" * 32)`` yields to a shorter
caller-supplied secret and changes what the module's own fixtures can do.

EXEMPTIONS
----------
``tests/conftest.py`` — and only that exact path, not every ``conftest.py`` in
the tree. It is not a test module; it is the single file pytest designates for
suite-wide setup, and its own docstring documents the one variable it sets
(``RICO_OPERATION_STORE``) together with how tests opt back out via monkeypatch.
Centralised, documented setup in the file pytest reserves for it is the correct
pattern. A *nested* conftest (``tests/integration/conftest.py`` and the like)
gets no such licence: it configures one subtree but still leaks into the whole
session, so the rule applies to it exactly as to any other module.
"""
from __future__ import annotations

import ast
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TESTS_ROOT.parent

# Exempt by EXACT relative path, not by basename. Only the single designated
# suite-wide setup file is excused; a nested tests/*/conftest.py is an ordinary
# collaborator in one subtree and gets no special licence to leak into the whole
# session, so the rule applies to it like any other module.
EXEMPT_PATHS = {Path("tests/conftest.py")}

# Statement forms that unconditionally overwrite or remove an existing value.
FORBIDDEN_METHODS = {"update", "pop", "clear"}

# os.putenv / os.unsetenv mutate the real process environment while leaving the
# os.environ mapping untouched, so they bypass every os.environ-shaped check.
# They are rarer and blunter than os.environ writes — and strictly worse, since
# the leak becomes invisible to code that reads os.environ — so they are
# forbidden at import time on the same terms.
FORBIDDEN_OS_FUNCTIONS = {"putenv", "unsetenv"}

# Never descend into these — their bodies run when *called*, not when imported.
# ClassDef is deliberately NOT here: a class body executes at import, so a
# module-level `class C: os.environ["X"] = "y"` really does leak. Methods stay
# excluded automatically because they are FunctionDef nodes nested inside the
# class body.
_DEFERS_EXECUTION = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.Lambda,
)


def _is_environ(node: ast.AST) -> bool:
    """True for ``os.environ`` or a bare ``environ`` imported from ``os``."""
    if isinstance(node, ast.Attribute) and node.attr == "environ":
        return isinstance(node.value, ast.Name) and node.value.id == "os"
    return isinstance(node, ast.Name) and node.id == "environ"


def _is_os_module(node: ast.AST) -> bool:
    """True for the ``os`` module itself (``os.putenv`` style calls)."""
    return isinstance(node, ast.Name) and node.id == "os"


def _import_time_nodes(nodes: list[ast.AST]):
    """Yield every AST node reachable at import time.

    Recurses through control flow that *does* execute on import (``if``,
    ``try``, ``with``, ``for``, ``while``) and through class bodies, which also
    run at import. Prunes only at ``def`` / ``async def`` / ``lambda``, whose
    bodies run when called. Pruning a ``def`` also skips its decorators and
    parameter defaults, which do run at import — a deliberate trade for a simple
    rule, since neither is a plausible place to find a bare ``os.environ``
    assignment.
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
            if isinstance(func, ast.Attribute):
                if func.attr in FORBIDDEN_METHODS and _is_environ(func.value):
                    found.append(f"line {node.lineno}: os.environ.{func.attr}(...)")
                elif func.attr in FORBIDDEN_OS_FUNCTIONS and _is_os_module(func.value):
                    found.append(f"line {node.lineno}: os.{func.attr}(...)")
            elif isinstance(func, ast.Name) and func.id in FORBIDDEN_OS_FUNCTIONS:
                # `from os import putenv` — same process-level mutation.
                found.append(f"line {node.lineno}: {func.id}(...)")
    return found


def _module_level_walk_stops_at_functions() -> None:
    """Self-check: the walker must not report mutations inside a function.

    Methods are covered by the same rule for free: a method is a FunctionDef
    nested in the class body, so descending into the class body still stops at
    the method.
    """
    tree = ast.parse(
        "import os\n"
        "def f():\n"
        "    os.environ['INSIDE_FUNCTION'] = 'x'\n"
        "class C:\n"
        "    def m(self):\n"
        "        os.environ.pop('INSIDE_METHOD', None)\n"
    )
    assert _violations(tree) == []


def _class_body_is_flagged() -> None:
    """Self-check: a class *body* runs at import, so it must be reported.

    Pruning ClassDef alongside FunctionDef is the intuitive mistake — and it
    would silently blind the detector to a real leak, since
    ``class C: os.environ["X"] = "y"`` at module level executes on collection
    exactly like a bare assignment.
    """
    tree = ast.parse(
        "import os\n"
        "class C:\n"
        "    os.environ['IN_CLASS_BODY'] = 'x'\n"
    )
    assert len(_violations(tree)) == 1


def _putenv_is_flagged() -> None:
    """Self-check: os.putenv / os.unsetenv bypass the os.environ mapping."""
    tree = ast.parse("import os\nos.putenv('X', 'y')\nos.unsetenv('Z')\n")
    assert len(_violations(tree)) == 2


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
    _class_body_is_flagged()
    _putenv_is_flagged()


def test_no_test_module_mutates_environ_at_import_time():
    """No test module may overwrite or remove an env var at import time.

    Such a write is never undone and applies to the whole session, so it can
    silently invert another module's assertions — including production
    fail-closed guards, where the failure mode is a false green.
    """
    offenders: dict[str, list[str]] = {}

    for path in sorted(TESTS_ROOT.rglob("*.py")):
        if path.relative_to(REPO_ROOT) in EXEMPT_PATHS:
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
