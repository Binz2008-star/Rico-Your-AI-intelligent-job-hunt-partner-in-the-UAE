import types

import pytest
import tests.integration.test_operation_multiworker_postgres as op_postgres


class _FakeForkContext:
    name = "fork"


class _FakeSpawnContext:
    name = "spawn"


def test_get_test_context_prefers_fork(monkeypatch):
    """When fork is available, _get_test_context returns it without trying spawn."""
    call_order = []

    def fake_get_context(method):
        call_order.append(method)
        if method == "fork":
            return _FakeForkContext()
        raise AssertionError("spawn should not be requested when fork is available")

    fake_mp = types.SimpleNamespace(get_context=fake_get_context)
    monkeypatch.setattr(op_postgres, "mp", fake_mp)

    ctx = op_postgres._get_test_context()
    assert ctx.name == "fork"
    assert call_order == ["fork"]


def test_get_test_context_falls_back_to_spawn(monkeypatch):
    """When fork is unavailable, _get_test_context falls back to spawn."""
    call_order = []

    def fake_get_context(method):
        call_order.append(method)
        if method == "fork":
            raise ValueError("fork unavailable")
        if method == "spawn":
            return _FakeSpawnContext()
        raise AssertionError(f"unexpected start method: {method}")

    fake_mp = types.SimpleNamespace(get_context=fake_get_context)
    monkeypatch.setattr(op_postgres, "mp", fake_mp)

    ctx = op_postgres._get_test_context()
    assert ctx.name == "spawn"
    assert call_order == ["fork", "spawn"]


def test_get_test_context_raises_when_no_method_available(monkeypatch):
    """When neither fork nor spawn is available, _get_test_context raises RuntimeError."""
    call_order = []

    def fake_get_context(method):
        call_order.append(method)
        raise ValueError(f"{method} unavailable")

    fake_mp = types.SimpleNamespace(get_context=fake_get_context)
    monkeypatch.setattr(op_postgres, "mp", fake_mp)

    with pytest.raises(RuntimeError, match="No supported multiprocessing start method is available"):
        op_postgres._get_test_context()

    assert call_order == ["fork", "spawn"]
