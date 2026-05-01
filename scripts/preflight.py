"""Preflight check: run before starting the bot.

Verifies environment, config, and external connectivity. Designed to be
the first thing the operator (or Claude Code on the operator's machine)
runs after install.ps1 and before starting the bot for real.

Each check prints PASS/FAIL with a short reason. Exit code is 0 only
when everything passes. Fix the highest-priority FAIL first.

Usage (from repo root):
    .venv\\Scripts\\python.exe scripts\\preflight.py        (Windows)
    .venv/bin/python scripts/preflight.py                    (Mac/Linux)
"""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


class Result:
    def __init__(self):
        self.failures: list[str] = []
        self.warnings: list[str] = []

    def ok(self, name: str, detail: str = "") -> None:
        print(f"  {GREEN}PASS{RESET}  {name}" + (f"  ({detail})" if detail else ""))

    def fail(self, name: str, detail: str) -> None:
        print(f"  {RED}FAIL{RESET}  {name}  ({detail})")
        self.failures.append(f"{name}: {detail}")

    def warn(self, name: str, detail: str) -> None:
        print(f"  {YELLOW}WARN{RESET}  {name}  ({detail})")
        self.warnings.append(f"{name}: {detail}")


def check_python_version(r: Result) -> None:
    v = sys.version_info
    if (v.major, v.minor) >= (3, 11):
        r.ok("Python version", f"{v.major}.{v.minor}.{v.micro}")
    else:
        r.fail("Python version", f"need 3.11+, have {v.major}.{v.minor}")


def check_venv(r: Result) -> None:
    in_venv = sys.prefix != sys.base_prefix or hasattr(sys, "real_prefix")
    if in_venv:
        r.ok("Running in venv", sys.prefix)
    else:
        r.warn("Running in venv",
               "not detected; OK if you're using system Python deliberately")


def check_dependencies(r: Result) -> None:
    """Don't import ib_insync (heavy); just verify it's installed."""
    import importlib.util
    required = ["pandas", "numpy", "loguru", "dotenv", "httpx", "pydantic"]
    missing = []
    for mod in required:
        if importlib.util.find_spec(mod) is None:
            missing.append(mod)
    if missing:
        r.fail("Dependencies", f"missing: {', '.join(missing)}. Run: pip install -e .")
    else:
        r.ok("Dependencies", "all present")

    # ib_insync separately (only matters for live runs)
    if importlib.util.find_spec("ib_insync") is None:
        r.fail("ib_insync", "missing; needed to connect to Gateway. Run: pip install -e .")
    else:
        r.ok("ib_insync", "installed")


def check_env_file(r: Result) -> dict:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        r.fail(".env file", f"not found at {env_path}. Copy .env.example to .env and fill it in.")
        return {}
    r.ok(".env file", str(env_path))

    # Parse without dotenv to avoid masking actual env loading
    settings = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            settings[k.strip()] = v.split("#", 1)[0].strip()

    # Required for live connection
    if settings.get("MODE", "").lower() == "live":
        r.warn("MODE", "set to 'live' — bot will refuse without --i-understand-the-risk flag")
    elif settings.get("MODE", "").lower() == "paper":
        r.ok("MODE", "paper")
    else:
        r.fail("MODE", f"must be 'paper' or 'live', got {settings.get('MODE')!r}")

    # IBKR connection params
    port = settings.get("IBKR_PORT", "")
    if port == "4002":
        r.ok("IBKR_PORT", "4002 (Gateway paper)")
    elif port in ("4001", "7496", "7497"):
        r.warn("IBKR_PORT", f"{port} — check this matches your Gateway/TWS")
    else:
        r.fail("IBKR_PORT", f"unexpected value {port!r}; should be 4002 for Gateway paper")

    # Calendar provider
    provider = settings.get("ECON_CALENDAR_PROVIDER", "stub").lower()
    if provider == "fmp":
        if settings.get("FMP_API_KEY"):
            r.ok("Calendar provider", "fmp + key set")
        else:
            r.fail("Calendar provider",
                   "ECON_CALENDAR_PROVIDER=fmp but FMP_API_KEY is empty")
    elif provider == "stub":
        r.warn("Calendar provider",
               "stub (event-blackout disabled — set to 'fmp' before going live)")
    else:
        r.fail("Calendar provider", f"unknown: {provider!r}")

    return settings


