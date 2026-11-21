# IBKR Trading Bot: regime rotation, research log and weekly report

A personal investing system built on Interactive Brokers. It began as an intraday oil-arbitrage bot. That idea
failed its first honest backtest, and the project became what it is now:

1. **A monthly regime-rotation portfolio.** Two market dials pick one of four macro regimes each month. Each regime
   maps to a fixed book of ETFs for each of four risk tiers.
2. **A research log.** More than 87 ideas tested against two separate 20-year eras. Every verdict is recorded.
3. **Quadrant Balances.** A trend and cycle tool on daily, weekly and monthly bars that flags whether the long
   equity cycle is intact, breaking or washed out.
4. **Quadrant Weekly.** A nine-page research PDF built every Saturday, written to be passed around.

> **Note for Claude Code (or anyone starting fresh):** this file is the project context. Read it fully, then
> `TESTS.md`, before proposing or changing anything. The section "Working rules" near the end is binding.
> All work lives on the branch `claude/trading-bot-cl1-uso-spread-02qa7h`. If you are on `main` and the
> folders `src/portfolio`, `research` and `report` are missing, you are on the wrong branch.

---

## 1. Start here

Read in this order.

| File | What it is |
|---|---|
| `README.md` | This file: context, the system, the process, the rules |
| `TESTS.md` | The registry. One line per idea ever tested, with its verdict (adopted, rejected, filed) |
| `PORTFOLIOS.md` | The full evidence behind every line in `TESTS.md`, in date order. Long. Search it, do not skim it |
| `REGIMES.md` | The four-regime framework and what each regime has paid |
| `DEPLOYMENT.md` | The manual runbook: account settings, day one, the monthly routine |
| `AUTOMATION.md` | The hands-off executor, its cron schedule and staged go-live |
| `report/README.md` | How the weekly PDF is built and what may go in it |
| `STRATEGIES.md`, `CL1_USO_STRATEGY.md`, `CL_SURGE_CALLS.md`, `BIOTECH_CATALYST.md`, `COMMODITY_TREND_RESULTS.md` | Earlier strategy specs and their test results (section 10) |

Data that must never be rewritten: everything under `paper/` (section 5).

---

## 2. Who this is for

- One investor, mid-twenties, with a multi-decade horizon and regular monthly contributions.
- A taxable IBKR Pro account with fractional shares, HIFO tax lots, and options and futures approval.
- A small retail account. Account size is deliberately not stored in this repo or in any file it generates.
  Tools that need it take it as an input.
- **Live tier: AGG** (aggressive). The live account started on 1 September 2026. The paper ledger started on
  20 August 2026 and keeps running as the benchmark the live account is measured against.
- Background: the investor previously worked on a desk that used a "trend and cycle / quadrant balances" tool.
  Section 6 is that tool, rebuilt.

---

## 3. The system

### The classifier

Two dials, read once a month on completed month-end closes. No tuning, no publication lag.

- **Growth dial:** on when SPY closes the month above the average of its prior nine month-end closes
  (the 10-month moving-average rule).
- **Inflation dial:** on when DBC (broad commodities) does the same.
- The reading at the end of month T-1 sets the regime for all of month T. If history is missing it fails closed.

| Regime | Growth | Inflation | Share of months (2007-2026) | Average run |
|---|---|---|---|---|
| GROWTH | on | off | 32% | 3.2 months |
| REFLATION | on | on | 47% | 5.3 months |
| STAGFLATION | off | on | 8% | 2.7 months |
| DEFLATION | off | off | 13% | 2.3 months |

What each regime paid in the following month, annualised, 2007-2026 (`REGIMES.md`):

| Regime | SPY | QQQ | Oil (USO) | Commodities (DBC) | Gold | Long Treasuries |
|---|---|---|---|---|---|---|
| Growth | +14.9% | +22.3% | −1.8% | −1.4% | +6.6% | +6.4% |
| Reflation | +7.4% | +9.5% | +15.6% | +11.7% | +13.6% | +0.5% |
| Stagflation | −10.7% | −6.0% | −8.4% | −7.9% | −7.5% | +4.2% |
| Deflation | +31.4% | +44.3% | −28.4% | −3.3% | +24.6% | +8.5% |

