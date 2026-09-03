# Automation Runbook — hands-off execution

The executor (`src/execution/rotation_executor.py`) turns the monthly
system into a cron job: it runs the screener if the month's ledger row
doesn't exist yet, reads live account state from IB Gateway, diffs
against the tier's target weights with the adopted rules
(contribution-first, 5pp drift band, full exit of departed tickers),
places limit orders (sells first, mid-price, repriced through the
spread once if unfilled), and appends every order to
`paper/executions.csv`. It is state-based: running it twice does
nothing the second time, and a partially-filled month is finished by
the next run.

**What "hands-off" honestly means here:** the system trades ~15
minutes a month, so the automation's job is reliability, not speed.
Your remaining monthly involvement is reading one summary line and
funding the account. Plan for ~10 minutes a week of glancing at logs
for the first three months, then nearly zero.

## The box

IBKR only accepts API orders through a running IB Gateway, so the loop
needs an always-on machine. Any of these work:

- A used mini-PC (~$100-150, recommended — fully yours, no monthly cost)
- A Raspberry Pi 4/5 (Gateway runs on ARM via the standalone Java build)
- A small VPS (~$5-10/mo; understand you're putting broker credentials
  on rented hardware — use IBKR's IP restriction setting)

Requirements: Linux, Java 17+, Python 3.11+, ~2GB RAM.

## One-time setup

1. **Clone the repo** on the box; `pip install -e .` (pulls ib_insync,
   pandas, loguru).
2. **IB Gateway** (offline installer from IBKR) + **IBC**
   (github.com/IbcAlpha/IBC) to automate login and the daily restart.
   Configure IBC with your username; store the password in IBC's
   config (chmod 600), enable auto-restart.
3. **2FA**: in IBKR Mobile, enable IB Key. Then in Client Portal →
   Settings → Secure Login System, opt into the reduced 2FA regime for
   Gateway sessions. Reality check: IBKR forces a full re-auth
   ~weekly; IBC handles the daily restart but the weekly one needs a
   tap on your phone. This is the one hard limit on "fully" hands-off
   — budget one phone tap a week.
4. **Ports**: Gateway paper = 4002, live = 4001. `.env` on the box:
   `IBKR_PORT=4002` (paper) until promotion; `MODE=live` only at
   promotion.
5. **Account settings** (Client Portal): fractional shares ON, Tax
   Optimizer → HIFO, leveraged-ETF permission signed, recurring
   monthly ACH deposit, dividends paid as cash, API access enabled in
   Gateway config (trusted IP 127.0.0.1).
6. **Dedicated account.** The executor ignores and never counts
   positions outside the rotation universe, but keep this account
   single-purpose anyway — separation is what makes the ledger
   comparison clean.

## Schedule (crontab, box set to America/New_York)

```cron
# Rotation: first trading day of the month, 15:40 ET (equity buys near
# the close per the overnight study). Runs on the 1st-3rd; the
# state-based design makes the extra runs no-ops once positions match.
40 15 1-3 * 1-5  cd /home/bot/IBKRTradingBot && python -m src.execution.rotation_executor --tier VAGG --execute >> logs/rotation.log 2>&1

# Contribution deploy: mid-month, after the ACH lands and settles.
40 15 15-17 * 1-5  cd /home/bot/IBKRTradingBot && python -m src.execution.rotation_executor --tier VAGG --execute >> logs/rotation.log 2>&1

# Weekly read-only regime watch (Mondays): distance-to-boundary +
# provisional quadrant, logs to paper/watch.csv, trades nothing.
10 9 * * 1  cd /home/bot/IBKRTradingBot && python -m src.portfolio.watch >> logs/watch.log 2>&1

# Ledger + git push (keeps the paper trail off-box too)
0 18 1-3 * 1-5  cd /home/bot/IBKRTradingBot && git add paper/ && git commit -m "ledger/executions $(date +\%F)" && git push
```

Add a healthchecks.io ping (`&& curl -fsS https://hc-ping.com/<uuid>`)
to the rotation line — you get an email if the job ever *doesn't* run,
which is the failure mode silent automation actually has.

## Staged go-live (do not skip stages)

1. **Stage 1 — dry-run against your funded account** (now): Gateway
   logged into the LIVE account, executor WITHOUT `--execute`. It
   reads real balances and logs exactly what it would trade, placing
   nothing. Run one month. Verify `paper/executions.csv` matches what
   you'd have done by hand.
2. **Stage 2 — paper account execution** (optional but cheap): Gateway
   on port 4002 with IBKR's paper account, `--execute` on. Verifies
   fills, fractional orders, and the reprice path end-to-end.
3. **Stage 3 — live**: `MODE=live`, port 4001, `--execute
   --i-understand-the-risk` in the cron line. Start at the September
   row you've already verified by hand.

## Controls

- **Kill switch**: `touch HALT` in the repo root (or set
  `EXECUTION_HALT=1`). Every subsequent run aborts before reading
  anything. Remove the file to resume.
- **Shorts off**: `INCLUDE_SHORTS=False` in `src/portfolio/matrix.py`
  — next ledger row resolves long-only, executor follows.
- **Abort conditions** (no orders placed): HALT present, no ledger row
  for the month, open orders already working, weights don't sum to 1,
  buys exceed equity, bad quotes.
- **Audit trail**: `paper/ledger.csv` = what the model decided;
  `paper/executions.csv` = what the account did about it. The gap
  between them is the execution report card (DEPLOYMENT.md,
  "Measuring yourself honestly").

## What stays manual, by design

- The weekly IB Key tap (IBKR's rule, not ours).
- Reading the monthly summary — know what your money is doing.
- Tier changes, matrix version changes, and the annual glide-path
  review: the executor executes; it never decides policy.