def check_gateway_socket(host: str, port: int, r: Result) -> None:
    """TCP connect — does NOT initiate IB API handshake. Just confirms
    something is listening on the configured port.
    """
    try:
        with socket.create_connection((host, port), timeout=3.0):
            r.ok("Gateway socket", f"{host}:{port} reachable")
    except OSError as exc:
        r.fail("Gateway socket",
               f"cannot connect to {host}:{port} ({exc.__class__.__name__}). "
               f"Is Gateway running and logged into paper?")


def check_fmp(api_key: str, r: Result) -> None:
    if not api_key:
        return
    import httpx
    try:
        resp = httpx.get(
            "https://financialmodelingprep.com/stable/economic-calendar",
            params={"from": "2026-01-01", "to": "2026-01-02", "apikey": api_key},
            timeout=10.0,
        )
        if resp.status_code != 200:
            r.fail("FMP API", f"HTTP {resp.status_code}")
            return
        data = resp.json()
        if isinstance(data, dict) and "Error Message" in data:
            r.fail("FMP API", data["Error Message"])
        else:
            r.ok("FMP API", f"key works ({len(data) if isinstance(data, list) else '?'} events for sample window)")
    except Exception as exc:
        r.fail("FMP API", f"{exc!r}")


def check_writable_dirs(r: Result) -> None:
    for d in ("logs", "state", "reports"):
        p = REPO_ROOT / d
        try:
            p.mkdir(parents=True, exist_ok=True)
            test = p / ".preflight"
            test.write_text("ok")
            test.unlink()
            r.ok(f"{d}/ writable", str(p))
        except OSError as exc:
            r.fail(f"{d}/ writable", f"{p}: {exc}")


def check_git(r: Result) -> None:
    """Confirm we can git-push without a prompt (eod_push needs this)."""
    import subprocess
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=5,
        )
        if out.returncode != 0:
            r.fail("Git", "not a git repo or git not on PATH")
            return
        branch = out.stdout.strip()
        if branch == "main":
            r.warn("Git branch",
                   "on main; EOD push will refuse. Switch to your dev branch.")
        else:
            r.ok("Git branch", branch)

        # Check that origin is set
        origin = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=5,
        )
        if origin.returncode == 0:
            r.ok("Git origin", origin.stdout.strip())
        else:
            r.warn("Git origin", "no origin remote set; eod_push won't work")
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        r.fail("Git", f"{exc!r}")


def main() -> int:
    r = Result()
    print("=== IBKR Trading Bot — Preflight ===")
    print()
    print("[Environment]")
    check_python_version(r)
    check_venv(r)
    check_dependencies(r)
    check_writable_dirs(r)
    print()

    print("[Configuration]")
    settings = check_env_file(r)
    print()

    print("[Connectivity]")
    if settings:
        host = settings.get("IBKR_HOST", "127.0.0.1")
        try:
            port = int(settings.get("IBKR_PORT", "4002"))
            check_gateway_socket(host, port, r)
        except ValueError:
            r.fail("Gateway socket", "IBKR_PORT not an integer")
        check_fmp(settings.get("FMP_API_KEY", ""), r)
    print()

    print("[Repository]")
    check_git(r)
    print()

    print("=== Summary ===")
    if r.failures:
        print(f"{RED}{len(r.failures)} failure(s):{RESET}")
        for f in r.failures:
            print(f"  - {f}")
    if r.warnings:
        print(f"{YELLOW}{len(r.warnings)} warning(s):{RESET}")
        for w in r.warnings:
            print(f"  - {w}")
    if not r.failures and not r.warnings:
        print(f"{GREEN}All checks passed.{RESET}")
        return 0
    if r.failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
