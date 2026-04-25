"""Tests for src.main CLI dispatch and mode gating."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src import main as main_mod


def test_live_mode_without_risk_flag_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("MODE", "paper")  # baseline; CLI will override
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))

    with pytest.raises(RuntimeError, match="i-understand-the-risk"):
        main_mod.main(["--check-connection", "--mode", "live"])


def test_live_mode_with_risk_flag_proceeds_to_connection(monkeypatch, tmp_path):
    """With the flag set, mode gate passes and we get to the connection step (which we stub)."""
    monkeypatch.setenv("MODE", "paper")
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))

    fake_check = SimpleNamespace(
        connected=True,
        server_version=178,
        accounts=["DU1234567"],
        net_liquidation=8000.0,
        buying_power=32000.0,
        spy_last=500.0,
        notes=[],
    )

    class _FakeConn:
        def __init__(self, *a, **kw): ...
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def check(self): return fake_check

    monkeypatch.setattr(main_mod, "IBConnection", _FakeConn)

    rc = main_mod.main(["--check-connection", "--mode", "live", "--i-understand-the-risk"])
    assert rc == 0


def test_no_args_returns_nonzero(monkeypatch, tmp_path):
    monkeypatch.setenv("MODE", "paper")
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    rc = main_mod.main([])
    assert rc != 0


def test_check_connection_failure_returns_one(monkeypatch, tmp_path):
    monkeypatch.setenv("MODE", "paper")
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))

    from src.broker.connection import IBConnectionError

    class _FailingConn:
        def __init__(self, *a, **kw): ...
        def __enter__(self): raise IBConnectionError("gateway not running")
        def __exit__(self, *a): return False

    monkeypatch.setattr(main_mod, "IBConnection", _FailingConn)
    rc = main_mod.main(["--check-connection"])
    assert rc == 1