Two lessons from that table shaped everything. In stagflation nothing works except bonds and cash. Deflation
months hide violent equity rebounds, because the classifier lags the low.

### The four risk tiers

MOD defines what each regime owns. CONS dilutes it with cash. AGG and VAGG add leverage, nothing else.
The ladder is monotonic: more risk, more return, in almost every regime and era.

### The matrix, version 9 (`src/portfolio/matrix.py`)

Weights in percent. All holdings are ordinary ETFs.

| Tier | Growth | Reflation | Stagflation | Deflation |
|---|---|---|---|---|
| **CONS** | SPY 40, IEF 40, GLD 20 | SPY 21, XLE 17.5, GLD 17.5, DBC 14, SHY 30 | SHY 60, duration 40 | TLT 40, SHY 25, GLD 25, SPY 10 |
| **MOD** | QQQ 70, IEF 30 | SPY 30, XLE 25, GLD 25, DBC 20 | SHY 40, short energy 10, duration 50 | TLT 35, short oil 10, GLD 30, XLP 15, SPY 10 |
| **AGG** | QLD 100 | QQQ 30, ERX 25, GLD 25, DBC 20 | SHY 25, short energy 15, duration 60 | TLT 25, short oil 15, TMF 15, GDX 30, QQQ 15 |
| **VAGG** | TQQQ 100 | TQQQ 30, ERX 25, GLD 25, DBC 20 | SHY 15, short energy 15, duration 70 | TMF 35, TLT 5, short oil 15, GDX 30, QLD 15 |

Four signals resolve those cells into the month's actual book:

- **Conditional duration (stagflation).** "Duration" becomes TLT when TLT is above its own 10-month average,
  otherwise SHY.
- **Momentum tilt (reflation).** The three real-asset lines (energy, gold, commodities) are re-weighted
  45 / 32.5 / 22.5 by trailing six-month return.
- **Shorts through inverse ETFs.** "Short oil" is SCO and "short energy" is ERY, each at half the sleeve weight
  with SHY for the rest. No margin, no borrow. One switch, `INCLUDE_SHORTS`, turns the whole short book off.
- **Washout rebound (deflation).** When fewer than 25% of 18 sectors are above their 10-month average, the
  equity slice in the deflation cell grows by up to 10 points, funded from TLT. Not in CONS.

### Official numbers

Matrix v9, January 2007 to September 2026, from `research/official_stats.py`
(stored in `research/evidence_current.json`):

| | CAGR | Sortino | Worst drawdown |
|---|---|---|---|
| CONS | +9.8% | 1.62 | −10.2% |
| MOD | +15.4% | 1.73 | −14.3% |
| AGG | +27.3% | 1.41 | −33.1% |
| VAGG | +35.3% | 1.22 | −46.8% |
| SPY | +11.0% | 0.69 | −55.2% |

**Read these honestly.** The cell contents were designed after seeing the modern sample, so tier-level numbers
are upward-biased. What has been validated out of sample, on 1987-2006, is the framework: the switch and the
cell structure deliver index-like returns at roughly a third of the drawdown. Backtests ignore taxes and costs.
Leveraged ETFs decay in choppy markets.

### How the matrix got here

| Version | Change |
|---|---|
| v1, v2 | Canon-grounded playbook, then the monotonic tier ladder |
| v3 | Conditional duration in stagflation. Momentum tilt in reflation |
| v4 | Deflation gold raised to 25-30%. Small equity rebound slice added |
| v5 | Short oil in deflation, plus the global shorts switch |
| v6 | Short energy equities in stagflation |
| v7 | Washout-conditional rebound slice in deflation |
| v8 | AGG reflation leverage moved from equities to energy (QQQ 1x, ERX 2x) |
| v9 | Gold instrument by regime for AGG and VAGG: bullion in reflation, miners in deflation |

