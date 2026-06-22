"""Deployment layer — basket architecture, position sizing, daily-check.

Separate from the research code (src/commodity, src/crypto) and the
abandoned options-runner (src/runner, src/strategies). This package holds
the operational system for the VALIDATED strategy: static 50/50 QQQ-trend +
BTC-trend with config-driven basket weights.
"""
