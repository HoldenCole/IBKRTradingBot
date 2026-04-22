# IBKR Trading Bot

An algorithmic trading bot that connects to Interactive Brokers (IBKR) for strategy research, paper trading, and eventual live execution. Built to run options and futures strategies on a retail-sized account.

> **Note for Claude Code:** This README is your project context. Read it fully before making changes. When in doubt about safety rules, ask before acting — especially anything that could touch live money.

---

## Project Goals

- Connect to IBKR via the TWS/Gateway API using `ib_insync`
- Run and evaluate trading strategies against the **paper account** first
- Provide a clean framework where new strategies can be dropped in without rewriting plumbing
- Log everything: orders, fills, errors, PnL, signal decisions
- Graduate to small live trading only after a strategy proves out in paper

**Account context:** ~$8k initial capital, IBKR Pro account, approved for options and futures.

---

## Tech Stack

- **Python 3.11+**
- **`ib_insync`** — async-friendly wrapper over the IBKR API
- **`pandas`** — data handling
- **`pytest`** — tests
- **`python-dotenv`** — config
- **`loguru`** — logging (structured, rotating)

Keep dependencies lean. If a new library is needed, justify it in the PR.

---

## Project Structure

```
.
├── README.md
├── .env.example              # template — never commit real .env
├── pyproject.toml
├── src/
│   ├── config.py             # loads env vars, validates settings
│   ├── broker/
│   │   ├── connection.py     # IB() wrapper, reconnect logic
│   │   └── orders.py         # order helpers with safety checks
│   ├── strategies/
│   │   ├── base.py           # Strategy abstract base class
│   │   └── <your_strategy>.py
│   ├── data/
│   │   └── market_data.py    # historical + streaming data
│   ├── risk/
│   │   └── guardrails.py     # position size, max loss, kill switch
│   └── main.py               # entrypoint
├── tests/
│   └── test_*.py
├── logs/                     # gitignored, auto-created
└── notebooks/                # exploratory work, gitignored
```

---

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in:

```
IBKR_HOST=127.0.0.1
IBKR_PORT=4002              # 4002 = Gateway paper, 4001 = Gateway live, 7497 = TWS paper, 7496 = TWS live
IBKR_CLIENT_ID=1
MODE=paper                  # paper | live — live requires explicit override
LOG_LEVEL=INFO
MAX_POSITION_USD=500        # per-position cap
MAX_DAILY_LOSS_USD=200      # kill switch triggers if breached
```

### 3. Configure IB Gateway

Open IB Gateway (paper login) → Configure → Settings → API → Settings:

- ☑ Enable ActiveX and Socket Clients
- ☐ Read-Only API (must be **unchecked**)
- Socket port: **4002**
- Trusted IPs: add `127.0.0.1`
- Save and restart Gateway

### 4. Verify connection

```bash
python -m src.main --check-connection
```

Expected output: account summary, a test SPY quote, and `Connected: True`.

---

## Running a Strategy

```bash
# Paper mode (default, safe)
python -m src.main --strategy my_strategy

# Backtest against historical data
python -m src.main --strategy my_strategy --backtest --from 2025-01-01 --to 2025-12-31

# Live mode — intentionally requires an extra flag
python -m src.main --strategy my_strategy --mode live --i-understand-the-risk
```

---

## Writing a New Strategy

All strategies inherit from `Strategy` in `src/strategies/base.py`:

```python
from src.strategies.base import Strategy, Signal

class MyStrategy(Strategy):
    name = "my_strategy"

    def on_bar(self, bar) -> Signal | None:
        # return a Signal (BUY/SELL/CLOSE + size + reason)
        # or None to do nothing
        ...

    def on_fill(self, fill) -> None:
        # called when an order fills
        ...
```

The framework handles connection, data subscriptions, order routing, logging, and guardrails. The strategy file should only contain signal logic.

---

## Safety Rules (Non-Negotiable)

These rules exist because a trading bug costs real money. **Claude Code must follow these without exception:**

1. **Default to paper.** `MODE=paper` is the default. Live mode requires `--mode live --i-understand-the-risk` AND the user's explicit confirmation in chat.
2. **Every order goes through `src/broker/orders.py`.** That module enforces:
   - Position size cap (`MAX_POSITION_USD`)
   - Daily loss kill switch (`MAX_DAILY_LOSS_USD`)
   - Sanity checks (no zero-price orders, no orders outside trading hours unless explicitly allowed)
3. **Log every decision.** Signals, orders placed, fills, rejections, errors. Logs rotate daily in `logs/`.
4. **No silent failures.** Exceptions bubble up. The bot halts on anything it doesn't understand rather than guessing.
5. **Backtests are not proof.** A strategy must run in paper for a meaningful sample before any live discussion.
6. **Ask before destructive changes.** Canceling open orders, closing positions, changing risk parameters — confirm with the user first when running interactively.

---

## Operational Gotchas

- **Nightly Gateway restart** ~11:45 PM ET. The bot must detect disconnection and reconnect, or exit cleanly and be restarted by a supervisor (e.g., `systemd`, `supervisord`).
- **Weekly 2FA re-auth** on IB Gateway. For unattended operation, look into IBC (IB Controller) — but not until the strategy is proven.
- **Paper market data is delayed** by default. Subscribe to real-time data on the live account and it flows through to paper.
- **Client ID collisions.** Each connection needs a unique `clientId`. Running two scripts with `clientId=1` will silently kick one off.
- **Contract qualification.** Always call `ib.qualifyContracts(...)` before using a contract — IBKR needs the conId resolved.
- **Futures contract months.** Continuous futures (`ContFuture`) are for historical data only. Trading requires a specific contract month (e.g., `ESM6` for June 2026 E-mini S&P).
- **Pattern Day Trader rule.** Eliminated by the SEC on April 14, 2026, but full broker implementation phases in over up to 18 months. Don't assume it's gone on your account yet — check IBKR's rollout status.

---

## Testing

```bash
pytest                      # run all tests
pytest tests/test_risk.py   # run one file
pytest -k guardrail         # run matching tests
```

Strategy logic should be tested against mock bars/ticks. Broker integration tests use the paper account and are marked `@pytest.mark.integration` — skipped by default.

---

## Roadmap

- [ ] Connection + account summary smoke test
- [ ] Market data subscription (stocks, options chains, futures)
- [ ] Strategy base class + example strategy (e.g., opening-range breakout on MES)
- [ ] Historical data fetcher for backtests
- [ ] Simple backtest engine (bar-level, no tick simulation)
- [ ] Risk guardrails module with unit tests
- [ ] Structured logging with daily rotation
- [ ] Paper run of first real strategy
- [ ] Reconnection + nightly restart handling
- [ ] Performance dashboard (PnL, drawdown, trade log)

---

## Disclaimer

This is personal research software. Nothing in this repo is financial advice. Automated trading can lose money faster than manual trading — including more than the account balance when leverage is involved. The author and any contributors (including AI assistants) accept no responsibility for losses.