---

## 4. The monthly process

1. **The 1st of the month.** The monthly routine classifies the regime, resolves the four signals and appends
   one row to `paper/ledger.csv`. That row is the only thing that rotates money.
2. **Regime unchanged.** Sell nothing. Put the month's contribution into whatever is most underweight.
   Rebalance by selling only if a position is more than 5 points over target.
3. **Regime changed.** Sell what leaves the book, then buy the new book to target.
4. **Habits.** Limit orders near the midpoint. Equity ETFs bought near the close and sold near the open.
   HIFO lots. Harvest lots more than about 5% under water.

Tools:

| Tool | Use |
|---|---|
| `python3 -m src.main --paper-log` | Write the month's ledger row (once per month, idempotent) |
| `python3 -m src.portfolio.order_calc --tier AGG --equity <value> [--held TICKER=DOLLARS]` | Dollar orders from the latest row |
| `python3 -m src.portfolio.orders_workbook --tier AGG` | Rebuild `RotationOrders.xlsx`. The sheet ships with an empty account-value cell. Weights always show. Dollar columns fill in once a value is typed |
| `src/execution/rotation_executor.py` | The automated executor, staged in `AUTOMATION.md`. Kill switch: a file named `HALT` in the repo root |

Monthly checkpoints only. Checking the same rule weekly or daily lost in both eras (test 67). Weekly and daily
runs exist, but they are informational.

---

## 5. What is logged, and what is only watched

Everything under `paper/` is append-only. Never edit or restate a row.

| File | Written by | Meaning |
|---|---|---|
| `paper/ledger.csv` | monthly routine | The regime and every tier's book for each month, with the signals behind it |
| `paper/watch.csv`, `paper/weekly.csv` | Saturday routine | Distance of each dial from its line, the provisional regime, the week |
| `paper/trend_cycle.csv` | daily routine | Quadrant Balances codes, member balances and the flag |
| `paper/swing_trades.csv`, `paper/swing_daily.csv` | daily routine | The standalone swing paper account |
| `paper/overrides.csv` | by hand | Any time the investor departs from the model's book, with the reason and the re-entry rule |

Signals that are computed and logged but **do not trade**:

- **Weekly watch.** Where the dials stand and what next month would be if it ended today.
- **Shadow classifier** (test 58). A faster, asymmetric entry rule. Promoted only if it wins most live
  disagreements.
- **Fragility shadow** (test 70b). S&P within 3% above its 200-day average with 20-day volatility above 16%.
  Logs a one-notch-down shadow book. Promotion trigger is pre-registered. This is not Quadrant Balances and
  the two names must not be mixed.
- **Quadrant Balances flag** (section 6).

Candidates that passed testing and wait on the investor's decision:

- **25% stay-in** (test 85). When the growth dial is off but the Quadrant Balances flag is Intact, hold 75% of
  the defensive book and 25% of the growth-on book. Return and Sortino improved in all eight tier and era
  cells. Drawdown was one point worse in the modern era, so it missed the adoption rule narrowly.
- **Standalone swing account** (tests 79 and 82, section 7). Paper only.

---

## 6. Quadrant Balances

The investor's former desk tool, rebuilt exactly from a workbook export (tests 84 and 85).
Code: `src/portfolio/trend_cycle.py`. Always call it "Quadrant Balances".

- **Cycle** = 5-bar average of the close minus the 15-bar average. Fast.
- **Trend** = Coppock curve: 10-bar weighted average of the 14-bar and 11-bar rates of change. Slow.
- Each is computed on daily, weekly and monthly bars. The week and month in progress count as bars.
- Each oscillator is always in one of four quadrants:

| Quadrant | Oscillator | Report label |
|---|---|---|
| 1 | below zero, rising | Recovering |
| 2 | above zero, rising | Advancing |
| 3 | above zero, falling | Rolling over |
| 4 | below zero, falling | Declining |

