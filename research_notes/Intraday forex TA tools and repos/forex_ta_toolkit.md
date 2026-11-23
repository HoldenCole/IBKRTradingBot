# Open-source and low-cost toolkit for building and running an intraday FX technical strategy (US retail, as of 23 November 2026)

Method notes that apply to every table below (all lookups done 2026-11-23):

- **Stars / licence / last commit / latest GitHub release**: read from the shields.io JSON badge endpoints (`https://img.shields.io/github/{stars|license|last-commit|v/release|release-date}/OWNER/REPO.json`). Stars are therefore rounded as shields rounds them (e.g. "12k"). The GitHub API and github.com HTML were not reachable from this session, so repository pages themselves were not opened; READMEs were read from `raw.githubusercontent.com`.
- **Latest PyPI version and upload date**: read from `https://pypi.org/pypi/PACKAGE/json` (exact dates).
- Relative dates returned by shields ("october", "last friday") were converted against today (Monday 2026-11-23); a month without a year means 2026.
- "Batch" = recomputes over a whole array/DataFrame. "Incremental" = O(1) update per new bar with retained state.
- Pages that could **not** be opened are listed in the Gaps of the relevant section.

---

## 1. What is the best 2026 open-source stack, component by component, for researching and then running a self-built intraday FX technical strategy on (a) OANDA US spot and (b) CME micro FX futures? Which pieces must be written by hand?

