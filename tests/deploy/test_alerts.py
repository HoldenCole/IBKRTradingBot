"""Tests for the alerting layer. CapturingAlerter for behavior; SmtpAlerter
mocked so no real email is sent."""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from src.deploy.alerts import (
    Alert, AlertSeverity, CapturingAlerter, SmtpAlerter,
    alert_critical, alert_daily_summary, alert_for_order,
    alert_for_state_change,
)
from src.deploy.broker import OrderState, OrderTicket, OrderType
from src.deploy.signal_state import SignalSnapshot, SignalState, StateChange


def _snap(state: SignalState, as_of: date = date(2024, 6, 20)) -> SignalSnapshot:
    return SignalSnapshot("qqq", as_of, state, close=540.0,
                          sma50=525.0, sma200=510.0)


# ===== CapturingAlerter =====

def test_capturing_alerter_stores_alerts():
    a = CapturingAlerter()
    sent = a.send(Alert(AlertSeverity.INFO, "test", "body"))
    assert sent is True
    assert len(a.sent) == 1
    assert a.sent[0].title == "test"
    assert a.sent[0].sent_at is not None


# ===== Builders =====

def test_alert_for_state_change_enter():
    ch = StateChange("qqq", SignalState.OFF, SignalState.ON,
                     date(2024, 6, 19), date(2024, 6, 20))
    alert = alert_for_state_change(ch, _snap(SignalState.ON))
    assert alert.severity == AlertSeverity.INFO
    assert "ENTER" in alert.title
    assert "OFF -> ON" in alert.title
    assert "close=540.00" in alert.body
    assert "sma50=525.00" in alert.body


def test_alert_for_state_change_exit():
    ch = StateChange("qqq", SignalState.ON, SignalState.OFF,
                     date(2024, 6, 19), date(2024, 6, 20))
    alert = alert_for_state_change(ch, _snap(SignalState.OFF))
    assert "EXIT" in alert.title


def test_alert_for_order_rejected_is_critical():
    t = OrderTicket("O-1", "QQQ", "BUY", 10, OrderType.MOO,
                    OrderState.REJECTED, note="insufficient cash")
    alert = alert_for_order(t)
    assert alert.severity == AlertSeverity.CRITICAL
    assert "insufficient cash" in alert.body


def test_alert_for_order_submitted_is_info():
    t = OrderTicket("O-1", "QQQ", "BUY", 10, OrderType.MOO, OrderState.SUBMITTED)
    alert = alert_for_order(t)
    assert alert.severity == AlertSeverity.INFO


def test_daily_summary_with_warnings_is_warning_severity():
    snaps = {"qqq": _snap(SignalState.ON), "btc": _snap(SignalState.OFF)}
    alert = alert_daily_summary(date(2024, 6, 20), snaps, flip_count=1,
                                 warnings=["data feed slow"])
    assert alert.severity == AlertSeverity.WARNING
    assert "data feed slow" in alert.body
    assert "flips=1" in alert.body


def test_daily_summary_no_warnings_is_info():
    snaps = {"qqq": _snap(SignalState.ON)}
    alert = alert_daily_summary(date(2024, 6, 20), snaps, flip_count=0,
                                 warnings=[])
    assert alert.severity == AlertSeverity.INFO


def test_alert_critical_builder():
    a = alert_critical("Broker unreachable", "ib_insync connect failed 3x")
    assert a.severity == AlertSeverity.CRITICAL


# ===== SmtpAlerter — mocked transport =====

def test_smtp_from_env_returns_none_without_host(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert SmtpAlerter.from_env() is None


def test_smtp_from_env_with_minimal_config(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("ALERT_TO", "you@example.com,me@example.com")
    a = SmtpAlerter.from_env()
    assert a is not None
    assert a.smtp_host == "smtp.example.com"
    assert a.alert_to == ["you@example.com", "me@example.com"]


def test_smtp_send_does_not_raise_on_smtp_failure():
    """If the SMTP server is unreachable, send() must return False rather
    than crash the daily-check job."""
    a = SmtpAlerter(smtp_host="invalid.invalid", smtp_port=587,
                    smtp_user="u", smtp_password="p", alert_from="f@x.com",
                    alert_to=["t@x.com"])
    result = a.send(Alert(AlertSeverity.INFO, "test", "body"))
    assert result is False


def test_smtp_send_calls_send_message(monkeypatch):
    """Verify the actual send-message path is invoked when SMTP works."""
    captured: dict = {}

    class FakeSMTP:
        def __init__(self, host, port):
            captured["host"] = host
            captured["port"] = port
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def starttls(self, context=None):
            captured["tls"] = True
        def login(self, u, p):
            captured["login"] = (u, p)
        def send_message(self, msg):
            captured["msg_subject"] = msg["Subject"]

    import src.deploy.alerts as alerts_module
    monkeypatch.setattr(alerts_module.smtplib, "SMTP", FakeSMTP)

    a = SmtpAlerter(smtp_host="smtp.example.com", smtp_port=587,
                    smtp_user="u", smtp_password="p", alert_from="f@x.com",
                    alert_to=["t@x.com"])
    ok = a.send(Alert(AlertSeverity.INFO, "hello", "world"))
    assert ok is True
    assert captured["host"] == "smtp.example.com"
    assert "[INFO] hello" in captured["msg_subject"]
    assert captured["tls"] is True
    assert captured["login"] == ("u", "p")