- **The code** `4-03-25` means quadrant 4, third bar in that quadrant, 25th bar below zero. The middle number
  is the stage: low means the move is young.
- **Member balances** are the share of S&P 500 members in each quadrant, per oscillator and bar size.
- The daily feeds the weekly, which feeds the monthly. That is why it runs every trading day.

**The flag.** WASHOUT: half or more of members in a monthly cycle decline. BROKEN: both S&P monthly readings
below zero. DETERIORATING: one below. INTACT: both above. It is qualified by the weekly stage: a decline is
EARLY through week 3 and MATURE from week 4.

What the history says (two eras, 1987-2006 and 2007-2026):

- Weekly declines in weeks 1 to 3 have been poor entries. Weeks 4 to 8 have been good ones.
- A weekly decline under an intact monthly was followed by +4.6% and +7.0% over 13 weeks, about 80% of the
  time higher. Under a broken monthly: −0.8% and +1.1%.
- A monthly washout was followed by +17.5% and +21.4% over 12 months, higher in 92% to 100% of cases. The
  danger is the zone just below the line: 2008 passed through 40 to 50% on the way down, and that reading was
  nine months early.
- When the classifier's growth dial is off but the flag is Intact, the S&P 500 averaged +1.7% and +3.2% the
  next month. Once the flag had broken: −0.1% and −0.4%. The classifier's exits are whipsaws more often than
  not while the monthly is intact.
- Limit: the monthly readings are slow. March 2020 began with the flag Intact.

**When it says buy and sell** (test 87, 1950-2026). It is a bottom tool. It does not call tops.

| Level | Buy | Sell |
|---|---|---|
| Monthly, multi-year | Monthly trend turns up from below zero (caught 11 of 13 bear-market lows, about 4 months late). Confirmed when the monthly cycle is back above zero. Extreme: a member washout | Only one: monthly trend crosses below zero. Late by design. A roll-over above zero is a caution, not a sell |
| Weekly, intra-year | Only while the monthly is intact: weekly trend decline in week 4 or later, then the weekly cycle turns up | None |

Under a broken monthly, weekly buy signals fail. Replacing the classifier with the monthly signal was tested
and rejected: it exits too late for the leveraged books. Nothing, including this tool, predicted the
November 2026 sell-off (test 86).

Earlier attempts to trade a breadth-phase version of this (tests 53 to 55) added nothing over the washout
rule already in the matrix. It is a dashboard and a flag, not a lever.

---

## 7. Swing-trading research (tests 75 to 83)

Asked for as a separate account, judged on its own. Code: `research/swing/`, logger `src/portfolio/swing_logger.py`.

- **What works.** Buying daily dips in equity index ETFs. Lower Bollinger band (20 days, 2 SD), 2-day RSI and
  IBS all carry a real, era-stable edge. A regime gate is the best filter.
- **What does not.** Bollinger breakouts. Weekly rotation rules of any kind. Fading stretched moves. Tight
  stops, which destroy bounce trades at every bar size from 5 minutes to 3 days. Options as the wrapper, which
  surrender most of the edge in the model.
- **The paper account (test 79).** SPY and QQQ only. Buy a close with RSI(2) below 10 that is either below the
  lower band or above the 200-day average. Only in Growth or Reflation months. Not in the fragile state.
  Exit on a close above the 5-day average or after 10 days. Two half-size slots.
  1999-2026 at 1x: +6.3% a year, Sharpe 0.87, worst drawdown −14%.
- **Version 2 (test 82).** Adds sell-off bounces in XLE, GLD, GDX, TLT, DBC and USO while they are above their
  210-day line. +8.4% a year at 1x, same drawdown. A candidate.
- **Sell-off rule (test 81).** Buying a 5-day drop beyond 2 sigma pays in real assets only while price is
  still above its 210-day line. Below it the sell-off continues.
- **Buy triggers (test 83).** A close below the lower band is the best trigger. Depth below the band is the
  dial. A second straight close beats the first. Intraday triggers do not bounce the same day.

---

## 8. Everything else that was tested