### Takeaway
For research, the strongest current combination is TA-Lib 0.8.x (now pip-installable with a real streaming API) or pandas-ta-classic for indicators, NautilusTrader for event-driven bid/ask backtests with backtesting.py as the quick-look alternative, Dukascopy ticks for free bid/ask history, Optuna + `arch` + skfolio for search and overfitting control, and QuantStats for reporting. For live trading, path (b) CME micro FX futures via IBKR is well served by open tools (ib_async, NautilusTrader's IB adapter, pysystemtrade), while path (a) OANDA US has **no maintained open-source Python client or NautilusTrader adapter** in 2026, so the OANDA execution layer, the OANDA financing model, session/opening-range helpers, the news filter glue, the kill switch and reconciliation must be written by hand.

### Cited Findings

#### 1A. Execution and broker connectivity (category 4)

**OANDA v20 (US spot) — API facts**
- REST rate limit is 120 requests per second per IP; streaming is limited to 20 active streams per IP; no more than 2 new connections per second — [OANDA development guide](https://developer.oanda.com/rest-live-v20/development-guide/)
- The price stream "does not include every single price created for the Account, but instead will provide at most 4 prices per second (every 250 milliseconds) for each instrument" — so it is a throttled quote stream, not a full tick feed — [OANDA pricing endpoints](https://developer.oanda.com/rest-live-v20/pricing-ep/)
- OANDA recommends persistent connections and a reconciliation pattern: request Account Details once at startup, store the snapshot and its TransactionID, then poll Account Changes with the last TransactionID — [OANDA best practices](https://developer.oanda.com/rest-live-v20/best-practices/)
- The official v20 release notes end at version 3.0.25 dated September 28, 2018 (the API definition has not had a versioned change since) — [OANDA release notes](https://developer.oanda.com/rest-live-v20/release-notes/)
- OANDA US lists TradingView, MT4 and its own web/mobile platform on its platforms page; MT5 is not listed for the US entity — [OANDA US platforms](https://www.oanda.com/us-en/trading/platforms/)

**OANDA Python wrappers — status table**

| Package | Repo / PyPI | Licence | Stars | Latest release | Last commit | Status and limits |
|---|---|---|---|---|---|---|
| oandapyV20 | [hootnot/oanda-api-v20](https://github.com/hootnot/oanda-api-v20) / [PyPI](https://pypi.org/project/oandapyV20/) | MIT | 415 | 0.7.2, 2021-08-27 | Aug 2021 | Stale (established earlier). Still the most-used wrapper; works because the API itself is frozen since 2018. Sync only. |
| v20 (official bindings) | [oanda/v20-python](https://github.com/oanda/v20-python) / [PyPI](https://pypi.org/project/v20/) | MIT | 267 | 3.0.25.0, 2018-09-28 | Sep 2018 | Official but abandoned; matches the last API release note. |
| tpqoa | [yhilpisch/tpqoa](https://github.com/yhilpisch/tpqoa) | MIT | 189 | not on PyPI (404) | Jun 2023 | Thin teaching wrapper over the official `v20` package; install from Git only. |
| async-v20 | [jamespeterschinner/async_v20](https://github.com/jamespeterschinner/async_v20) / [PyPI](https://pypi.org/project/async-v20/) | MIT | 12 | 8.0.0b1, 2019-01-04 | Nov 2020 | Dead beta. |
| "oanda-v20" | — | — | — | PyPI returns 404 | — | No package of this name exists on PyPI. |

- tpqoa's README: it "makes use of the Python package `v20` from Oanda" — [tpqoa README](https://raw.githubusercontent.com/yhilpisch/tpqoa/master/README.md)
- NautilusTrader's integration list in its README includes Interactive Brokers (brokerage, "stable") and Databento (data, "stable") but no OANDA adapter; the 2.0 release notes also do not mention OANDA — [NautilusTrader README](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/develop/README.md), [releases](https://github.com/nautechsystems/nautilus_trader/releases)
- QuantConnect LEAN has an OANDA brokerage model (`BrokerageName.OandaBrokerage`) and its forex data comes only from OANDA (`Market.Oanda` is "the only market available for Forex pairs") — [LEAN OANDA model](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/brokerages/supported-models/oanda), [LEAN forex data](https://www.quantconnect.com/docs/v2/writing-algorithms/securities/asset-classes/forex/requesting-data)
- AutoTrader, the one Python framework built around OANDA ("Oanda | Forex CFDs | Complete"), states "AutoTrader is no longer maintained... I've decided to archive it"; last PyPI release 1.1.2 on 2024-03-23, GPL-3.0, 1.3k stars, last commit May 2025 — [AutoTrader README](https://raw.githubusercontent.com/kieran-mackle/AutoTrader/main/README.md), [PyPI](https://pypi.org/project/autotrader/)
- Blankly (LGPL-3.0, 2.5k stars) last released 1.18.25b0 on 2023-07-23 and last committed December 2024 — stale — [PyPI](https://pypi.org/project/blankly/), [repo](https://github.com/blankly-finance/blankly)

**Other US spot dealers**
- FOREX.com US offers a REST API: open a (spread-only) account, then request API access from customer service; the page states no minimum. It can execute trades on 80 markets, stream prices, pull historical data, and read orders/positions/margin. A FIX API is offered "for institutions" via Institutional Sales — [FOREX.com US API trading](https://forex.com/en-us/premium-trader-tools/api-trading)
- FOREX.com US markets MT5 to US clients on a dedicated page — [FOREX.com US MT5](https://www.forex.com/en-us/lp/metatrader-5/)
- Trading.com US is listed by MetaQuotes as an MT5 broker and its US pages advertise MT5 — [MetaQuotes broker listing](https://www.metatrader5.com/en/find-broker/trading-com-us), [Trading.com US MT5](https://www.trading.com/us/lp/mt5-std-sm-l-cmc)
- tastyfx offers MT4 on its US site — [tastyfx MT4](https://tastyfx.com/platforms/metatrader-4)
- tastyfx has a help article titled "What is tastyfx's API offering?" but the page returned HTTP 404 when fetched, so protocol and terms are unverified — [tastyfx API help page](https://tastyfx.com/help-and-support/general-queries/what-is-tastyfxs-api-offering)

**MetaTrader 5 bridging (only relevant at FOREX.com US / Trading.com US)**

| Tool | Repo / PyPI | Licence | Stars | Latest | Notes |
|---|---|---|---|---|---|
| MetaTrader5 (official) | [PyPI](https://pypi.org/project/MetaTrader5/) | MIT (per PyPI) | n/a | 5.0.6231, 2026-09-27 | Windows-only (established); needs a running terminal. |
| mt5linux | [lucas-campagna/mt5linux](https://github.com/lucas-campagna/mt5linux) / [PyPI](https://pypi.org/project/mt5linux/) | MIT | 243 | 1.1.1, 2026-08-04 | "uses Wine, RPyC, and mt5server.exe ... to run MetaTrader5 on Linux"; can manage Docker containers itself. Last commit Oct 2026. |
| MetaTrader5-Docker-Image | [gmag11/MetaTrader5-Docker-Image](https://github.com/gmag11/MetaTrader5-Docker-Image) | MIT | 423 | v2.3, Dec 2025 | KasmVNC-based image with an RPyC server for mt5linux; image grew "from about 600 MB to 4 GB" with Python included. |
| aiomql | [Ichinga-Samuel/aiomql](https://github.com/Ichinga-Samuel/aiomql) / [PyPI](https://pypi.org/project/aiomql/) | MIT | 154 | 4.1.2, 2026-02-28 | Async framework over MetaTrader5; requires Python >=3.13. |
| siliconmetatrader5 | [PyPI](https://pypi.org/project/siliconmetatrader5/) | PolyForm-Noncommercial-1.0.0 | not checked | 1.3.0, 2026-11-05 | MT5 Python API on macOS/Linux; non-commercial licence. |
| MetaApi cloud SDK | [metaapi/metaapi-python-sdk](https://github.com/metaapi/metaapi-python-sdk) / [PyPI](https://pypi.org/project/metaapi-cloud-sdk/) | Proprietary ("Other/Proprietary License") | 100 | 29.1.1, 2025-11-20 | Cloud bridge; no Windows box needed. |

- mt5linux README quote and Docker usage — [mt5linux README](https://raw.githubusercontent.com/lucas-campagna/mt5linux/master/README.md); Docker image details — [MetaTrader5-Docker-Image README](https://raw.githubusercontent.com/gmag11/MetaTrader5-Docker-Image/main/README.md)
- MetaApi lists a regular subscription at "$30 per month, approximately $1 per day" and an extended one at "$100 per month" (plus a $5 signup bonus); the Manager API add-on is USD 125 per MT server per month — [metaapi.cloud](https://metaapi.cloud/)

**cTrader**
- Spotware said that after an internal regulatory assessment in early 2026 "we made the strategic decision to restrict the onboarding of US-based traders on the platform"; FundedNext stopped selling cTrader accounts to US traders from 31 March 2026 and The5ers and Goat Funded Trader followed (article dated 1 July 2026) — [Finance Magnates](https://www.financemagnates.com/forex/ctrader-restricts-us-prop-firm-access-following-internal-regulatory-assessment/)
- FXStreet's cTrader broker list notes cTrader brokers are not CFTC/NFA registered, which is why it is unavailable to US residents there — [FXStreet](https://www.fxstreet.com/brokers/best/ctrader-brokers)
- The Python Open API SDK `ctrader-open-api` is at 0.9.2 (2024-06-26), MIT, 195 stars, last commit Aug 2024 — [PyPI](https://pypi.org/project/ctrader-open-api/), [spotware/OpenApiPy](https://github.com/spotware/OpenApiPy). **Flag: effectively unavailable to US residents.**

**CME micro FX futures connectivity**
- ib_async (successor to ib_insync): PyPI 2.1.0 uploaded 2025-12-08, BSD, 1.8k stars, last commit December 2025, Python >=3.10; needs IB Gateway or TWS running; README recommends raising Gateway memory to 4096 MB for bulk data — [PyPI](https://pypi.org/project/ib_async/), [ib_async README](https://raw.githubusercontent.com/ib-api-reloaded/ib_async/main/README.md)
- pysystemtrade is "a fully automated system for futures trading (for interactive brokers)" and "uses the ib_async library"; GPL-3.0, 3.6k stars, v1.8.3 (Sep 2026), last commit Nov 2026; moved to the `pst-group` organisation in January 2026 — [pysystemtrade README](https://raw.githubusercontent.com/robcarver17/pysystemtrade/master/README.md)
- Tradovate API access is a $25 per month add-on and requires a live funded account with at least $1,000; prop/evaluation accounts are not eligible. A CME Information License Agreement (sub-vendor status) is needed to stream real-time or historical market data through the API but not to place orders and read the account (article dated 12 November 2026, citing Tradovate's "Tradovate API Access" support article as updated September 2026) — [CrossTrade blog](https://crosstrade.io/blog/tradovate-api-add-on-fee-cme-license-webhook/)
- A Tradovate community post puts the CME ILA fee at $500 per month if you want real-time data via the API — [Tradovate community](https://community.tradovate.com/t/whats-the-deal-with-market-subscriptions-and-api-access-to-charts-do-we-need-another-payment/11039.md)
- NinjaTrader and Tradovate are the same clearing group: "NinjaTrader Clearing, LLC d/b/a NinjaTrader, Kraken Derivatives US, and Tradovate", and the site is branded "by Payward" — [NinjaTrader commissions page footer](https://ninjatrader.com/pricing/commissions/)
- Lumibot (GPL-3.0, 2.3k stars, v4.6.95 on 2026-11-22) advertises "stocks, options, futures, forex, crypto and prediction markets through supported brokers" — [Lumibot README](https://raw.githubusercontent.com/Lumiwealth/lumibot/dev/README.md), [PyPI](https://pypi.org/project/lumibot/)

**TradingView alert-to-broker bridges**

| Bridge | Cost (2026-11-23) | Brokers relevant here | Notes |
|---|---|---|---|
| TradersPost | Free tier (paper auto-submit, manual live); $49, $99, $199 per month (15% off yearly); extra live accounts $10/mo each | Lists OANDA, Interactive Brokers, Tradovate, NinjaTrader; forex is a supported asset class | Paid plans "are limited by how many asset classes you can trade" — [TradersPost pricing](https://traderspost.io/pricing) |
| PineConnector | Core $59/mo, Plus $129/mo, Pro $199/mo; 7-day Core trial for $7 | MetaTrader only (hosted MT5 "Edge" in London or Virginia) | Claims "typical end-to-end latency under 1 second"; EA needs Windows 10/11 or Server 2016-2022 — [PineConnector FAQ](https://www.pineconnector.com/pages/faq) |
| tradingview-webhooks-bot (open source) | Free | None built in | GPL-3.0, 782 stars, v1.0.2 and last commit Feb 2024; Flask app; "To actually submit trades, you will have to use a library like ccxt... For other brokers, usually there are SDKs or APIs available" — [README](https://raw.githubusercontent.com/robswc/tradingview-webhooks-bot/master/README.md) |

- A third-party source says PineConnector stopped supporting MT4 on 1 October 2025, while PineConnector's own FAQ still describes itself as a "TradingView to MT4 & MT5 Bridge" — [NexusFi](https://nexusfi.com/d/platforms/pineconnector/); contradicted by [PineConnector FAQ](https://www.pineconnector.com/pages/faq)

#### 1B. Session, calendar and filter tooling (category 5)
- pandas_market_calendars (MIT, 1k stars, v5.6.1 on 2026-11-14) ships a "FOREX" OTC calendar (`ForexExchangeCalendar`) plus several CME calendars (CME_Equity, CME_Bond, CME_Agriculture, CME Globex Crypto) — [README](https://raw.githubusercontent.com/rsheftel/pandas_market_calendars/master/README.rst), [PyPI](https://pypi.org/project/pandas_market_calendars/)
- exchange_calendars (Apache-2.0, 689 stars, v4.13.3 on 2026-11-14) includes a `CMES` calendar — [README](https://raw.githubusercontent.com/gerrymanoim/exchange_calendars/master/README.md), [PyPI](https://pypi.org/project/exchange_calendars/)
- Forex Factory's calendar export is served from `nfs.faireconomy.media` as `ff_calendar_thisweek` in JSON/XML/CSV/ICS; a Forex Factory forum post says demand exceeded 4 billion requests per month and the limit became two requests per five minutes for each of the four file types — [Forex Factory thread](https://www.forexfactory.com/thread/post/15041460). A direct request from this session returned HTTP 429 — [feed URL](https://nfs.faireconomy.media/ff_calendar_thisweek.json)
- FRED's API has a release-dates endpoint that needs only a free API key; by default it excludes release dates with no data (i.e. future dates), so the include option must be set to see upcoming releases — [FRED API docs](https://fred.stlouisfed.org/docs/api/fred/releases_dates.html); Python client `fredapi` 0.5.2 (2024-05-05) — [PyPI](https://pypi.org/project/fredapi/)
- Trading Economics API: third-party reports (June and August 2026) put Standard at $149/month and Professional at $299/month billed yearly; sources conflict on whether the Economic Calendar API is included in those tiers — [apis.io summary](https://apis.io/plans/tradingeconomics/tradingeconomics-plans-pricing/), [BusinessQuant](https://businessquant.com/resources/best-macroeconomic-data-providers), versus [Trading Economics API plans](https://tradingeconomics.com/api). The official client `tradingeconomics` is 4.5.11 (2026-07-08), MIT — [PyPI](https://pypi.org/project/tradingeconomics/)
- Finnhub's `/calendar/economic` endpoint is labelled premium according to a third-party comparison; not confirmed on Finnhub's own pricing page (JS-rendered) — [Finnhub pricing](https://finnhub.io/pricing); client `finnhub-python` 2.4.30 (2026-11-05) — [PyPI](https://pypi.org/project/finnhub-python/)
- investpy: last release 1.0.8 on 2022-01-24, last commit October 2022; the maintainer said Investing.com changed its APIs and Cloudflare protection and pointed users to `investiny` as a stopgap — [investpy discussion 612](https://github.com/alvarobartt/investpy/discussions/612), [PyPI](https://pypi.org/project/investpy/). Treat as dead.
- OANDA's own rollover cut is 5 pm ET, and its candle endpoint defaults to `dailyAlignment=17`, `alignmentTimezone=America/New_York` — usable anchors for a rollover-hour filter — [OANDA financing](https://www.oanda.com/us-en/trading/financing-fees/), [OANDA pricing endpoints](https://developer.oanda.com/rest-live-v20/pricing-ep/)

#### 1C. Research hygiene and optimisation (category 6)

| Tool | Repo / PyPI | Licence | Stars | Latest | What it gives |
|---|---|---|---|---|---|
| Optuna | [optuna/optuna](https://github.com/optuna/optuna) / [PyPI](https://pypi.org/project/optuna/) | MIT | 15k | 5.1.0, 2026-11-16 | Parameter search (TPE, pruning); no walk-forward logic of its own. |
| arch | [bashtage/arch](https://github.com/bashtage/arch) / [PyPI](https://pypi.org/project/arch/) | NCSA (per PyPI) | 1.7k | 9.0.0, 2026-11-11 | `SPA` ("also known as the Reality Check or Bootstrap Data Snooper"), `RealityCheck`, `StepM` (Romano-Wolf), `MCS` (Hansen-Lunde-Nason); stationary, circular-block and moving-block bootstraps. |
| skfolio | [skfolio/skfolio](https://github.com/skfolio/skfolio) / [PyPI](https://pypi.org/project/skfolio/) | BSD-3-Clause | 2.7k | 1.14.4, 2026-11-21 | `CombinatorialPurgedCV` (purge + embargo, path recombination), `WalkForward`, Multiple Randomized CV. |
| pypbo | [esvhd/pypbo](https://github.com/esvhd/pypbo) | AGPL-3.0 | 146 | not on PyPI; last commit Jul 2026 | PBO, PSR, MinTRL, MinBTL, Deflated Sharpe Ratio; README lists "Add test cases" as TODO. |
| timeseriescv | [sam31415/timeseriescv](https://github.com/sam31415/timeseriescv) / [PyPI](https://pypi.org/project/timeseriescv/) | MIT | 290 | 0.2, 2018-09-07 | Purged walk-forward and CPCV splitters; stale. |
| QuantStats | [ranaroussi/quantstats](https://github.com/ranaroussi/quantstats) / [PyPI](https://pypi.org/project/quantstats/) | Apache-2.0 | 7.9k | 0.0.86, 2026-09-27 | Tear sheets; built-in `qs.stats.montecarlo(returns, sims=1000, bust=-0.20, goal=0.50)`. |
| pyfolio-reloaded | [stefan-jansen/pyfolio-reloaded](https://github.com/stefan-jansen/pyfolio-reloaded) / [PyPI](https://pypi.org/project/pyfolio-reloaded/) | Apache-2.0 | 626 | 0.10.2, 2026-11-02 | Tear sheets. |
| empyrical-reloaded | [PyPI](https://pypi.org/project/empyrical-reloaded/) | Apache-2.0 | 134 | 0.7.3, 2026-11-16 | Risk/performance statistics. |
| mlfinlab | [hudson-and-thames/mlfinlab](https://github.com/hudson-and-thames/mlfinlab) | not identifiable | 5k | not on PyPI; last public commit Dec 2021 | Closed-source since; do not plan around it. |

- arch class names and descriptions were read from the source — [arch multiple_comparison.py](https://raw.githubusercontent.com/bashtage/arch/main/arch/bootstrap/multiple_comparison.py); bootstrap list — [arch README](https://raw.githubusercontent.com/bashtage/arch/main/README.md)
- skfolio `CombinatorialPurgedCV(n_folds=10, n_test_folds=8, purged_size=0, embargo_size=0)` documentation — [skfolio docs](https://skfolio.org/generated/skfolio.model_selection.CombinatorialPurgedCV.html); README examples of `WalkForward(train_size=252, test_size=60)` — [skfolio README](https://raw.githubusercontent.com/skfolio/skfolio/main/README.rst)
- pypbo feature list — [pypbo README](https://raw.githubusercontent.com/esvhd/pypbo/master/README.md); QuantStats Monte Carlo — [QuantStats README](https://raw.githubusercontent.com/ranaroussi/quantstats/main/README.md)
- vectorbt (open source) is the usual tool for broadcasting large parameter grids; see section 2 for its licence and limits — [vectorbt README](https://raw.githubusercontent.com/polakowo/vectorbt/master/README.md)

#### 1D. Deployment and monitoring (category 7)

| Tool | Repo / PyPI | Licence | Stars | Latest | Use |
|---|---|---|---|---|---|
| Healthchecks | [healthchecks/healthchecks](https://github.com/healthchecks/healthchecks) | BSD-3-Clause | 11k | v5.0.3, Oct 2026 | Dead-man's-switch heartbeat monitoring (self-host or hosted). |
| Apprise | [caronc/apprise](https://github.com/caronc/apprise) / [PyPI](https://pypi.org/project/apprise/) | BSD-2-Clause | 18k | 2.3.0, 2026-11-20 | One API for Telegram, email, Pushover, Slack, etc. |
| python-telegram-bot | [repo](https://github.com/python-telegram-bot/python-telegram-bot) / [PyPI](https://pypi.org/project/python-telegram-bot/) | LGPL-3.0-only (PyPI); shields reports GPL-3.0 | 30k | 22.8, 2026-06-12 | Two-way Telegram control (status, pause, flatten). |
| Supervisor | [Supervisor/supervisor](https://github.com/Supervisor/supervisor) / [PyPI](https://pypi.org/project/supervisor/) | BSD-derived | 9.2k | 4.3.0, 2025-08-23 | Process supervision (systemd is the no-install alternative). |
| Uptime Kuma | [louislam/uptime-kuma](https://github.com/louislam/uptime-kuma) | MIT | 95k | v2.5.12, 2026-11-17 | Self-hosted monitoring with push monitors. |
| freqtrade (pattern reference) | [freqtrade/freqtrade](https://github.com/freqtrade/freqtrade) | GPL-3.0 | 57k | v2026.10, Oct 2026 | Crypto-only, but a mature open example of dry-run mode and Telegram control: "designed to support all major exchanges and be controlled via Telegram or webUI". |

- freqtrade description — [freqtrade README](https://raw.githubusercontent.com/freqtrade/freqtrade/develop/README.md)
- NautilusTrader offers "optional Redis-backed state persistence" for live systems — [NautilusTrader README](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/develop/README.md)
- OANDA's partner VPS page says the partner VPS (Beeks) shares a data centre with OANDA infrastructure and an OANDA page references Equinix NY4 and LD4; none of these pages ties the v20 REST endpoint to a specific data centre — [OANDA VPS partners](https://oanda.com/us-en/trading/tools/partners/vps-partners)
- PineConnector sells a compatible Windows VPS "from $30/month" (indicative of Windows forex VPS pricing) — [PineConnector FAQ](https://www.pineconnector.com/pages/faq)

### Inferences
- **Recommended stack (a) OANDA US spot:** indicators TA-Lib 0.8.x (batch + stream API) with talipp as alternative; research backtests in NautilusTrader 1.231 on Dukascopy quote ticks (alternative: backtesting.py with `spread=` for quick single-pair checks, or LEAN, which is the only engine with OANDA's own history and an OANDA brokerage model); data from Dukascopy for research plus OANDA bid/ask candles to check broker-specific behaviour; live execution via a hand-written thin REST/stream client (or pinned oandapyV20 0.7.2, accepting it is unmaintained); Forex Factory weekly feed for a news blackout; Optuna + skfolio CPCV + arch SPA/StepM; QuantStats; systemd/Supervisor + Healthchecks + Apprise/Telegram on a small Linux VPS in the New York area.
- **Recommended stack (b) CME micro FX futures:** same research tools, but use NautilusTrader's Interactive Brokers adapter (or raw ib_async) for live trading and Databento/IBKR history for the futures themselves; Tradovate is workable only if you accept the $25/month API fee, the $1,000 minimum and sourcing market data elsewhere (its API data needs a CME licence). This path has a fully open, maintained research-to-live chain; path (a) does not.
- **Must be hand-written (no good open tool found):** (1) a maintained OANDA v20 client with reconnecting streams and transaction-ID reconciliation; (2) an OANDA financing model with the 1% admin fee and Wednesday triple (NautilusTrader's module uses raw OECD rate differentials, see section 2); (3) session, opening-range, and rollover-hour helpers (no maintained library found; pandas_market_calendars only gives open/closed); (4) the news-blackout join between a calendar feed and the strategy clock; (5) kill switch (max daily loss, max position, stale-data and heartbeat checks) and startup reconciliation against broker state; (6) a bid/ask-aware bar builder if not using NautilusTrader's own aggregation; (7) FIFO/no-hedging position logic if the backtester allows hedged positions.
- Because the OANDA API definition has been frozen since September 2018, stale wrappers are a maintenance and security-patch risk rather than a functional one; a 200-300 line `httpx`/`aiohttp` client covers candles, pricing stream, orders and account changes.
- TradingView webhook bridges add a third party and roughly a one-second hop (PineConnector's own claim) to every order; they suit bar-close strategies on 15-minute bars and above, not 1-minute logic, and they move strategy logic into Pine where repainting pitfalls apply (section 2).
- ib_async had no commits between December 2025 and this check (about 11 months); it is the accepted successor but should be watched for maintenance slowdown.

### Gaps
- tastyfx API details (REST vs streaming, eligibility, cost) could not be confirmed: the help page returned 404 and search snippets conflict (one FAQ document describes a WebSocket API).
- FOREX.com US REST API documentation URL, rate limits and any Python SDK were not found; the API page does not link the docs.
- Whether OANDA US ever enabled MT5 was not confirmed; only the absence of MT5 on the US platforms page was observed. The official `forex.com/en-us` platform page returned 403 to direct fetch.
- Lumibot's actual forex-capable broker list (OANDA? Tradovate?) was not opened; only the README claim was read.
- NinjaTrader's own API/automation (NinjaScript, ATI) and its backtester were not researched in this pass.
- IBC / IB Gateway auto-restart tooling, concrete VPS vendors and prices near NY4 or Chicago, and where `api-fxtrade.oanda.com` is hosted were not established from primary sources; latency should be measured with ping/traceroute from candidate locations.
- Whether TradingView webhooks still require a paid TradingView plan, and which plan, was not verified.
- econdb: no PyPI package named `econdb` exists (404); its API and pricing were not researched. Finnhub and Trading Economics prices are from third parties only.
- IBKR's rule that US clients must be Eligible Contract Participants for leveraged spot FX was taken from earlier project research and not re-verified (the IBKR forex page returned HTTP 500).

---

## 2. Which backtester gets intraday FX costs right out of the box, and what must be configured manually (spread, swap, slippage, bid/ask fills)?

### Takeaway
None is fully correct out of the box. NautilusTrader comes closest (fills against L1 bid/ask quote ticks, a built-in FX rollover module at 5 pm US/Eastern, fill/latency/margin models), and LEAN is second (OANDA bid/ask QuoteBars, but zero slippage and no financing by default); backtesting.py and open-source vectorbt only apply a constant spread or fractional fee and have no swap, and every engine needs the broker's financing mark-up and realistic slippage added by hand.

### Cited Findings

**Comparison table (documented behaviour; "manual" = you must code or configure it)**

| Engine | Version / date | Licence | Stars | Bid and ask separately | Variable spread | Commission | Swap / rollover | Slippage | Intrabar stop/limit | Tick or 1-min data | Margin / leverage | FIFO / no-hedging |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NautilusTrader | Stable 1.231.0 (PyPI 2026-08-02); 2.0.0rc9 pre-release 2026-11-10 | LGPL-3.0-or-later | 32k | Yes with QuoteTick (L1 best bid/ask) | Yes (from quotes) | Fee models (e.g. MakerTakerFeeModel) | Built-in FX rollover module (OECD rate differential); broker mark-up manual | `prob_slippage` one-tick model, latency model | Bars become 4 synthetic updates O-H-L-C or adaptive ordering | Quotes, trades, bars, L2/L3 | `AccountType.MARGIN`, `LeveragedMarginModel` default | `OmsType.NETTING` available (venue-level) |
| QuantConnect LEAN | Continuous (last commit 2026-11-20); lean-cli 1.0.234 (2026-11-18) | Apache-2.0 | 23k | Yes (QuoteBars with bid and ask, no sizes) | Yes (OANDA spread dataset) | OANDA model: zero fees | OANDA model: `NullMarginInterestRateModel` (none) | OANDA model: `NullSlippageModel` (none) | Fill model on bar/tick data | Tick, second, minute | `SecurityMarginModel`, up to 50x | Not documented on the pages read |
| backtesting.py | 0.6.6 (2026-07-22) | AGPL-3.0 | 9.3k | No (single OHLC series) | No (constant `spread=`) | `commission=` (applied twice per trade since 0.6.0) | None | None beyond spread | OHLC-based SL/TP | Any bar size; single instrument | `margin=` | FIFO closing by default; `hedging=` "makes FIFO trade closing optional" |
| vectorbt (open source) | 1.2.1 (2026-11-11) | Apache 2.0 + Commons Clause | 9.9k | No | No | fees as fraction | None | slippage as fraction | Limited; README says limit orders and leverage are PRO features | Any bars | Not in OSS (PRO) | Not modelled |
| vectorbt PRO | v2026.10.5 | Proprietary membership | n/a | not verified | not verified | yes | not verified | yes | limit orders (per README) | any | leverage (per README) | not verified |
| Backtrader | 1.9.78.123 (2023-04-19) | GPL-3.0 | 24k | No | No | Yes | Manual | Yes | Yes | Any | Yes | Manual |
| MT5 Strategy Tester | Terminal build dependent | Proprietary (free with broker) | n/a | Yes ("trading operations are always performed by Bid and Ask prices") | Yes in real-tick mode | Broker settings | Broker swap settings | Random delay mode | Tick-level | Broker real ticks or generated from M1 | Yes | Netting accounts at US brokers |
| TradingView strategy tester | n/a | Proprietary | n/a | No (chart price only) | No | `commission` property | No | `slippage` property | Broker emulator assumptions; Bar Magnifier on Premium/Ultimate | Chart bars | `leverage`/margin settings | n/a |

Sources for the table rows are itemised below. Cells with no itemised source (the whole Backtrader row; vectorbt's "fees/slippage as fraction"; MT5's "broker swap settings" and "netting accounts at US brokers"; TradingView's leverage setting) are from prior knowledge and were **not re-verified** in this session.

**NautilusTrader**
- Versions: PyPI latest stable 1.231.0 uploaded 2026-08-02 (Python >=3.12,<3.15); GitHub shows 2.0.0rc5 through rc9 between 15 September and 10 November 2026; the README says release candidates "are intended for community testing... We do not recommend using release candidates in production" and require `--pre` — [PyPI](https://pypi.org/project/nautilus_trader/), [releases](https://github.com/nautechsystems/nautilus_trader/releases), [README](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/develop/README.md)
- Data hierarchy: L3, L2, "L1 quote ticks (market-by-price): Best bid and ask prices and sizes", trades, bars. "Bar data ... cannot establish intrabar price order, spread, depth, or queue position"; the docs advise moving "to quotes, trades, or depth data before relying on results that depend on spread, exact intrabar order, tight exits, or queue position" — [data and venues](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/develop/docs/concepts/backtesting/data-and-venues.md)
- Bar execution: applies only on an `L1_MBP` venue with `bar_execution=True` and externally aggregated time bars; each bar is split into four synthetic updates, default path Open-High-Low-Close, or with `bar_adaptive_high_low_ordering=True` the extreme nearest the open is visited first; this "is a deterministic heuristic, not a reconstruction of the actual trade sequence" — [bar execution](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/develop/docs/concepts/backtesting/bar-execution.md)
- Look-ahead guard: "each bar's initialization timestamp (`ts_init`) must represent the close of the interval"; for open-stamped bars set `ts_init = ts_event + interval_ns`. "The engine does not provide a native next-bar-open fill mode"; using the current bar's open inside `on_bar` "introduces look-ahead" — [bar execution](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/develop/docs/concepts/backtesting/bar-execution.md)
- Fill model: `prob_fill_on_limit` (default 1.0) and `prob_slippage` (default 0.0); "A successful slippage draw moves the fill one tick against the order direction"; other built-ins include `OneTickSlippageFillModel` and `MarketHoursFillModel` ("normal or one-tick-wider synthetic spread") — [fill models](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/develop/docs/concepts/backtesting/fill-models.md)
- Latency: `StaticLatencyModel(base_latency_nanos=...)` delays order arrival — [bar execution](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/develop/docs/concepts/backtesting/bar-execution.md)
- Accounts: `CASH`, `MARGIN`, `BETTING`; margin accounts use `LeveragedMarginModel` by default, `StandardMarginModel` optional; examples use `OmsType.NETTING` — [accounts and margin](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/develop/docs/concepts/backtesting/accounts-and-margin.md)
- FX rollover module: "Simulates FX rollover (swap) interest applied at 5 PM US/Eastern daily... Wednesday and Friday rollovers are tripled (Wednesday for T+2 settlement, Friday for the weekend)"; it "Uses short-term interest rate data (OECD format)" and returns `(base_rate - quote_rate) / 365 / 100` as the daily rate — [fx_rollover.rs source](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/develop/crates/backtest/src/modules/fx_rollover.rs), [Rust API docs](https://nautilustrader.io/docs/rust-api-latest/nautilus_backtest/modules/fx_rollover/struct.FXRolloverInterestModule.html)
- A separate CFD swap module takes "per-instrument signed daily Decimal fractions of settlement notional, with separate long and short values. The UTC rollover time and triple-roll weekday are configurable" — [simulation modules](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/develop/docs/concepts/backtesting/simulation-modules.md)

**QuantConnect LEAN**
- Forex dataset: created "by QuantConnect processing raw tick data from OANDA"; 72 pairs; starts January 2007 (varies by pair); tick, second, minute, hour, daily; UTC; QuoteBars carry bid and ask prices but no sizes — [LEAN forex dataset docs](https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/quantconnect/forex-data)
- Resolutions table: Tick = quote ticks only; Second and Minute = QuoteBars only; no trade data — [LEAN forex requesting data](https://www.quantconnect.com/docs/v2/writing-algorithms/securities/asset-classes/forex/requesting-data)
- OandaBrokerageModel defaults: `ImmediateFillModel`; `NullSlippageModel`; `ConstantFeeModel` with zero fees because "Our data is the spread dataset, so we model the spread pricing. To estimate OANDA Core+Commission data, use a custom fee model and a custom fill model"; `SecurityMarginModel` "allows up to 50x leverage"; `NullMarginInterestRateModel` — [LEAN OANDA brokerage model](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/brokerages/supported-models/oanda)
- Local data cost via LEAN CLI: minute forex files cost 3 QCC each; the worked example is 312 files = 936 QCC = $9.36 for one pair-year — [LEAN CLI forex datasets](https://www.quantconnect.com/docs/v2/lean-cli/datasets/quantconnect/forex)
- Shields reports the last tagged GitHub release as v2.4.0.1 (August 2017), which is misleading: LEAN ships continuously from master (last commit 2026-11-20) and via the `lean` CLI package 1.0.234 (2026-11-18) — [QuantConnect/Lean](https://github.com/QuantConnect/Lean), [lean on PyPI](https://pypi.org/project/lean/)

**backtesting.py**
- 0.6.6 released 2026-07-22 (bug fixes incl. Pandas 3.0, CAGR); 0.6.0 (2025-02-04) added `Backtest(spread=)` and changed `commission=` "to apply twice per trade"; 0.6.2 added `FractionalBacktest`; 0.6.3 added `MultiBacktest`; `hedging=` (2020) "makes FIFO trade closing optional" — [backtesting.py CHANGELOG](https://raw.githubusercontent.com/kernc/backtesting.py/master/CHANGELOG.md), [PyPI](https://pypi.org/project/backtesting/)

**vectorbt (open source) and PRO**
- Licence file: "Apache 2.0 with Commons Clause" — [vectorbt LICENSE.md](https://raw.githubusercontent.com/polakowo/vectorbt/master/LICENSE.md)
- README: "VectorBT is the open-source community edition of VectorBT PRO. PRO extends the library with parallelization, additional data integrations, portfolio optimization, pattern recognition, event projections, limit orders, leverage, and over 100 other features" — [vectorbt README](https://raw.githubusercontent.com/polakowo/vectorbt/master/README.md)
- vectorbt 1.2.1 uploaded 2026-11-11, Python >=3.11,<3.15 — [PyPI](https://pypi.org/project/vectorbt/)
- PRO pricing: $25 per month, $225 per year, or $500 lifetime; "Individual memberships are for personal, non-commercial use only"; site banner shows PRO v2026.10.5 — [VectorBT PRO membership](https://vectorbt.pro/become-a-member/)

**Engines that are not suitable or are stale**
- Jesse 3.7.0 (2026-11-23), MIT, 8.8k stars: PyPI summary is "A trading framework for cryptocurrencies" — crypto-only — [PyPI](https://pypi.org/project/jesse/)
- hftbacktest 2.4.4 (2025-12-10), MIT, 5.1k stars, last commit Dec 2025: needs Level-2/Level-3 feeds and models queue position; live bots are "currently for Binance Futures and Bybit" — crypto-oriented and unusable for spot FX without depth data — [hftbacktest README](https://raw.githubusercontent.com/nkaz001/hftbacktest/master/README.rst), [PyPI](https://pypi.org/project/hftbacktest/)
- Zipline-reloaded 3.2.1 (2026-10-25), Apache-2.0, 2k stars — maintained, but an equities-style engine — [PyPI](https://pypi.org/project/zipline-reloaded/)
- bt 1.4.1 (2026-10-10), MIT, 3k stars — portfolio-allocation backtests, not intraday order simulation — [PyPI](https://pypi.org/project/bt/)
- Backtrader 1.9.78.123 (2023-04-19), GPL-3.0, 24k stars, last commit April 2023 — stale — [PyPI](https://pypi.org/project/backtrader/)
- PyBroker 2.0.3 (2026-11-15), "Apache License 2.0 with Commons Clause", 3.7k stars — maintained but stock/ML oriented — [PyPI](https://pypi.org/project/lib-pybroker/)
- AutoTrader (FX/OANDA-specific) — unmaintained, see section 1 — [AutoTrader README](https://raw.githubusercontent.com/kieran-mackle/AutoTrader/main/README.md)

**MetaTrader 5 Strategy Tester**
- Testing can use "real ticks provided by a broker or ... ticks generated by the strategy and based on minute data"; "When testing on real ticks, a spread may change within a minute bar, whereas when generating ticks within a minute, a spread fixed in the appropriate bar is used"; "trading operations are always performed by Bid and Ask prices"; if a minute has no tick data the tester generates ticks, and ticks without a matching minute bar are ignored; modes are Every Tick, 1 Minute OHLC and Open Prices Only (the last cannot use Random Delay) — [MetaTrader 5 help: tick generation](https://www.metatrader5.com/en/terminal/help/algotrading/tick_generation)

**TradingView strategy tester**
- Broker emulator: fills use only chart data; if the open is closer to the high it assumes open → high → low → close, otherwise open → low → high → close; it "assumes that no gaps exist inside each chart bar"; orders created on a bar close fill at the next bar's open by default — [Pine Script strategies docs](https://www.tradingview.com/pine-script-docs/concepts/strategies/)
- "Users with Premium and Ultimate plans can override the broker emulator's chart-based assumptions" with Bar Magnifier (`use_bar_magnifier = true`), which pulls lower-timeframe bars; scripts can request at most 200,000 lower-timeframe bars — [Pine Script strategies docs](https://www.tradingview.com/pine-script-docs/concepts/strategies/)
- Repainting: TradingView classes as unacceptable "leaking future information into the past, strategies on non-standard charts, and realtime intrabars generating alerts or orders"; `request.security()` with `lookahead_on` and no `[1]` offset leaks future data; `calc_on_every_tick` strategies behave differently on historical and realtime bars; history is limited to 5,000-40,000 bars by plan — [Pine Script repainting docs](https://www.tradingview.com/pine-script-docs/concepts/repainting/)

**Commercial packages**
- StrategyQuant X lifetime licences: Starter $1,290, Professional $1,790, Ultimate $4,900 (or 12 monthly payments of $129 / $175 / $420); walk-forward optimizer and robustness tests are Professional-tier features — [StrategyQuant pricing](https://strategyquant.com/pricing/)
- Forex Tester Online: Starter $199/year and Pro $299/year list price ($139 and $179 during the Black Friday promotion shown on 2026-11-23); Starter includes "up to 23 years of tick-by-tick data" on 69 symbols, Pro 283 symbols — [forextester.com](https://forextester.com/)

### Inferences
- "Right out of the box" ranking for intraday FX: (1) NautilusTrader on quote ticks; (2) LEAN with OANDA QuoteBars; (3) MT5 real-tick mode (accurate for that broker's feed, but MQL5-only and tied to a broker that offers MT5 in the US); (4) backtesting.py with constant spread; (5) vectorbt OSS for fast screening only.
- What must be configured by hand in NautilusTrader for OANDA-like realism: load bid/ask quote ticks (not mid bars); supply rate data to the FX rollover module **and** add OANDA's 1% annualised admin fee (the built-in uses raw OECD short-term rate differentials, which will understate real financing cost and overstate credits); set `prob_slippage` or a latency model; choose `OmsType.NETTING` to mirror US no-hedging rules; set margin to 2% (50:1) on majors. For LEAN: replace `NullSlippageModel`, add a financing model (none by default), and note fees are zero because the data already embeds OANDA's spread.
- The NautilusTrader source comment says both Wednesday and Friday rollovers are tripled. OANDA's own schedule triples only Wednesday (5 pm ET) and charges nothing on Saturday/Sunday. Unless the code offsets this elsewhere, the built-in module may not match OANDA's weekly pattern; verify with a one-week test before trusting swap totals.
- For strategies holding minutes to one day and flat before 5 pm ET, swap can be made irrelevant by design, which removes the largest modelling gap; spread at entry/exit times then dominates and requires tick or 1-minute bid/ask data rather than a constant spread.
- TradingView and backtesting.py both fill on a single price series with an assumed intrabar path; stops and targets inside the same bar are path-guesses, so results on 1-5 minute bars with tight exits should not be trusted from either.
- US FIFO: backtesting.py's default (non-hedging, FIFO close) and NautilusTrader's NETTING mode are the closest to NFA Compliance Rule 2-43b behaviour; no engine enforces the rule by name.

### Gaps
- Whether NautilusTrader bid-priced and ask-priced bars update the two book sides separately in 1.231/2.0 was not confirmed in the pages read (earlier versions did); quote ticks are the documented route.
- MT5 "history quality" percentages, the cTrader backtester, NinjaTrader's Strategy Analyzer and Forex Tester desktop (FT6) pricing were not verified from primary pages (forextester.com/pricing returned 403; the cTrader point is moot for US residents).
- No new (2024-2026) FX-specific open-source Python or Rust backtester of substance was found beyond those listed; pandas-ta-classic's README mentions an integration with "manifoldbt", which was not investigated. barter-rs (MIT, 2.4k stars, last commit Jan 2026) was not assessed for FX.
- vectorbt PRO's bid/ask and swap handling were not checked (docs are members-only).
- LEAN's exact bid/ask fill rule for QuoteBars and its handling of FIFO were not re-read in this session.

---

## 3. What is the cheapest reliable source of multi-year tick or 1-minute bid/ask data for the major pairs, and what are its known defects?

### Takeaway
Dukascopy's free historical feed (tick-level bid and ask, many years deep, retrievable with maintained open-source downloaders) is the cheapest multi-year bid/ask source; its defects are that it is one Swiss bank's top-of-book indicative quotes, not OANDA's or CME's prices, with quoted-size "volume", occasional gaps and scaling quirks. The cheapest broker-matched alternative is OANDA's own bid/ask candles via the v20 API (free with an account) or QuantConnect's OANDA dataset at about $9.36 per pair-year of minute data.

### Cited Findings

**Sources and prices**

| Source | Cost | Depth / granularity | Bid and ask? | Known defects |
|---|---|---|---|---|
| Dukascopy historical feed | Free | Tick and candles; per-instrument start dates listed in dukascopy-node README | Yes (tick bid/ask; candles per offer side) | Top-of-book quotes of one bank's liquidity; volume = quoted size; gaps; scaling divisor quirks; differs from other feeds |
| HistData.com | Free (M1 and tick, ASCII) | M1 from 2000 | M1 is bid only; separate tick files | EST without DST; bid quotes only on bars; site unreachable in this session |
| TrueFX | Free with registration | Tick, millisecond, top of book | Yes | Sourced from Integral OCX; depth of archive not verified |
| OANDA v20 candles | Free with account | S5 to monthly; max 5,000 candles per request | Yes (`price=M`, `B`, `A`) | Broker-specific; stream throttled to 4 prices/sec; history depth not documented on the page |
| QuantConnect OANDA dataset | $9.36 per pair-year (minute, local download) | From Jan 2007; tick to daily; 72 pairs | Yes (QuoteBars) | No sizes; LEAN format |
| IBKR historical bars | Free for forex with account | Bars; ≤30-second bars only for last 6 months | Yes (BID, ASK, MIDPOINT, BID_ASK) | Pacing limits; BID_ASK requests count double |
| Massive (ex-Polygon) Currencies | $0 Basic; $49/month Starter; $999/month Business | Basic 2 years EOD/minute; Starter 10+ years, quotes, websockets | Starter lists quotes | History from 2009-09-25; six of seven USD majors miss weeks in late 2020 |
| Databento (CME futures, not spot) | Standard plan $199/month from 2026-06-22 (was $179); pay-as-you-go historical | CME Globex MDP 3.0 | Yes (order book) | Futures only; costs by usage |
| FirstRate Data FX bundle | One-off price not shown; updates $59.95/month | 1-min from 2009/2010 to Nov 2026, 74 tickers | No (single OHLC series) | No bid/ask; source is FirstRate's own |

- Dukascopy support statement: "Ticks are quotes arriving in our system from our liquidity providers. They are neither orders nor trades. We reflect only best ask and bid available in our system... Volumes shown are volumes quoted on the best bid and ask levels" — [Elite Trader thread quoting Dukascopy](https://elitetrader.com/et/threads/interpreting-dukascopy-tick-data.352792/)
- Forum reports on Dukascopy data: timestamps appearing as GMT+2 rather than UTC in a 2012 thread, missing ticks around weekends/DST, bar-level spikes, and a price-scaling divisor issue for JPY crosses and gold — [Dukascopy forum](https://www.dukascopy.com/swiss/english/forex/jforex/forum/viewtopic.php?p=64464), [Dukascopy forum](https://www.dukascopy.com/swiss/english/forex/jforex/forum/viewtopic.php?p=84267)
- Tickstory treats Friday 22:00 to Sunday 21:00 UTC as the weekend window and notes Dukascopy occasionally has data inside it; it attributes gaps in raw Dukascopy data to illiquid periods — [Tickstory forum](https://tickstory.com/forums/topic/data-gaps-and-bad-ticks-error-source/)
- A MultiCharts user found backtests on Dukascopy bid data and IQFeed data "drastically different" and was advised to backtest on the same feed the live broker supplies — [MultiCharts forum](https://www.multicharts.com/discussion/viewtopic.php?p=101017&view=show)
- HistData: 1-minute data is "EST without daylight saving adjustments", bars are bid quotes (columns "Bar OPEN/HIGH/LOW/CLOSE Bid Quote"), available from 2000; tick data only in ASCII — [FX-1-Minute-Data README](https://github.com/philipperemy/FX-1-Minute-Data), [histdata on PyPI](https://pypi.org/project/histdata/)
- TrueFX: "Top-of-book, tick-by-tick market data, with fractional pip spreads in millisecond detail ... sourced from Integral OCX ... at zero cost"; requires free registration — [TrueFX downloads](https://www.truefx.com/truefx-historical-downloads/)
- OANDA candles endpoint: `price` component default M (mid), with bid and ask selectable; `granularity` default S5; `count` default 500, maximum 5,000; `smooth` default False; `dailyAlignment` default 17; `alignmentTimezone` default America/New_York ("returned times will still be represented in UTC"); `weeklyAlignment` default Friday — [OANDA pricing endpoints](https://developer.oanda.com/rest-live-v20/pricing-ep/)
- OANDA granularities run from S5 (5-second) through M1, H4, weekly and monthly — [OANDA instrument definitions](https://developer.oanda.com/rest-live-v20/instrument-df/)
- QuantConnect dataset facts and price — [LEAN forex dataset docs](https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/quantconnect/forex-data), [LEAN CLI forex datasets](https://www.quantconnect.com/docs/v2/lean-cli/datasets/quantconnect/forex)
- IBKR pacing: identical requests within 15 seconds, six or more requests for the same contract/exchange/tick type within two seconds, or more than 60 requests in ten minutes are violations; BID_ASK requests count twice; bars of 30 seconds or less are unavailable beyond six months; forex data needs no paid subscription — [IBKR historical data limitations](https://www.interactivebrokers.com/docs/tws-api/doc/market-data-historical/historical-data-limitations/introduction), [IBKR market data limitations](https://www.interactivebrokers.com/docs/tws-api/doc/md/market-data-limitations)
- Massive currencies plans, history start (25 September 2009), late-2020 gaps and "institutional bank feeds" sourcing — [massive.com/currencies](https://massive.com/currencies); Business tier $999/month — [massive.com/business-currencies](https://massive.com/business-currencies); client `massive` 2.11.0 (2026-11-19), MIT — [PyPI](https://pypi.org/project/massive/)
- Databento subscription change effective Monday 22 June 2026; CME Globex MDP 3.0 Standard renews at $199/month after $179 — [Databento blog](https://databento.com/blog/updates-to-subscription-pricing); client `databento` 0.90.0 (2026-11-03), Apache-2.0, 333 stars — [PyPI](https://pypi.org/project/databento/)
- FirstRate FX Majors bundle: 1-minute to 1-day bars, 74 tickers, Jan 2009 - Nov 2026 (individual pairs listed from 2010-01-01), updated to 2026-11-20, "Updates are $59.95 per month thereafter" — [FirstRate FX Majors](https://firstratedata.com/b/20/fx-majors); its dataset card describes single-series OHLCV with no separate bid/ask — [FirstRate FX dataset card](https://firstratedata.com/ai/datasets/fx-intraday)

**Open-source downloaders**

| Tool | Repo / PyPI | Language | Licence | Stars | Latest | Status |
|---|---|---|---|---|---|---|
| dukascopy-node | [Leo4815162342/dukascopy-node](https://github.com/Leo4815162342/dukascopy-node) | Node.js / CLI | MIT | 984 | v1.51.1, Oct 2026 | Active; tick and candle timeframes, CSV/JSON; README lists earliest date per instrument (UTC). |
| dukascopy-python | [Eghosa-Osayande/dukascopy](https://github.com/Eghosa-Osayande/dukascopy) / [PyPI](https://pypi.org/project/dukascopy-python/) | Python | MIT | not checked | 7.0.0, 2026-11-17 | Active; `fetch_ticks()` for bid/ask ticks; candles by `OFFER_SIDE_BID` or ask; UTC datetimes. |
| tick-vault | [keyhankamyar/tick-vault](https://github.com/keyhankamyar/tick-vault) / [PyPI](https://pypi.org/project/tick-vault/) | Python | MIT | not checked | 0.1.0, 2025-10-13 | New; mirrors Dukascopy `.bi5` layout, resume, SQLite metadata. |
| tickterial | [PyPI](https://pypi.org/project/tickterial/) | Python | MIT | repo not found via shields | 1.1.2, 2024-06-04 | Dormant. |
| duka | [giuse88/duka](https://github.com/giuse88/duka) / [PyPI](https://pypi.org/project/duka/) | Python | MIT | 357 | 0.2.0, 2016-06-04 | Dead (last commit Aug 2017). |
| findatapy | [cuemacro/findatapy](https://github.com/cuemacro/findatapy) / [PyPI](https://pypi.org/project/findatapy/) | Python | Apache-2.0 | 2.2k | 0.1.42, 2026-03-20 | Maintained; multi-source incl. Dukascopy. |
| histdata (FX-1-Minute-Data) | [philipperemy/FX-1-Minute-Data](https://github.com/philipperemy/FX-1-Minute-Data) / [PyPI](https://pypi.org/project/histdata/) | Python | Apache-2.0 (repo), MIT (PyPI field) | 697 | 1.1, 2023-05-19 | Last commit May 2025; also offers a pre-built 2000-2024 M1 archive. |
| polars-trading | [ngriffiths13/polars-trading](https://github.com/ngriffiths13/polars-trading) / [PyPI](https://pypi.org/project/polars-trading/) | Python/Rust | not specified | 62 | 0.2.0, 2025-09-02 | Tick-to-bar builders (`time_bars`, `tick_bars`); early stage. |

- READMEs read: [dukascopy-node](https://raw.githubusercontent.com/Leo4815162342/dukascopy-node/master/README.md), [dukascopy-python](https://raw.githubusercontent.com/Eghosa-Osayande/dukascopy/main/README.md), [tick-vault](https://raw.githubusercontent.com/keyhankamyar/tick-vault/main/README.md), [polars-trading](https://raw.githubusercontent.com/ngriffiths13/polars-trading/main/README.md)
- NautilusTrader's data engine aggregates time bars from ticks and exposes `time_bars_build_delay` so boundary ticks arrive before a bar closes — [bar execution](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/develop/docs/concepts/backtesting/bar-execution.md)

### Inferences
- Cheapest reliable multi-year bid/ask set: Dukascopy ticks via dukascopy-node or dukascopy-python, stored as Parquet. Budget one to two evenings of quality checks per pair.
- Quality checks to run before trusting any FX set (derived from the defects above): confirm timestamps are UTC and convert to America/New_York for session and 5 pm logic (never store EST-without-DST as HistData does); drop or flag quotes inside Friday 22:00 - Sunday 21:00 UTC; detect gaps longer than N minutes during liquid hours; reject ticks where ask <= bid or spread exceeds a per-pair cap; check JPY and metal price scaling against a known price; build bars from bid and ask separately and keep both (mid = average), rather than from mid ticks.
- Research on Dukascopy and trading on OANDA or CME introduces a feed mismatch: spreads, rollover-hour behaviour and exact highs/lows differ. A sensible control is to re-run the final strategy on OANDA's own bid/ask candles (or QuantConnect's OANDA data) and on IBKR/Databento futures bars for the futures path, and require the edge to survive on both.
- HistData M1 is acceptable only for coarse, long-history sanity checks: bid-only bars hide the spread and the fixed-EST clock shifts sessions by an hour for half the year relative to New York time.
- For CME micro FX futures there is no free tick history; IBKR bars (free with account) are the cheapest, Databento is the cleanest paid route.

### Gaps
- histdata.com itself could not be opened (503 / timeout), so its timezone and bid-only claims rest on the downloader READMEs.
- Dukascopy's current official documentation on timezone (UTC) and download limits was not retrieved; forum evidence is dated (2012-2018).
- Darwinex tick data (availability to US residents, price) could not be read (JS-rendered page); Tickstory's current pricing was not checked.
- OANDA v20 candle history depth per granularity is not stated on the API page; QuantConnect's "from January 2007" is the only depth evidence found.
- How far back IBKR 1-minute IDEALPRO and CME micro FX bars go was not established; a `reqHeadTimestamp` test is needed.
- FirstRate's one-off bundle price and Databento's pay-as-you-go per-GB rates for CME FX were not obtained.

---

## 4. Which indicator libraries are safe for live incremental use and which commonly cause backtest / live mismatches?

### Takeaway
Safe for incremental live use: TA-Lib 0.8.x's new handle-based Streaming API, talipp, streaming_indicators (small set), NautilusTrader's and LEAN's built-in indicators. Batch-only libraries (pandas-ta-classic, `ta`, finta, polars-ta/polars-talib, `technical`, vectorbt's indicator factory, stock-indicators) are fine in live trading only if recomputed on closed bars with enough warm-up; swing, zigzag, pivot and smart-money-concept tools look ahead by construction and are the usual source of backtest/live mismatches.

### Cited Findings

**Indicator library table**

| Library | Repo / PyPI | Language | Licence | Stars | Latest release | Last commit | Mode | Notes for intraday FX |
|---|---|---|---|---|---|---|---|---|
| TA-Lib (C) | [TA-Lib/ta-lib](https://github.com/TA-Lib/ta-lib) | C | BSD-3-Clause | 1.7k | v0.8.3, Oct 2026 | 2026-11-20 | Batch + stream | Reference implementation others test against. |
| TA-Lib (Python wrapper) | [TA-Lib/ta-lib-python](https://github.com/TA-Lib/ta-lib-python) / [PyPI](https://pypi.org/project/TA-Lib/) | Cython | BSD-2-Clause | 12k | 0.8.3.post1, 2026-11-21 | 2026-11-20 | Batch + stream | Binary wheels; 200+ indicators and candlestick patterns. |
| pandas-ta (original) | repo reported "not found" by shields / [PyPI](https://pypi.org/project/pandas-ta/) | Python | PyPI licence field empty; licence link points to pandas-ta.dev | n/a | 0.4.71b0, 2025-09-14 | unknown | Batch | Only two beta releases remain on PyPI; Python >=3.12. Uncertain status. |
| pandas-ta-classic | [xgboosted/pandas-ta-classic](https://github.com/xgboosted/pandas-ta-classic) / [PyPI](https://pypi.org/project/pandas-ta-classic/) | Python | MIT | 495 | 0.9.0, 2026-10-28 | 2026-11-19 | Batch | 224 indicators + 62 native candlestick patterns; Python >=3.11; optional numba. |
| pandas-ta-openbb | [PyPI](https://pypi.org/project/pandas-ta-openbb/) | Python | MIT | not checked | 0.4.25, 2026-09-28 | — | Batch | "Fork of pandas-ta for use with NumPy 2 and OpenBB." |
| ta | [bukosabino/ta](https://github.com/bukosabino/ta) / [PyPI](https://pypi.org/project/ta/) | Python | MIT | 5.3k | 0.11.0, 2023-11-02 | Mar 2026 | Batch | No release for three years. |
| talipp | [nardew/talipp](https://github.com/nardew/talipp) / [PyPI](https://pypi.org/project/talipp/) | Python | MIT | 546 | 2.7.0, 2025-09-09 | Sep 2025 | Incremental | Append, update-last, remove; indicator chaining; auto-sampling. |
| streaming_indicators | [mr-easy/streaming_indicators](https://github.com/mr-easy/streaming_indicators) / [PyPI](https://pypi.org/project/streaming-indicators/) | Python | MIT | 153 | 0.1.8, 2025-03-31 | Oct 2026 | Incremental | Small set (SMA, EMA, RSI, ATR, SuperTrend, VWAP...); `update` and non-committing `compute`. |
| tulipy / Tulip Indicators | [TulipCharts/tulipindicators](https://github.com/TulipCharts/tulipindicators), [PyPI tulipy](https://pypi.org/project/tulipy/) | C + Python | LGPL-3.0 | 944 (C lib) | C lib v0.9.1 Jan 2022; tulipy 0.4.0, 2019-04-11 | Jan 2024 | Batch | Stale. A jesse-ai fork (v0.4.6.2, Jul 2021, 22 stars) exists. |
| finta | [peerchemist/finta](https://github.com/peerchemist/finta) / [PyPI](https://pypi.org/project/finta/) | Python | LGPL-3.0 | 2.3k | 1.3, 2021-04-03 | Jul 2022 | Batch | Stale. |
| polars-ta | [wukan1986/polars_ta](https://github.com/wukan1986/polars_ta) / [PyPI](https://pypi.org/project/polars-ta/) | Python | MIT | 272 | 0.5.18, 2026-10-20 | Oct 2026 | Batch | Indicators as polars expressions plus TA-Lib wrappers. |
| polars-talib | [Yvictor/polars_ta_extension](https://github.com/Yvictor/polars_ta_extension) / [PyPI](https://pypi.org/project/polars-talib/) | Rust/Python | MIT | 259 | 0.2.1, 2026-10-18 | Oct 2026 | Batch | "bundles TA-Lib 0.8.1: all 201 batch indicators". |
| polars-trading | [ngriffiths13/polars-trading](https://github.com/ngriffiths13/polars-trading) | Rust/Python | not specified | 62 | 0.2.0, 2025-09-02 | Sep 2025 | Batch | Bar construction and AFML-style utilities rather than indicators. |
| vectorbt IndicatorFactory | [polakowo/vectorbt](https://github.com/polakowo/vectorbt) | Python/numba | Apache 2.0 + Commons Clause | 9.9k | 1.2.1, 2026-11-11 | Nov 2026 | Batch | Wraps TA-Lib/pandas-ta/custom functions over parameter grids. |
| NautilusTrader indicators | [nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader) | Rust (+ Python) | LGPL-3.0 | 32k | 1.231.0 / 2.0.0rc9 | 2026-11-23 | Incremental | Same indicator objects in backtest and live. |
| LEAN indicators | [QuantConnect/Lean](https://github.com/QuantConnect/Lean) | C# (+ Python API) | Apache-2.0 | 23k | continuous | 2026-11-20 | Incremental | Docs list "Supported Indicators" and candlestick patterns. |
| stock-indicators (Python) | [facioquo/stock-indicators-python](https://github.com/facioquo/stock-indicators-python) / [PyPI](https://pypi.org/project/stock-indicators/) | Python over .NET | Apache-2.0 | 405 | 1.3.5, 2025-06-02 | Nov 2026 | Batch | Requires the .NET SDK 8.0 or newer. Parent .NET library v3.1.0 (Nov 2026), 1.3k stars. |
| technical (freqtrade) | [freqtrade/technical](https://github.com/freqtrade/technical) / [PyPI](https://pypi.org/project/technical/) | Python | GPL-3.0 | 1k | 1.7.0, 2026-07-21 | Nov 2026 | Batch | Indicators "collected from all over github" plus timeframe-resampling utilities. |
| kand | [kand-ta/kand](https://github.com/kand-ta/kand) / [PyPI](https://pypi.org/project/kand/) | Rust + Python | Apache-2.0 OR MIT | 557 | 0.2.2, 2025-03-04 | Jan 2026 | not verified | Newer Rust TA library; quiet since early 2026. |
| ta-rs | [greyblake/ta-rs](https://github.com/greyblake/ta-rs) | Rust | MIT | 877 | none tagged | Oct 2022 | Incremental (by design) | Stale. |

**Price-action / candlestick tooling**

| Library | Repo / PyPI | Licence | Stars | Latest | Mode and pitfalls |
|---|---|---|---|---|---|
| TA-Lib candlestick patterns | (part of TA-Lib) | BSD | — | 0.8.3 | Batch and stream; patterns confirm on bar close. |
| smart-money-concepts | [joshyattridge/smart-money-concepts](https://github.com/joshyattridge/smart-money-concepts) / [PyPI](https://pypi.org/project/smartmoneyconcepts/) | MIT | 2.3k | 0.0.27, 2026-04-03 | Batch; **look-ahead by construction** (see quote below). |
| ZigZag | [jbn/ZigZag](https://github.com/jbn/ZigZag) / [PyPI](https://pypi.org/project/zigzag/) | BSD-3-Clause | 476 | 0.3.2, 2022-08-06 | Batch peak/valley finder; stale (last commit Aug 2022). |
| py-market-profile | [bfolkens/py-market-profile](https://github.com/bfolkens/py-market-profile) / [PyPI](https://pypi.org/project/marketprofile/) | BSD (per PyPI) | 413 | 0.2.0, 2020-01-19 | Batch; last commit Nov 2026 but no release since 2020. |
| trendln | [PyPI](https://pypi.org/project/trendln/) | MIT | not checked | 0.1.18, 2026-04-09 | Batch support/resistance trend-line calculator. |
| TechnicalAnalysisAutomation | [neurotrader888/TechnicalAnalysisAutomation](https://github.com/neurotrader888/TechnicalAnalysisAutomation) | MIT | 584 | no releases | Research scripts; last commit Apr 2023. |
| PatternPy | [keithorange/PatternPy](https://github.com/keithorange/PatternPy) | not identifiable | 482 | no releases | Last commit Jun 2023. |
| talipp "Pivots High/Low" | (part of talipp) | MIT | — | 2.7.0 | Incremental pivot detection. |

- TA-Lib Python install: "Binary wheels include the TA-Lib C library and do not require a compiler or a separate TA-Lib C installation... starting with version 0.6.5, we now build binary wheels... Starting with version 0.8.3, this library is statically linked into the extension"; 0.8.x pairs with TA-Lib C 0.8.x and numpy 2 — [ta-lib-python README](https://raw.githubusercontent.com/TA-Lib/ta-lib-python/master/README.md)
- TA-Lib Streaming API: "keeps a handle per indicator instead of recomputing from the whole array. Opening one costs a pass over the history; every bar after that is O(1), and each value it produces is identical to the one the Function API reports for that bar"; `s.update(price)` commits a closed bar, `s.peek(forming)` evaluates a forming bar "committing nothing", `s.copy()` forks state — [ta-lib-python README](https://raw.githubusercontent.com/TA-Lib/ta-lib-python/master/README.md)
- TA-Lib unstable period: functions with an unstable period start with the extra setting at 0 until changed with `set_unstable_period()`; an auto level such as `UNSTABLE_AUTO_PREC_4` is available; settings are process-wide — [ta-lib-python README](https://raw.githubusercontent.com/TA-Lib/ta-lib-python/master/README.md)
- TA-Lib describes itself as "Native in five languages: C/C++, Java, C#, Rust and TypeScript" — [ta-lib-python README](https://raw.githubusercontent.com/TA-Lib/ta-lib-python/master/README.md)
- talipp: "calculates new indicators' values exclusively based on the delta input data ... requires O(1) time to produce new values"; supports "appending new values", "updating the last input value", "removing arbitrary number of the input values" — [talipp README](https://raw.githubusercontent.com/nardew/talipp/main/README.md)
- streaming_indicators: `update` "To add new data point in the indicator computation" and `compute` "Compute indicator value with a new data point, but don't update it's state" — [streaming_indicators README](https://raw.githubusercontent.com/mr-easy/streaming_indicators/main/README.md)
- pandas-ta-classic: "This is the classic/community maintained version of the popular pandas-ta library"; "224 indicators and utility functions and 62 native candlestick patterns ... no TA-Lib required"; optional `talib=True` and numba acceleration — [pandas-ta-classic README](https://raw.githubusercontent.com/xgboosted/pandas-ta-classic/main/README.md)
- Original pandas-ta: PyPI lists only releases 0.4.67b0 and 0.4.71b0, homepage `pandas-ta.dev`, repository field still `github.com/twopirllc/pandas-ta`, description footer "Copyright © 2025 - Pandas TA" with the licence at `pandas-ta.dev/legal/license` — [pandas-ta PyPI JSON](https://pypi.org/pypi/pandas-ta/json). shields.io returned "repo not found" for `twopirllc/pandas-ta` on 2026-11-23 — [shields endpoint](https://img.shields.io/github/stars/twopirllc/pandas-ta.json)
- A fork's PyPI page carries the upstream notice that "current and past levels of support are unsustainable... Unless significant additional support is provided by July 1st, 2026, this widely used library will be archived" — [pandas-ta-kozmoai on PyPI](https://pypi.org/project/pandas-ta-kozmoai/)
- smart-money-concepts: "A swing high is when the current high is the highest high out of the swing_length amount of candles before and after"; `swing_length` is "the amount of candles to look back and forward" (example uses 50) — [smart-money-concepts README](https://raw.githubusercontent.com/joshyattridge/smart-money-concepts/master/README.md)
- TradingView's own guidance classes pivot-based scripts that plot into the past as "potentially misleading" repainting — [Pine Script repainting docs](https://www.tradingview.com/pine-script-docs/concepts/repainting/)
- stock-indicators requires ".NET SDK (8.0 or newer)" — [stock-indicators-python README](https://raw.githubusercontent.com/facioquo/stock-indicators-python/main/README.md)
- polars-talib bundle statement — [polars_ta_extension README](https://raw.githubusercontent.com/Yvictor/polars_ta_extension/master/README.md); technical description — [freqtrade/technical README](https://raw.githubusercontent.com/freqtrade/technical/main/README.md)

### Inferences
- **Best choice: TA-Lib 0.8.x** — one implementation for research (function API) and live (stream API) with documented value identity removes the most common mismatch (different maths in backtest and live). **Alternative: talipp** — pure Python, O(1), supports "update last value" for forming bars; cross-check its values against TA-Lib once.
- Common causes of backtest/live mismatch, by library class: (1) batch libraries recomputed on a short live window — EMA/RSI/ATR-type recursive indicators differ from a long-history backtest until warmed up (TA-Lib exposes this explicitly as the "unstable period", default 0); (2) computing on the forming bar live but on closed bars in the backtest; (3) swing/zigzag/pivot/SMC functions that need N future bars — a `swing_length=50` swing is only knowable 50 bars later, so any backtest that reads the label at the swing bar is looking ahead; (4) multi-timeframe merges that stamp a higher-timeframe bar at its open; (5) market-profile/volume-profile on spot FX, where "volume" is tick count or quoted size, not traded volume.
- ZigZag and py-market-profile are batch tools with no incremental mode documented; the last zigzag leg repaints until confirmed. Use them for research labelling only, or re-implement with an explicit confirmation delay.
- Avoid depending on the original pandas-ta in 2026: its repository is not reachable through shields, its PyPI history has been reduced to two betas with no declared licence, and an archive deadline of 1 July 2026 was announced. Use pandas-ta-classic (MIT, active) if the pandas-ta API is wanted.
- stock-indicators (needs .NET), tulipy and finta (stale since 2021-2022) and `ta` (no release since 2023) add risk without benefit over TA-Lib now that TA-Lib installs from wheels.
- No maintained open library for FX sessions, opening-range or initial-balance levels was found; these are small enough to write and test by hand with `zoneinfo`.

### Gaps
- pandas-ta.dev could not be opened (host not resolvable from this session's network), so the original project's current licence terms and whether the repository was archived, renamed or made private are unconfirmed.
- Incremental behaviour of LEAN and NautilusTrader indicators is asserted from their event-driven design, not from a page quoted here; the look-ahead behaviour of smart-money-concepts functions other than `swing_highs_lows` (order blocks, BOS/CHoCH, liquidity) was not individually checked.
- kand's API mode (batch vs incremental), mintalib 0.1.13 (2026-09-15) and numta 0.2.0 (2026-02-27) were noted on PyPI but not evaluated — [mintalib](https://pypi.org/project/mintalib/), [numta](https://pypi.org/project/numta/).
- Whether finta is formally archived on GitHub was not verified (only last-commit date, July 2022).
- No dedicated, maintained volume-profile or support/resistance library with FX-appropriate handling was identified.

---

## 5. What are current typical costs a strategy must clear: OANDA US spreads by session, OANDA financing, and CME micro FX futures all-in cost per round trip at Interactive Brokers, Tradovate and NinjaTrader?

### Takeaway
On 2026-11-23 OANDA US displayed spread-only spreads of 1.4 pips EUR/USD, 2.0 pips GBP/USD and 1.4 pips USD/JPY, with financing equal to the tom-next rate plus a 1% annualised admin fee charged at 5 pm ET (triple on Wednesday). A CME micro FX future at IBKR costs $0.40 per side ($0.15 commission + $0.24 exchange + $0.01 regulatory), i.e. $0.80 per round trip before the bid/ask spread; Tradovate and NinjaTrader charge $0.39 / $0.29 / $0.09 per side commission by plan plus exchange, clearing and NFA fees, with the exact all-in micro FX figure not retrievable in this session.

### Cited Findings

**OANDA US spot**
- Spread-only pricing table shown on the US pricing page: AUD/USD 1.4, EUR/GBP 1.7, EUR/JPY 1.8, EUR/USD 1.4, GBP/JPY 3.1, GBP/USD 2.0, NZD/USD 1.7, USD/CAD 2.2, USD/CHF 1.8, USD/JPY 1.4 (pips; the page does not state whether these are averages or over what period) — [OANDA US pricing](https://www.oanda.com/us-en/trading/our-pricing/)
- "At certain times and in certain market conditions, our spreads could be wider than usual. This includes the opening and closing of markets and major international or geopolitical events" — [OANDA US pricing](https://www.oanda.com/us-en/trading/our-pricing/)
- A reviewer using OANDA's trailing-average tool found an average EUR/USD spread of 1.69 pips for August 2025 (taken from a search-result summary; the review page itself was not opened and the attribution to this URL is probable, not certain) — [ForexBrokers.com OANDA review](https://forexbrokers.com/reviews/oanda)
- Core spreads + commission model (US help centre): requires a deposit or balance of at least 10,000 USD; core spreads "as low as 0.0" on selected majors; "A commission of 0.70 USD per 10,000 units is applied to each 'leg' of a trade"; worked example: 10,000 EUR/USD at a 0.2 pip spread costs 0.20 + 1.40 = 1.60 USD round trip — [OANDA US help: core spreads + commission](https://help.oanda.com/us/en/faqs/spreads-commission.htm)
- Third-party reviews (seen only as search-result summaries; exact page attribution uncertain) instead cite a core commission of $5 per $100,000 per side, which conflicts with the US help page figure of $7 per 100,000 per side — [BrokerAnalysis OANDA spreads and commissions](https://brokeranalysis.com/broker-review/oanda/spreads-and-commissions/), [ForexBrokers.com OANDA review](https://forexbrokers.com/reviews/oanda); contradicted by [OANDA US help](https://help.oanda.com/us/en/faqs/spreads-commission.htm)
- Elite Trader rebates run from $5 to $17 per million at 10M+ monthly volume — [OANDA US pricing](https://www.oanda.com/us-en/trading/our-pricing/)
- Financing: positions open at 5 pm ET are charged or credited; "Financing cost or credit = position value x applicable funding rate x 1/365"; funding rates are "a blend of underlying liquidity providers' tom-next swap rates, adjusted by our annualised admin fee"; average annualised admin fee is 1.00% for ordinary pairs, 2.00% for CZK/HUF/SAR/THB/ZAR pairs and 4.00% for TRY pairs — [OANDA US financing fees](https://www.oanda.com/us-en/trading/financing-fees/)
- "If you hold a position on Wednesday at 5 pm ET, the funding rate will typically be three times the amount... There are no financing charges or credits on Saturday or Sunday"; holidays can change the multiple — [OANDA US financing fees](https://www.oanda.com/us-en/trading/financing-fees/)
- OANDA's worked example: long 100,000 EUR/USD at a -3.00% long rate with EUR/USD at 1.15826 costs 9.52 USD for one night — [OANDA US financing fees](https://www.oanda.com/us-en/trading/financing-fees/)
- An inactivity fee applies only after 12 months without trading and not while a position is open — [OANDA US financing fees](https://www.oanda.com/us-en/trading/financing-fees/)
- US leverage caps: 50:1 on major pairs and 20:1 on others; OANDA margin rates "start from just 2% on EUR/USD" — [OANDA US spreads and margin](https://www.oanda.com/us-en/trading/spreads-margin/), [OANDA US pricing](https://www.oanda.com/us-en/trading/our-pricing/)
- OANDA publishes a historical spreads tool (minimum, average, maximum over recent months) — [OANDA US historical spreads](https://oanda.com/us-en/trading/historical-spreads)

**CME micro FX futures — Interactive Brokers**
- Commission for "E-Micro FX Futures": USD 0.15 per contract for up to 1,000 contracts a month (tiered and fixed identical), then 0.12 (1,001-10,000), 0.08 (10,001-20,000), 0.05 (above 20,000) — [IBKR futures commissions](https://www.interactivebrokers.com/en/pricing/commissions-futures.php)
- Exchange fee pass-through for "E-micro Forex Futures M6A, M6B, M6E, MIR, MCD, MJY, MSF, MNH, M6C, M6J, M6S": USD 0.24 per contract; regulatory fee recovery charge USD 0.01 for all products (NFA); for comparison standard FX futures are USD 1.60 and E-mini FX (E7, J7) USD 0.85 — [IBKR CME fees](https://www.interactivebrokers.com/en/accounts/fees/CME.php)

**CME micro FX futures — Tradovate and NinjaTrader**
- Tradovate commission for "Micros & CME E-nano Index Futures": $0.39 per side (Free plan), $0.29 (Monthly, $99/month), $0.09 (Lifetime, $1,499 one-time or 4 x $499); "Exchange, clearing, and NFA fees still apply" — [Tradovate pricing](https://www.tradovate.com/pricing/)
- NinjaTrader lists identical commissions and plan prices ($0.39 / $0.29 / $0.09 per micro per side; $0, $99/month, $1,499 lifetime) and adds exchange, clearing and NFA fees on top — [NinjaTrader pricing](https://ninjatrader.com/pricing/)
- NinjaTrader's per-contract all-in schedule is dated "as of August 14, 2026" and "updated quarterly"; the table is rendered client-side and the M6E row could not be read — [NinjaTrader commissions](https://ninjatrader.com/pricing/commissions/)
- NinjaTrader's own worked example for another micro (MCL, Free plan): $0.39 commission plus $0.61 exchange and NFA fees, all-in $1.19 per contract per side (from a search-result summary of the page; the page was not opened directly) — [NinjaTrader futures trading costs blog](https://ninjatrader.com/futures/blogs/futures-trading-costs/)
- Tradovate API automation adds $25/month and needs $1,000 minimum equity — [CrossTrade blog](https://crosstrade.io/blog/tradovate-api-add-on-fee-cme-license-webhook/)

### Inferences
- **OANDA spread-only, per round trip (spread crossed once in total):** EUR/USD 1.4 pips = about $1.40 per 10,000 units; GBP/USD 2.0 pips = about $2.00 per 10,000; USD/JPY 1.4 pips = about 140 JPY per 10,000 units (roughly $0.90 at a USD/JPY rate near 155; the rate was not checked today). Treat 1.4 as a floor for liquid hours: an independent August 2025 measurement averaged 1.69 pips on EUR/USD.
- **OANDA core pricing is not obviously cheaper for small accounts:** $0.70 per 10,000 per leg is $1.40 per round trip per 10,000 units, which already equals 1.4 pips on EUR/USD before any core spread; on GBP/USD it is 1.4 pips plus the core spread against 2.0 pips spread-only (a modest saving); on USD/JPY $1.40 exceeds the roughly $0.90 spread-only cost. It also requires $10,000. This is arithmetic on OANDA's published figures, not an OANDA statement; and the $7-per-100k figure conflicts with third-party reviews, so confirm with OANDA before relying on it.
- **Financing for an intraday system:** with a 1% annualised admin fee, the mark-up alone on 10,000 EUR/USD (about $11,600 notional) is roughly $0.32 per night ($0.95 on Wednesday), on top of the tom-next differential. A strategy that is flat by 5 pm ET pays none; one that holds through the roll pays it plus the wide rollover-hour spread.
- **IBKR micro FX all-in:** $0.15 + $0.24 + $0.01 = $0.40 per side, $0.80 per round trip per contract. For M6E this is fees only; crossing a one-tick bid/ask spread adds one tick. Using contract terms from prior knowledge (M6E = 12,500 EUR, tick 0.0001 = $1.25; not re-verified today because cmegroup.com returned 403), the fee portion equals about 0.64 pip and a one-tick spread about 1.0 pip, giving roughly $2.05 or 1.6 pips per round trip for a market-order trader, versus about $1.75 for 12,500 units at OANDA's 1.4-pip spread. Futures become cheaper when entries or exits rest as limit orders (earning rather than paying the tick) and they avoid dealer financing mark-ups, but the micro contract's fixed size (about 12,500 EUR) is coarser than OANDA's single-unit sizing.
- **Tradovate / NinjaTrader micro FX estimate:** commission $0.39 (Free plan) + exchange $0.24 (CME rate as passed through by IBKR) + NFA and clearing. The MCL example implies about $0.19 of clearing/other on top of commission plus exchange and NFA, so a Free-plan M6E trade is plausibly around $0.80-0.85 per side ($1.60-1.70 per round trip), roughly double IBKR. This is an estimate, not a published figure. The $99/month plan only pays back above roughly 500 round-trip contracts a month ($0.20 saved per round trip).
- **Hurdle rule of thumb from these numbers:** a system trading EUR/USD at OANDA needs an average gross edge comfortably above about 1.5-1.7 pips per round trip (more for GBP/USD at about 2.0+, more again around rollover, the Asian session and news), before slippage. Strategies with average trades under roughly 5-6 pips are highly cost-sensitive at these levels.

### Gaps
- **Spreads by session (London, New York, Asia, rollover hour) were not obtained from a primary source.** OANDA's historical-spreads tool is JS-rendered and returned no numbers; the only hourly figure found was an unverified third-party one-week sample. The practical fix is to compute hourly spread statistics yourself from OANDA bid/ask M1 candles (`price=BA`) over several months, split by New York-time hour.
- OANDA does not state on the pricing page whether the 1.4 / 2.0 / 1.4 figures are typical, average or minimum, nor the measurement window.
- The OANDA core commission figure ($0.70 per 10,000 per leg) conflicts with third-party reports of $5 per 100,000; not resolved.
- Exact Tradovate and NinjaTrader all-in per-side rates for M6E, M6B, M6A and MJY (including clearing and NFA fees) could not be read (tables are client-side rendered; Tradovate's all-in page URL returned 404).
- CME contract specifications (sizes, tick values, trading hours) and the CME fee schedule PDFs returned HTTP 403 and were not verified in this session; the IBKR pass-through page was used as the source for the $0.24 exchange fee.
- Typical quoted spread and depth on M6E, M6B, M6A and MJY by session, and intraday margin for micro FX at each broker, were not researched.
- IBKR market-data subscription cost for CME FX futures (needed for live micro FX trading) was not checked.
