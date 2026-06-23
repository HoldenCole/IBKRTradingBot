"""Alerting layer — notifications on filter state changes and operational events.

LOCKED DECISIONS (per Operational Spec):
  - One channel for paper. We support email (SMTP) and a CapturingAlerter
    for tests. SMS/Discord can be added without touching consumers.
  - Alerts on:
      * filter state changes (per sleeve flip ON/OFF)
      * order placed
      * order filled (or rejected)
      * daily check ran (one summary per day)
      * critical operational failures (data feed down, broker unreachable)
  - Failure-mode for the alerter itself: must NOT crash the daily-check
    job. If SMTP is unreachable, log the failure and continue. The
    alerter is best-effort; the source of truth is the persisted state
    file + the trade log.

What this module does NOT do:
  - retry alerts (a missed alert is logged once and moves on; alerts are
    not durable; if reliability matters later, swap in a queued backend)
  - format prose templates (alerts use compact key=value bodies — for
    Stage-1 single-user paper, this is enough)
  - rate-limiting / batching (one alert per event; volume is < 1/day
    in normal operation)
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import date, datetime
from email.message import EmailMessage
from enum import Enum
from typing import Protocol

from src.deploy.broker import OrderTicket
from src.deploy.signal_state import SignalSnapshot, StateChange

_log = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    INFO = "info"          # daily summary, normal flips
    WARNING = "warning"    # warmup-still-pending, data-feed degraded
    CRITICAL = "critical"  # broker unreachable, order rejected


@dataclass
class Alert:
    """A single alert event. Compact key=value body."""
    severity: AlertSeverity
    title: str
    body: str
    sent_at: datetime | None = None


class Alerter(Protocol):
    def send(self, alert: Alert) -> bool: ...


# =====================================================================
# Implementations
# =====================================================================
@dataclass
class CapturingAlerter:
    """Stores alerts in memory. Used by tests; also by the daily-check
    --dry-run mode where you want to preview what would be sent."""
    sent: list[Alert] = field(default_factory=list)

    def send(self, alert: Alert) -> bool:
        alert.sent_at = datetime.utcnow()
        self.sent.append(alert)
        _log.info("ALERT [%s] %s: %s", alert.severity.value,
                  alert.title, alert.body)
        return True


@dataclass
class SmtpAlerter:
    """Email-via-SMTP alerter. Best-effort: catches all exceptions and
    returns False rather than propagating. Credentials read from
    environment variables to avoid committing secrets:
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
      ALERT_FROM, ALERT_TO (comma-separated)

    Use TLS via STARTTLS by default; falls back to SMTP_SSL if SMTP_SSL=1.
    """
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    alert_from: str
    alert_to: list[str]
    use_ssl: bool = False

    @classmethod
    def from_env(cls) -> "SmtpAlerter | None":
        import os
        host = os.environ.get("SMTP_HOST")
        if not host:
            return None
        return cls(
            smtp_host=host,
            smtp_port=int(os.environ.get("SMTP_PORT", "587")),
            smtp_user=os.environ.get("SMTP_USER", ""),
            smtp_password=os.environ.get("SMTP_PASSWORD", ""),
            alert_from=os.environ.get("ALERT_FROM", os.environ.get("SMTP_USER", "")),
            alert_to=[a.strip() for a in os.environ.get("ALERT_TO", "").split(",") if a.strip()],
            use_ssl=os.environ.get("SMTP_SSL", "") == "1",
        )

    def send(self, alert: Alert) -> bool:
        msg = EmailMessage()
        msg["Subject"] = f"[{alert.severity.value.upper()}] {alert.title}"
        msg["From"] = self.alert_from
        msg["To"] = ", ".join(self.alert_to)
        msg.set_content(alert.body)
        try:
            if self.use_ssl:
                ctx = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=ctx) as s:
                    if self.smtp_user:
                        s.login(self.smtp_user, self.smtp_password)
                    s.send_message(msg)
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as s:
                    s.starttls(context=ssl.create_default_context())
                    if self.smtp_user:
                        s.login(self.smtp_user, self.smtp_password)
                    s.send_message(msg)
            alert.sent_at = datetime.utcnow()
            _log.info("alert sent: %s", alert.title)
            return True
        except Exception as exc:
            _log.exception("SMTP send failed for alert %r: %r", alert.title, exc)
            return False


# =====================================================================
# Builders — make alerts from domain events
# =====================================================================
def alert_for_state_change(ch: StateChange, snap: SignalSnapshot) -> Alert:
    """Compose an alert for a filter flip. INFO severity for normal flips;
    non-flip state changes (UNKNOWN->X) get no alert (they're not
    tradeable events)."""
    title = (f"{ch.strategy_id} {ch.direction.upper()}: "
             f"{ch.prev_state.value} -> {ch.new_state.value}")
    sma50_s = f"{snap.sma50:.2f}" if snap.sma50 is not None else "n/a"
    sma200_s = f"{snap.sma200:.2f}" if snap.sma200 is not None else "n/a"
    body = (
        f"strategy={ch.strategy_id}\n"
        f"as_of={snap.as_of}\n"
        f"direction={ch.direction}\n"
        f"prev_state={ch.prev_state.value}\n"
        f"new_state={ch.new_state.value}\n"
        f"close={snap.close:.2f}\n"
        f"sma50={sma50_s}\n"
        f"sma200={sma200_s}\n"
        f"next_action=MOO order will be submitted for next session open"
    )
    return Alert(severity=AlertSeverity.INFO, title=title, body=body)


def alert_for_order(ticket: OrderTicket) -> Alert:
    title = (f"{ticket.order_type.value} {ticket.side} "
             f"{ticket.quantity:g} {ticket.symbol} -> {ticket.state.value}")
    body = (
        f"order_id={ticket.order_id}\n"
        f"symbol={ticket.symbol}\n"
        f"side={ticket.side}\n"
        f"quantity={ticket.quantity}\n"
        f"order_type={ticket.order_type.value}\n"
        f"state={ticket.state.value}\n"
        f"avg_fill_price={ticket.avg_fill_price}\n"
        f"filled_quantity={ticket.filled_quantity}\n"
        f"note={ticket.note}\n"
    )
    sev = (AlertSeverity.CRITICAL if ticket.state.value == "rejected"
           else AlertSeverity.INFO)
    return Alert(severity=sev, title=title, body=body)


def alert_daily_summary(
    trading_date: date,
    snapshots: dict[str, SignalSnapshot],
    flip_count: int,
    warnings: list[str],
) -> Alert:
    lines = [f"trading_date={trading_date}",
             f"flips={flip_count}",
             f"warnings={len(warnings)}"]
    for sid, snap in sorted(snapshots.items()):
        lines.append(f"  {sid}: state={snap.state.value} close={snap.close:.2f}")
    for w in warnings:
        lines.append(f"  WARNING: {w}")
    sev = AlertSeverity.WARNING if warnings else AlertSeverity.INFO
    return Alert(severity=sev,
                 title=f"Daily check {trading_date}: {flip_count} flips",
                 body="\n".join(lines))


def alert_critical(title: str, body: str) -> Alert:
    return Alert(severity=AlertSeverity.CRITICAL, title=title, body=body)