`TESTS.md` is the full list. By theme:

| Theme | Verdict |
|---|---|
| The original CL1/USO lead-lag arbitrage and every intraday oil variant | Rejected. Fully arbitraged at the minute scale |
| Smoothing, hysteresis, confirmation delays, slower cadences, faster checkpoints | Rejected. Every delay destroys the crash exit that pays for the system |
| Intra-month crash brake and rebound accelerator | Rejected. The brake's benefit was a one-day look-ahead error, found and retracted |
| Volatility targeting, leverage timing, dynamic tiers, fragile-month de-levering | Rejected. The pattern flips between eras |
| Early-warning signals: high-yield and CCC credit, VIX term structure, yen, BOJ balance sheet, financials, valuation | Rejected. Each one either flips sign between eras or points the wrong way |
| Bottom signals | One adopted (breadth washout, v7). Breadth thrust, vol crest, Fed easing, credit turns rejected |
| Shorts | Oil in deflation and energy equities in stagflation adopted. Broad equity, bonds and semiconductors rejected |
| Sector, factor, style and thematic sleeves, international, real estate, TIPS, other metals, agriculture | Rejected. Nothing beats the incumbent in both eras |
| Gold instrument, energy instrument | Settled cell by cell (tests 71 to 73) |
| Business-cycle sector map | Largely agrees with the book where they overlap. No change |
| Crypto | Not in the matrix. A small trend-gated satellite is filed for a user decision |
| LEAPS as the leverage engine | Filed. One contract is too large for the account |
| Managed-futures ETFs in stagflation | Filed with a forward-data trigger |
| Strategy ETFs, a pitched momentum model, static leveraged mixes | Rejected |
| Commodity trend-following on futures | Rejected as tested. Needs clean continuous futures data |
| Biotech catalysts | No tradeable edge. Three avoidance rules kept |
| Overnight versus intraday returns | Real, not tradeable. Kept as a free time-of-day habit |

Recurring lessons:

1. **Two eras or nothing.** Most ideas that look good on 2007-2026 fail on 1987-2006.
2. **The monthly cadence is load-bearing.** Anything that checks more often or reacts mid-month loses.
3. **The cells already do the risk timing.** Overlays that vary risk on top of them add nothing.
4. **State signals fail, turn signals sometimes work.** Cheap gets cheaper. Washouts mark lows.

---

## 9. Quadrant Weekly, the research report

A nine-page PDF, `reports/Quadrant_Weekly_YYYY-MM-DD.pdf`, built each Saturday.

| Page | Content |
|---|---|
| 1 | Cover: the Quadrant Balances board for daily, weekly and monthly, the flag, what changed, what to watch |
| 2 | S&P 500 quadrant charts with state strips, zero-cross markers and member balances |
| 3 | Nasdaq-100 quadrant charts and what each stage has meant historically |
| 4 | Equities: indices and a sector board |
| 5 | Macro and rates |
| 6 | Energy and commodities, with the sell-off rule applied |
| 7 | Technicals: SPY and QQQ with Bollinger bands and which buy triggers fired |
| 8 | Regime model: the two dials, the regime map, distance to the line |
| 9 | Method and limits |

**It is research only, written to be sent around.** Nothing about the account may appear in it: no holdings,
books, tiers, weights, paper accounts, overrides, personal views or pending decisions. The report's data layer
reads market prices only and never opens the ledger or `paper/`. Personal items go in the chat briefing that
accompanies the PDF.

```bash
python3 -m src.report.build            # gather data and render (about 10 minutes cold)
python3 -m src.report.build --cached   # re-render from the last gathered data
```

Narrative text comes from `reports/commentary/YYYY-MM-DD.json`, written by hand each week and checked number
by number against the tables. The build prints `OVERFLOW page N` if anything runs off a page. Details and
design notes: `report/README.md`.

---

## 10. Earlier work kept for reference

- **The bot framework** (`src/broker`, `src/risk`, `src/strategies`, `src/backtest`, `src/main.py`). An
  `ib_insync` connection, order helpers with guardrails, a strategy base class and a bar-level backtester.
- **CL1/USO spread** (`CL1_USO_STRATEGY.md`). The idea the repo was named for. Rejected.
- **CL surge calls** (`CL_SURGE_CALLS.md`). Era-stable only with an oil trend filter. Filed as an execution
  layer that needs live options data.
- **Options suite** (`STRATEGIES.md`). IBS, EWO and afternoon-reversion specs for SPY and QQQ options. IBS has
  a real edge, strongest in Growth months, but works as an overlay, not a standalone strategy. Filed pending
  an IB Gateway connection.
- **Biotech catalysts** (`BIOTECH_CATALYST.md`) and **commodity trend** (`COMMODITY_TREND_RESULTS.md`,
  spec in `New Trading Strats`). Both tested, neither deployed.
- **`GrowthProjection.xlsx`** and **`InvestmentSystemOverview.docx`**. A long-run projection workbook and an
  overview document from the design phase.

---

## 11. Scheduled routines

Three scheduled tasks run in a long-lived Claude Code cloud session. A brand-new session does not inherit
them: recreate them if the old session is gone. `AUTOMATION.md` has the cron equivalents for a self-hosted box.

| Routine | When | What it does |
|---|---|---|
| Monthly ledger | 1st of the month, 14:05 UTC | Writes the ledger row, shows the new book, compares with the Quadrant Balances flag and any candidate |
| Saturday review | Saturdays, 12:00 UTC | Weekly watch and review, Quadrant Balances, builds and sends Quadrant Weekly, then a chat briefing covering the personal side |
| Daily reading | Weekdays, 16:40 New York | `trend_cycle --members --log`, then the swing paper logger. Sends a short daily, weekly and monthly reading |

All three are informational. None of them trades.

---

## 12. Repository map

```
README.md  TESTS.md  PORTFOLIOS.md  REGIMES.md  DEPLOYMENT.md  AUTOMATION.md
RotationOrders.xlsx          manual order sheet, rebuilt monthly, no account value stored
paper/                       append-only logs (section 5)
src/regime/quadrant.py       the classifier
src/portfolio/matrix.py      the matrix and its resolution rules
src/portfolio/paper_logger.py    ledger rows, provisional books, mark-to-market
src/portfolio/order_calc.py      order arithmetic: contribution-first, 5-point drift band
src/portfolio/orders_workbook.py builds RotationOrders.xlsx
src/portfolio/watch.py, weekly_review.py   the weekly watch and Saturday review
src/portfolio/trend_cycle.py     Quadrant Balances
src/portfolio/swing_logger.py    the swing paper account
src/execution/rotation_executor.py   the automated executor
src/report/                  Quadrant Weekly: data, charts, build, render
src/data/yahoo.py            price fetchers used by everything
src/broker, src/risk, src/strategies, src/backtest, src/main.py   the original bot framework
report/                      print stylesheet, fonts, report README
reports/                     issued PDFs and their commentary files
research/engine.py           modern backtest engine (2007-2026)
research/engine_pre2007.py   pre-2007 engine (1987-2006, proxy funds)
research/official_stats.py   regenerates the official numbers
research/swing/, research/trend_cycle/   the swing and Quadrant Balances studies
research/cache/              price cache, not in git
tests/                       pytest suite
```

---

## 13. Setup and commands

```bash
python3 -m pip install -q pandas numpy python-dotenv loguru openpyxl pytest matplotlib
python3 -m pip install -q --upgrade pillow        # matplotlib needs it in a fresh container
python3 -m pytest -q                              # the whole suite, no network needed

python3 -m src.portfolio.weekly_review --tier AGG --balance   # Saturday review (about 5 minutes)
python3 -m src.portfolio.trend_cycle --members --log          # Quadrant Balances reading
python3 -m src.portfolio.swing_logger                         # swing paper account, once per trading day
python3 research/fetch_pre2007.py                             # rebuild the research cache
```

Things that have bitten before:

- **Fresh containers lose pip packages and `research/cache/`.** Reinstall and rebuild before running studies.
- **Yahoo coarsens long ranges.** Asking for too long a daily range silently returns weekly or monthly bars.
  The fetchers assert the bar size. Use explicit windows or five-year chunks.
- **Same-day runs.** `watch.boundary` excludes today, so a review run right after the close shows stale dials.
  Runs before the final print can also log a slightly wrong close.
- **`src/data` was once swallowed by `.gitignore`.** The rule is now `/data/`. Do not broaden it.
- **Prices are Yahoo end-of-day.** No API key. IBKR market data needs a running IB Gateway, which the cloud
  session does not have.

IB Gateway setup, ports and the executor's staged go-live are in `AUTOMATION.md`. Paper port 4002, live 4001.

---

## 14. Working rules

These came from the investor and from mistakes already made. They are not suggestions.

**Investment rules**

1. **Never short the broad US equity market.** Sub-sectors and groups of equities are allowed.
2. **Matrix changes are the investor's decision.** Research proposes. It never adopts on its own.
3. **Two-era discipline.** Test on 2007-2026 and on 1987-2006. Adopt only if every metric improves in both.
   A near miss is a candidate, not a change.
4. **Informational signals never trade.** Only the monthly ledger row moves money.
5. **The ledger and every file in `paper/` are append-only.**
6. **Default to paper.** Live orders need `MODE=live`, the explicit risk flag and the investor's confirmation
   in the conversation. Every order goes through the guarded order path. Ask before anything destructive.
7. **Say what a backtest cannot show.** In-sample design, survivorship bias, small samples, costs, leverage decay.

**Reporting rules**

8. **The weekly PDF carries research only**, nothing about the account (section 9).
9. **No account size in generated files.** The order sheet ships with an empty value cell.
10. **Name things as the investor does.** "Quadrant Balances", never "fragile", for the trend and cycle tool.
11. **Chat answers:** lead with the outcome, short sentences, numbers in tables, no jargon without a definition.

**Repository rules**

12. Develop on `claude/trading-bot-cl1-uso-spread-02qa7h`. Do not open a pull request unless asked.
13. Do not put AI model names or identifiers in commits, code or documents.
14. Record every new test in `TESTS.md` (one line) and `PORTFOLIOS.md` (the evidence), verdict included,
    even when the verdict is no.
15. Keep dependencies lean. Never commit `.env` or credentials.

---

## 15. State at the last update (close of 20 November 2026)

This section goes stale. Check `paper/` for the present.

- **Regime in force:** Reflation, matrix v9, for the fourth month running.
- **Provisional December:** Deflation. Both dials are below their lines. The S&P 500 fund needs roughly +6% by
  month-end to stay growth-on.
- **Quadrant Balances flag:** Intact, weekly decline Early. S&P 500 weekly cycle `4-03-03`, weekly trend
  `4-01-01`, monthly cycle `3-03-43`, monthly trend `3-04-40`. About a fifth of members are in a monthly
  cycle decline, against a 50% washout line.
- **The week:** S&P 500 −8.6%, Nasdaq-100 −10.4%, VIX near 36, with gold, silver and copper falling alongside.
- **Open decisions for the investor:**
  1. The 1 December book: the model's Deflation book, or the 25% stay-in candidate.
  2. An override logged on 16 November (exit Nasdaq, keep energy, commodities and gold) is still marked
     unconfirmed in `paper/overrides.csv`.
  3. Whether to adopt either swing account beyond paper.
  4. The desk's own names for the four quadrants, to replace the report's labels.
- **Research not yet done:** stage counts as a filter on the swing entries; member balances for the Nasdaq-100
  and sectors (needs constituent lists); point-in-time index membership to remove survivorship bias.

---

## Disclaimer

This is personal research software. Nothing in this repository is financial advice. Automated trading can lose
money faster than manual trading, and leveraged products can lose more than expected. The author and any
contributors, including AI assistants, accept no responsibility for losses.
