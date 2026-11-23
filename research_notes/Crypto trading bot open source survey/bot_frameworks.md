# Open-source automated trading bot frameworks (crypto and liquid markets), status as of 23 November 2026

Method notes for the report writer:
- All GitHub star/fork counts are the rounded figures displayed on each repository page when fetched on 2026-11-23. They are "as displayed", not API-exact.
- Several GitHub release pages show day and month only. Where the year is not embedded in the tag name or release body, I say "year not shown on page; presumed 2026" rather than asserting it.
- I could not retrieve any Reddit (r/algotrading, r/freqtrade) or Hacker News threads through search in this session. User-experience evidence below comes from GitHub issues, project FAQs and blogs, and is labelled as anecdote.
- Anything I know only from background knowledge and did not verify in this session is in "Gaps" or explicitly labelled "unverified".

## Which frameworks are genuinely maintained and widely used in late 2026, and which are abandoned?

### Takeaway
The actively maintained, widely adopted tier in November 2026 is freqtrade (57.2k stars, monthly releases), NautilusTrader (31.8k, roughly fortnightly release candidates of v2), QuantConnect LEAN (22.7k, commits within the last 3 days), Hummingbot (21.4k, releases every ~2 months), CCXT (45.0k, the plumbing under most of the others), plus smaller but live projects Jesse, OctoBot, Passivbot, Lumibot, hftbacktest, OpenTrader and the NostalgiaForInfinity strategy repo. Gekko, Zenbot and Kelp are formally archived; Backtrader (last commit April 2023), Blankly (last commit December 2024), Krypto-trading-bot (last commit December 2024), Tribeca and Superalgos (stable release stuck at 1.6.1, only bot/doc commits in 2026) are stale or effectively abandoned.

### Cited Findings

#### Summary table (figures as displayed on GitHub, fetched 2026-11-23)

| Framework | Repo | License | Stars / forks | Latest release or commit (date) | Status |
|---|---|---|---|---|---|
| freqtrade (+FreqAI) | https://github.com/freqtrade/freqtrade | GPL-3.0 | 57.2k / 11.8k | 2026.10 (30 Oct 2026) | Active, monthly releases |
| CCXT (library) | https://github.com/ccxt/ccxt | MIT | 45.0k / 9.0k | version not captured | Active |
| NautilusTrader | https://github.com/nautechsystems/nautilus_trader | LGPL-3.0 | 31.8k / 4.3k | v2.0.0rc9 (10 Nov 2026, pre-release) | Very active; v2 still RC |
| Backtrader | https://github.com/mementum/backtrader | GPL-3.0 | 23.8k / 5.3k | last commit 19 Apr 2023 | Stale |
| QuantConnect LEAN | https://github.com/QuantConnect/Lean | Apache-2.0 | 22.7k / 5.4k | last commits 20 Nov 2026 | Very active |
| Hummingbot | https://github.com/hummingbot/hummingbot | Apache-2.0 | 21.4k / 5.2k | v2.18.0 (18 Nov; year presumed 2026) | Active |
| Gekko | https://github.com/askmike/gekko | MIT | 10.2k / 3.8k | archived 16 Feb 2020 | Dead |
| Jesse | https://github.com/jesse-ai/jesse | MIT (core); live plugin proprietary | 8.8k / 1.3k | tag v3.7.0 (23 Nov 2026) | Active |
| Zenbot | https://github.com/DeviaVir/zenbot | MIT | 8.2k / 1.9k | archived 15 Feb 2022 | Dead |
| OctoBot | https://github.com/Drakkar-Software/OctoBot | GPL-3.0 | 7.0k / 1.3k | 3.0.0-beta3 (08 Oct; year presumed 2026) | Active |
| Superalgos | https://github.com/Superalgos/Superalgos | Apache-2.0 | 5.8k / 6.0k | stable 1.6.1; last commit 7 May 2026 (docs) | Near-dormant |
| binance-trading-bot (chrisleekr) | https://github.com/chrisleekr/binance-trading-bot | Apache-2.0 | 5.6k / 1.2k | release date not captured | Appears active |
| hftbacktest | https://github.com/nkaz001/hftbacktest | MIT | 5.1k / 978 | release date not captured | Appears active |
| Tribeca | https://github.com/michaelgrosner/tribeca | license file present, type not verified | 4.1k / 923 | date not visible; README targets Node 7.8 | Effectively abandoned |
| Krypto-trading-bot | https://github.com/ctubio/Krypto-trading-bot | MIT (plus "non-free" components, paid unlock) | 3.7k / 828 | last commit 15 Dec 2024 | Stale |
| NostalgiaForInfinity (strategy) | https://github.com/iterativv/NostalgiaForInfinity | GPL-3.0 | 3.5k / 768 | commits 23 Nov 2026 | Very active |
| OpenTrader | https://github.com/Open-Trader/opentrader | Apache-2.0 | 2.9k / 354 | v1.0.0-beta.29 (06 Mar; year not shown) | Beta, hobby project |
| Blankly | https://github.com/blankly-finance/blankly | LGPL-3.0 | 2.5k / 312 | last commit 30 Dec 2024 | Abandoned in practice |
| Lumibot | https://github.com/Lumiwealth/lumibot | GPL-3.0 | 2.3k / 436 | v4.6.95 (22 Nov; year presumed 2026) | Very active |
| Passivbot | https://github.com/enarjord/passivbot | Unlicense (public domain) | 2.2k / 695 | v8.1.0 (10 Aug 2026) | Active |
| Kelp | https://github.com/stellar-deprecated/kelp | Apache-2.0 | 1.1k / 256 | archived 1 Feb 2024 | Dead |
| Hummingbot Dashboard | https://github.com/hummingbot/dashboard | Apache-2.0 | 373 / 215 | release not captured | Not archived |
| Hummingbot Gateway | https://github.com/hummingbot/gateway | Apache-2.0 | 266 / 293 | release not captured | Active (ships with Hummingbot) |

#### freqtrade and FreqAI
- 57.2k stars, 11.8k forks, 33,463 commits on `develop`; written in Python, requires Python 3.12+ — [freqtrade repo](https://github.com/freqtrade/freqtrade)
- License is GNU GPL version 3 — [freqtrade LICENSE](https://github.com/freqtrade/freqtrade/blob/develop/LICENSE)
- Last three releases: 2026.10 (30 Oct), 2026.9 (29 Sep), 2026.8 (31 Aug), i.e. monthly cadence. 2026.10 added websocket order book support, decoupled the bot loop from RPC messaging, dropped Python 3.11, and changed how strategy parameters are stored (breaking change) — [freqtrade releases](https://github.com/freqtrade/freqtrade/releases)
- Supported spot: Binance, BingX, Bitget, Bybit (and Bybit EU), Gate (and Gate EU), HTX, Hyperliquid, Kraken, OKX (and MyOKX EEA). Futures: Binance, Bitget, Bybit, Gate, Hyperliquid, Kraken, OKX. Community tested: Bitvavo, Kucoin. README: "potentially many others ... We cannot guarantee they will work" — [freqtrade repo](https://github.com/freqtrade/freqtrade)
- No options support and no AMM DEX support are listed; Hyperliquid is the only DEX — [freqtrade repo](https://github.com/freqtrade/freqtrade)
- Designed for candle-based (OHLCV) directional strategies written as pandas dataframe logic with callbacks; README disclaimer: "This software is for educational purposes only", recommends starting in dry-run and having Python knowledge — [freqtrade repo](https://github.com/freqtrade/freqtrade)
- Risk controls ("Protections"): StoplossGuard (halts trading after N stoploss exits in a lookback window, across all pairs by default), MaxDrawdown (halts trading when drawdown exceeds `max_allowed_drawdown`; "equity" mode recommended for new setups), LowProfitPairs, CooldownPeriod. The docs do not use the term "kill switch" — [freqtrade plugins docs](https://www.freqtrade.io/en/stable/plugins/)
- Stoploss-on-exchange support varies: Binance spot (stop-loss-limit) and futures (stop-limit/stop-market); Kraken spot and Kraken Futures; OKX spot and futures; Bybit futures only (not spot); Hyperliquid futures only — [freqtrade exchange notes](https://www.freqtrade.io/en/stable/exchanges/)
- FreqAI: module that trains ML models (scikit-learn, CatBoost, XGBoost, LightGBM, any Python library) and retrains them on a schedule during live/dry runs on a separate thread; backtesting emulates the periodic retraining. Cannot be combined with dynamic VolumePairlists that add/remove pairs; the example strategy is "for showcasing", not production; the page makes no performance claims and does not discuss overfitting — [FreqAI docs](https://www.freqtrade.io/en/stable/freqai/)
- Hyperopt uses Optuna (NSGAIIISampler) with loss functions including Sharpe, Sortino, Calmar, MaxDrawDown, ProfitDrawDown, MultiMetric; docs warn that over-precise parameter values "will usually result in overfitted results" and that results usually stop improving after 500 to 1000 epochs — [freqtrade hyperopt docs](https://www.freqtrade.io/en/stable/hyperopt/)

#### Hummingbot (Strategy V2, Dashboard, Gateway, API, Condor)
- 21.4k stars, 5.2k forks, Apache-2.0, Python — [hummingbot repo](https://github.com/hummingbot/hummingbot)
- Last three releases: v2.18.0 (18 Nov), v2.17.0 (22 Sep), v2.16.0 (29 Jul); the page shows no year (presumed 2026). v2.18.0 added a unified Bitget connector, moved Derive connectors to Derive's v3 API, and fixed "backtest stop-loss pricing", an API throttler race condition and several security issues — [hummingbot releases](https://github.com/hummingbot/hummingbot/releases)
- Connectors: sponsor connectors are Backpack, Binance, Bitget, Gate.io, KuCoin, OKX (CEX spot+perp), Derive and Hyperliquid (CLOB DEX spot+perp), XRP Ledger, Meteora, Orca. Other CEX spot: BingX, Bitrue, Bitstamp, BTC Markets, Bybit, Coinbase, Foxbit, Gemini, HTX, Kraken, MEXC, NDAX. Other perp: Aevo, Architect, Bybit, Decibel, EVEDEX, GRVT, Pacifica, dYdX, Injective Helix, Lighter. AMM/router: 0x, Balancer, Curve, DFlow, Jupiter, OKX DEX, PancakeSwap, Raydium, Titan, Uniswap — [hummingbot repo](https://github.com/hummingbot/hummingbot)
- Strategy V2: Controllers are "reusable V2 strategies" built from Executors; Scripts are the other entry point (`on_tick`); V1 strategies are described as legacy templates that are "more rigid and less customizable" — [hummingbot docs](https://hummingbot.org/docs/)
- Executor types: Position, DCA, Grid, Arbitrage, TWAP, XEMM (cross-exchange market making) and LP Executor (CLMM liquidity provision on Meteora/Raydium, new in v2.13.0) — [hummingbot executors docs](https://hummingbot.org/strategies/v2-strategies/executors/)
- Risk control is per-position "triple barrier": stop loss, take profit, time limit, plus trailing stop (activation delta and trailing delta). On perps the executor manages the open position; on spot it places TP/SL orders after the entry fills — [PositionExecutor docs](https://hummingbot.org/strategies/v2-strategies/executors/positionexecutor/)
- Dashboard: "Application that helps you create, backtest, deploy, and manage Hummingbot instances", with Optuna optimisation and one-click paper/live deployment; 373 stars, not archived — [hummingbot dashboard repo](https://github.com/hummingbot/dashboard)
- Hummingbot API is described as the central hub for running bots; Condor is "AI harness for building and running agentic strategies and bot instances" and is presented in the docs as the recommended starting point (Telegram and web UI); an MCP server exposes the API to AI assistants; Quants Lab is the notebook sandbox for research/backtesting; paper trading is available in the client — [hummingbot repo](https://github.com/hummingbot/hummingbot); [hummingbot docs](https://hummingbot.org/docs/)
- Gateway: TypeScript middleware for DEXs, Apache-2.0, 266 stars; chains: Ethereum, Arbitrum, Avalanche, Base, BSC, Celo, Optimism, Polygon, Solana; connectors: Jupiter, Meteora, Raydium, PancakeSwap, Uniswap, 0x (route docs also name Orca, DFlow, OKX, Titan) — [hummingbot gateway repo](https://github.com/hummingbot/gateway)

#### Jesse
- 8.8k stars, 1.3k forks, MIT, Python with indicators in Rust; features listed: backtest "free of look-ahead bias", paper/live trading, Optuna optimisation with Ray, risk-management helper functions, spot and futures, DEX support — [jesse repo](https://github.com/jesse-ai/jesse)
- No GitHub "releases", but tags are frequent: v3.7.0 (23 Nov 2026), v3.6.1 (10 Nov 2026), v3.6.0 (3 Nov 2026) — [jesse tags](https://github.com/jesse-ai/jesse/tags)
- Live and paper trading run through "an official plugin" that is pre-built, and "access is limited to those with an active license"; the user registers on the Jesse website and sets `LICENSE_API_TOKEN` — [Jesse live trading docs](https://docs.jesse.trade/docs/livetrade)
- Live exchanges: Binance Spot, Binance US Spot, Bybit Spot, Coinbase Spot, Gate.io Spot, KuCoin Spot, Kraken Pro Spot; perps on Binance, Bybit (USDT and USDC), Gate.io, KuCoin, Kraken Pro Futures; plus Lighter, Apex Omni, Hyperliquid; Alpaca for US stocks/ETFs (public beta). Backtest data sources also include FMP, Massive and custom CSV — [Jesse supported exchanges](https://docs.jesse.trade/docs/supported-exchanges)
- Pricing of the live plugin could not be verified from the official page (HTTP 403). A third-party aggregator lists lifetime tiers at $899 / $999 / $1,599 but its wording is internally inconsistent — [toolradar Jesse pricing](https://toolradar.com/tools/jesse/pricing)

#### NautilusTrader
- 31.8k stars, 4.3k forks, LGPL-3.0; Rust-native core with Python control plane via PyO3 — [nautilus_trader repo](https://github.com/nautechsystems/nautilus_trader)
- Releases: v2.0.0rc9 (10 Nov 2026), rc8 (28/29 Oct 2026), rc7 (15 Oct 2026); all v2 entries are marked pre-release. rc9 added Python 3.15, a Kalshi adapter, a FinFeed prediction-market data adapter and Polymarket Protocol V2 — [nautilus_trader releases](https://github.com/nautechsystems/nautilus_trader/releases)
- README warnings: the project "is still under active development", "breaking changes can occur between releases", v2 release candidates are not recommended for production including live trading with real capital, and v1 receives only critical security backports during the transition — [nautilus_trader repo](https://github.com/nautechsystems/nautilus_trader)
- Integrations (status "stable" unless noted): AX Exchange, Betfair, Binance, Bybit, Coinbase, Deribit, Derive, dYdX, Hyperliquid, Interactive Brokers, Kraken, Lighter, OKX, Polymarket, Kalshi (beta); data: Databento, Tardis, CoinAPI (beta), FinFeed (beta) — [nautilus_trader repo](https://github.com/nautechsystems/nautilus_trader)
- Asset coverage therefore includes spot, perps, options (Deribit), regulated futures and equities via Interactive Brokers, and prediction markets — [nautilus_trader repo](https://github.com/nautechsystems/nautilus_trader)

#### OctoBot
- 7.0k stars, 1.3k forks, GPL-3.0, Python, open source "since 2018" — [OctoBot repo](https://github.com/Drakkar-Software/OctoBot)
- Latest releases: 3.0.0-beta3 (08 Oct, marked "Latest"), beta2 (06 Aug), beta1 (30 Jul); page shows no year (presumed 2026) and no change notes for beta3 — [OctoBot releases](https://github.com/Drakkar-Software/OctoBot/releases)
- Exchanges: 15+, including Binance (spot, futures), Coinbase (spot), Hyperliquid, MEXC, KuCoin, OKX, Binance US, Crypto.com, HTX, Bitget, BingX, CoinEx, BitMart, Phemex, Gate.io, Ascendex; Bybit listed as "currently unavailable" — [OctoBot repo](https://github.com/Drakkar-Software/OctoBot)
- Strategy types: grid, DCA, crypto baskets (index), TradingView alert trading, AI trading via OpenAI or Ollama models, separate market-making project; backtesting and paper trading built in; deployment by Docker image, executables, DigitalOcean one-click, Raspberry Pi; paid hosted offering at octobot.cloud and commercial licences for institutions — [OctoBot repo](https://github.com/Drakkar-Software/OctoBot)

#### Passivbot
- 2.2k stars, 695 forks, Unlicense ("free and unencumbered software released into the public domain"), Python and Rust — [passivbot repo](https://github.com/enarjord/passivbot)
- Releases: v8.1.0 (10 Aug 2026), v8.0.0 (14 Jul, year not shown), v7.11.0 (13 May 2026). v8.1.0 added live USDT perps on Bitunix and WEEX and hardened restart/PnL reconstruction — [passivbot releases](https://github.com/enarjord/passivbot/releases)
- Exchanges (perpetual futures): Bybit, OKX, Bitget, Bitunix, GateIO, Binance, Kucoin, Hyperliquid, WEEX, Lighter — [passivbot repo](https://github.com/enarjord/passivbot)
- Strategy: default `trailing_martingale` starts small and adds to the position as price moves against it within configured exposure limits; grid and trailing entries/closes; "contrarian market making" that does not predict trends; "forager" coin selection; "unstucking" realises small losses on stuck positions with a cap so balance does not fall below a set percentage under its past peak — [passivbot repo](https://github.com/enarjord/passivbot)
- A shared Rust orchestrator plans orders for both live trading and backtests; the optimizer runs thousands of backtests with an evolutionary algorithm — [passivbot repo](https://github.com/enarjord/passivbot)
- Third-party tracker notes that on leveraged futures Passivbot "may expose more than 100% of the wallet's funds" and warns against getting 20% in the first month then being liquidated in the next — [futuresboard passivbot page](https://ecoppen.github.io/futuresboard/passivbot)

#### QuantConnect LEAN
- 22.7k stars, 5.4k forks, Apache-2.0, C# engine with Python and C# strategies; `pip install lean` CLI runs `lean backtest` and `lean live` locally in Docker — [LEAN repo](https://github.com/QuantConnect/Lean)
- Most recent commits dated 20 November 2026 (e.g. "Send the opening part of a cross-zero trailing stop as a market order (#10203)") — [LEAN commits](https://github.com/QuantConnect/Lean/commits/master)
- Live brokerages documented by QuantConnect: crypto via Coinbase, Kraken, Bitfinex, Binance (spot and futures), Bybit (spot and futures), dYdX (futures); equities/options/futures via Interactive Brokers, TradeStation, Tastytrade, Tradier, Alpaca (equities, options, crypto), Charles Schwab, Public, Webull, Trading Technologies and others; QuantConnect paper trading covers equities, forex, CFD, crypto, futures. Binance US is not listed on that page — [QuantConnect brokerages docs](https://www.quantconnect.com/docs/v2/cloud-platform/live-trading/brokerages)

#### Superalgos
- 5.8k stars, 6.0k forks, Apache-2.0, 23,353 commits; visual strategy designer, charting, data mining, backtesting, paper trading, multi-server deployment; TensorFlow integration described as partial; has an SA token and "Social Trading Network"; tutorial uses Binance or Binance US — [Superalgos repo](https://github.com/Superalgos/Superalgos)
- Stable release is still 1.6.1; newest tags are automated "Beta v1.7.0" snapshots dated 28 to 30 Sep 2026 — [Superalgos releases](https://github.com/Superalgos/Superalgos/releases)
- Latest commits on master: 7 May 2026 (merge of a README link fix) and 23 Mar 2026 (docs fixes by "Beggar Hunter Bot") — [Superalgos commits](https://github.com/Superalgos/Superalgos/commits/master)

#### Dead or stale projects
- Gekko: 10.2k stars, MIT, "archived by the owner on Feb 16, 2020"; README: "This repo is not maintained anymore" — [gekko repo](https://github.com/askmike/gekko)
- Zenbot: 8.2k stars, MIT, "archived by the owner on Feb 15, 2022"; README: "project is no longer actively maintained" — [zenbot repo](https://github.com/DeviaVir/zenbot)
- Kelp (Stellar): 1.1k stars, Apache-2.0, Go, public archive, "archived by the owner on Feb 1, 2024"; supported Stellar DEX plus Kraken/Binance/Coinbase Pro via CCXT — [kelp repo](https://github.com/stellar-deprecated/kelp)
- Krypto-trading-bot: 3.7k stars, C++ "automated high frequency market making", spot only on Coinbase, Binance, Binance.US, BitMEX, Kraken, KuCoin, Bitfinex, Gate.io, HitBTC, Poloniex; MIT but requires agreeing to install "collaborative non-free software" and pay 0.00121 BTC per API key to unlock (otherwise order book updates once per 121 seconds) — [Krypto-trading-bot repo](https://github.com/ctubio/Krypto-trading-bot)
- Krypto-trading-bot last commits: 15 Dec 2024 (dependency bumps) and 23 Nov 2024 — [Krypto-trading-bot commits](https://github.com/ctubio/Krypto-trading-bot/commits/master)
- Tribeca: 4.1k stars, Node.js/TypeScript market maker for Coinbase, HitBTC, OKCoin, Bitfinex; README requirements are Node v7.8, TypeScript 2.2, MongoDB v3 — [tribeca repo](https://github.com/michaelgrosner/tribeca)
- Blankly: 2.5k stars, LGPL-3.0; last commits 30 Dec 2024 ("support more python versions"), 8 Nov 2024, 23 Dec 2023; README still lists FTX and "Coinbase Pro" as working exchanges and tests Python 3.7 to 3.10 — [blankly commits](https://github.com/blankly-finance/blankly/commits/main); [blankly repo](https://github.com/blankly-finance/blankly)
- Backtrader: 23.8k stars, GPL-3.0; last commit 19 Apr 2023 ("Version 1.9.78.123"); live brokers are Interactive Brokers via `IbPy`, Oanda via `oandapy` (REST only), Visual Chart — [backtrader commits](https://github.com/mementum/backtrader/commits/master); [backtrader repo](https://github.com/mementum/backtrader)

#### Smaller live projects
- OpenTrader: 2.9k stars, 354 forks, Apache-2.0, TypeScript/Node 22+; GRID, DCA, RSI and custom strategies; `opentrader backtest`, paper trading; OKX, Bybit, Binance, Kraken, Coinbase, Gate.io, Bitget via CCXT; author describes it as a personal free-time project and warns there "might be bugs in the code" — [opentrader repo](https://github.com/Open-Trader/opentrader)
- OpenTrader latest release v1.0.0-beta.29 on 06 Mar (year not shown) — [opentrader releases](https://github.com/Open-Trader/opentrader/releases)
- Lumibot: 2.3k stars, 436 forks, GPL-3.0, 7,540 commits; stocks, options, futures, forex, crypto, prediction markets; same strategy class for backtest, paper and live; backtest data from Yahoo, ThetaData, Polygon; "AI-native" agent strategies; commercial BotSpot hosted cloud and paid bootcamp — [lumibot repo](https://github.com/Lumiwealth/lumibot)
- Lumibot releases v4.6.95 (22 Nov), v4.6.94 and v4.6.93 (21 Nov), year not shown (presumed 2026), i.e. near-daily releases — [lumibot releases](https://github.com/Lumiwealth/lumibot/releases)
- Lumibot brokers: Alpaca (stocks, options, crypto), Interactive Brokers (stocks, options, futures, forex), Tradier, Charles Schwab, Tradovate (futures), TopstepX/ProjectX (futures), Bitunix (USDT perps), Coinbase Advanced and Kraken via CCXT — [lumibot brokers docs](https://lumibot.lumiwealth.com/brokers.html)
- hftbacktest: 5.1k stars, 978 forks, MIT; Python (Numba) plus Rust; backtesting that "accounts for limit orders, queue positions, and latencies" using L2/L3 feeds; live bot supports Binance Futures and Bybit only and is Rust-only — [hftbacktest repo](https://github.com/nkaz001/hftbacktest)
- chrisleekr/binance-trading-bot: 5.6k stars, Apache-2.0, Binance only; trailing-trade, momentum, rebalance and grid profiles; author says it is "not recommended for real funds" — [binance-trading-bot repo](https://github.com/chrisleekr/binance-trading-bot)
- CCXT: 45.0k stars, 9.0k forks, MIT; 105 exchange markets; JavaScript, TypeScript, Python, C#, PHP, Go, Java, Rust; certified exchanges are Binance, Bybit, Gate, OKX, KuCoin, Bitget, Hyperliquid, BingX, MEXC, Crypto.com, HashKey Global, WOOFI PRO — [ccxt repo](https://github.com/ccxt/ccxt)
- A comparison blog (author sells a competing product) characterises CCXT as "not a bot framework" with no backtesting and no built-in risk management — [dev.to comparison](https://dev.to/trendrider/freqtrade-vs-hummingbot-vs-ccxt-which-should-you-use-1ma7)
- NostalgiaForInfinity: 3.5k stars, 768 forks, GPL-3.0, 28,903 commits; five commits on 23 Nov 2026 touching X7 and X8 strategy versions — [NFI repo](https://github.com/iterativv/NostalgiaForInfinity); [NFI commits](https://github.com/iterativv/NostalgiaForInfinity/commits/main)

#### Open-source Solana / EVM sniping and MEV bots (category)
- SlowMist reported that a GitHub repo "solana-pumpfun-bot" contained a malicious dependency that scanned local files and uploaded wallet private keys; the attacker used fake accounts to inflate forks and stars — [Cointelegraph](https://cointelegraph.com/news/solana-trading-bot-github-malware-scam)
- The OSV database lists the PyPI package `solana-sniper-bot` (MAL-2026-13373) as malicious — [OSV MAL-2026-13373](https://osv.dev/vulnerability/MAL-2026-13373)
- JFrog documented 25 malicious npm and PyPI packages targeting Solana developers ("FakeFix") that harvest keypairs, SSH keys, cloud credentials and .env files — [JFrog research](https://research.jfrog.com/post/solana-fakefix/)
- StepSecurity documented a malicious Polymarket bot in a hijacked GitHub organisation whose dependencies steal wallet private keys and open an SSH backdoor — [StepSecurity](https://www.stepsecurity.io/blog/malicious-polymarket-bot-hides-in-hijacked-dev-protocol-github-org-and-steals-wallet-keys)

### Inferences
- "Stars" overstate real usage for old projects: Backtrader (23.8k) and Gekko (10.2k) rank high but are unmaintained; Superalgos has more forks (6.0k) than stars (5.8k), which is unusual and consistent with its token-reward contribution scheme rather than organic adoption.
- For a US retail user the realistic live candidates are freqtrade, Hummingbot, NautilusTrader (v1 stable line or wait for v2 GA), LEAN, Jesse (paid live plugin), Lumibot and OctoBot. Passivbot and hftbacktest are well maintained but target venues US persons cannot use (see US-venue question).
- The sniping/MEV category should be treated as hostile by default: star and fork counts were shown to be faked in at least one documented case, and these bots require a raw private key in a config file, so a single malicious dependency drains the wallet. Beyond malware, a retail sniper competes with professional searchers on latency; I found no credible evidence of sustained retail profitability.
- Open-source grid/DCA options are: Passivbot (perps, martingale-like), OctoBot (grid, DCA), OpenTrader (grid, DCA), Hummingbot Grid/DCA executors, chrisleekr/binance-trading-bot, and freqtrade position adjustment (as used by NFI "grinding").

### Gaps
- Exact star counts (API values) were not available; GitHub API access was blocked in this session, so only rounded page figures are reported.
- Release year for Hummingbot v2.18.0, OctoBot 3.0.0-beta3, OpenTrader beta.29 and Lumibot v4.6.95 is not shown on the fetched pages; presumed 2026 from sequence, not verified.
- Tribeca licence type and last-commit date not verified. Hummingbot Dashboard, Gateway, hftbacktest and chrisleekr/binance-trading-bot latest release dates not captured.
- Jesse live-plugin pricing not verified from the official page (403).
- Not researched in this session (no data, do not cite): vn.py, barter-rs, pycryptobot, Gainium open-source edition, intelligent-trading-bot, StockSharp, OpenAlgo, alpaca-py repo metrics. Alpaca-based bots are covered only via Lumibot, Jesse and LEAN's Alpaca integrations.
- Hummingbot Foundation funding model (exchange fee-share with sponsor connectors) was not confirmed on the pages fetched.

## Which support the same code path for backtest, paper and live, and how realistic are their backtests?

### Takeaway
freqtrade, Jesse, NautilusTrader, LEAN, Lumibot, Passivbot and Hummingbot V2 controllers all run one strategy definition in backtest, paper and live, but realism differs sharply: freqtrade's candle backtester explicitly assumes zero slippage and fills at the requested price, while NautilusTrader and hftbacktest simulate order-book matching with latency and (hftbacktest) queue position. No framework's own documentation claims its backtest equals live; freqtrade and NautilusTrader both state the opposite.

### Cited Findings
- freqtrade backtesting assumptions: "All orders are filled at the requested price (no slippage) as long as the price is within the candle's high/low range"; entries at candle open; exchange default fees applied (override with `--fee`); intra-candle order is exit signal, stoploss, ROI, trailing stop; stoploss exits fill at the stop price even if the low was lower; precision and minimum-size limits use current, not historic, exchange rules — [freqtrade backtesting docs](https://www.freqtrade.io/en/stable/backtesting/)
- freqtrade states backtesting "will **never** replace running a strategy in dry-run mode"; `--timeframe-detail` can replay a lower timeframe inside each candle; dynamic pairlists make results non-reproducible; position stacking results "cannot be reproduced in dry/live trading" — [freqtrade backtesting docs](https://www.freqtrade.io/en/stable/backtesting/)
- freqtrade on look-ahead bias: "Backtesting analyzes the whole dataframe timerange at once for performance reasons", so strategies can accidentally use future candles; "Strategies that look into the future will perform well during backtesting, often with incredible profits or winrates"; this is "a common pain-point, which can cause huge differences between backtesting and dry/live run methods" — [freqtrade strategy customization docs](https://www.freqtrade.io/en/stable/strategy-customization/)
- freqtrade ships `lookahead-analysis` and `recursive-analysis`; the docs say "Many strategies, without the programmer knowing, have fallen prey to lookahead bias", that removing the bias usually makes the strategy significantly worse, and that the tool can only verify signals that actually trigger (false negatives possible) — [freqtrade lookahead-analysis docs](https://www.freqtrade.io/en/stable/lookahead-analysis/)
- freqtrade hyperopt: validation guidance is to re-run a backtest on the same timerange and configuration; the page does not prescribe out-of-sample testing — [freqtrade hyperopt docs](https://www.freqtrade.io/en/stable/hyperopt/)
- A concrete live-vs-backtest gap: with order-book pricing live (`use_order_book: true`), entry takes the best ask, whereas the backtest proposes the candle open and fills if low ≤ rate ≤ high. One user's XRP trade backtested at entry 1.4889 (+4.19%) but filled live at 1.5386 (+0.54%); `--timeframe-detail 1m` did not close the gap — [NFI issue #1234, opened 26 Aug 2026](https://github.com/iterativv/NostalgiaForInfinity/issues/1234) (single user report, anecdote)
- NautilusTrader: "The same strategy and execution-algorithm code can run across backtest and live systems, reducing deployment divergence", with a caution that live execution adds venue, transport, timing, persistence and reconciliation behaviour a simulation may not reproduce — [nautilus_trader repo](https://github.com/nautechsystems/nautilus_trader)
- NautilusTrader backtesting "simulates trading against historical data with the same core components as live trading"; docs sections cover matching data granularity to venue `book_type`, deterministic matching, configurable slippage and probabilistic fills, bar execution (OHLC sequencing), and accounts/margin/funding — [NautilusTrader backtesting docs](https://nautilustrader.io/docs/latest/concepts/backtesting/)
- hftbacktest reconstructs L2 (market-by-price) and L3 (market-by-order) books and models feed latency, order latency and queue position with built-in or custom models — [hftbacktest repo](https://github.com/nkaz001/hftbacktest)
- Jesse advertises backtests "free of look-ahead bias" and offers paper trading as a toggle on the live page; live exchanges Kraken Pro Spot, Gate.io Spot, Lighter, Apex Omni and Hyperliquid are live-only and not in the backtest candle list — [jesse repo](https://github.com/jesse-ai/jesse); [Jesse live docs](https://docs.jesse.trade/docs/livetrade); [Jesse supported exchanges](https://docs.jesse.trade/docs/supported-exchanges)
- Passivbot: a shared Rust orchestrator plans orders for both live trading and backtests — [passivbot repo](https://github.com/enarjord/passivbot)
- Hummingbot: controllers are described as enabling backtesting and multi-bot deployment through the Dashboard; Quants Lab is the notebook environment for research and backtesting; paper trading is in the client. The v2.18.0 release notes include a fix for "backtest stop-loss pricing" — [hummingbot docs](https://hummingbot.org/docs/); [hummingbot releases](https://github.com/hummingbot/hummingbot/releases)
- A competitor-authored comparison rates backtesting as "excellent" for freqtrade, "limited" for Hummingbot and "none" for CCXT — [dev.to comparison](https://dev.to/trendrider/freqtrade-vs-hummingbot-vs-ccxt-which-should-you-use-1ma7) (author has a commercial interest)
- LEAN: `lean backtest` and `lean live` run the same algorithm locally via Docker; QuantConnect offers paper trading across equities, forex, CFD, crypto, futures — [LEAN repo](https://github.com/QuantConnect/Lean); [QuantConnect brokerages docs](https://www.quantconnect.com/docs/v2/cloud-platform/live-trading/brokerages)
- Lumibot: paper and live trading use the same strategy class as backtesting; backtest data sources are Yahoo, ThetaData, Polygon — [lumibot repo](https://github.com/Lumiwealth/lumibot)
- Blankly claimed backtest, paper, sandbox and live "switched by changing a single line", but the project has had no functional commits since 2023/2024 — [blankly repo](https://github.com/blankly-finance/blankly); [blankly commits](https://github.com/blankly-finance/blankly/commits/main)
- OctoBot and OpenTrader both offer backtesting and paper trading, OctoBot only on self-run instances — [OctoBot repo](https://github.com/Drakkar-Software/OctoBot); [opentrader repo](https://github.com/Open-Trader/opentrader)

### Inferences
- Realism ranking (my assessment from the documentation): hftbacktest (queue + latency, L2/L3) > NautilusTrader (order-book matching engine, fill and latency models) > LEAN (configurable fill/slippage/fee models, not verified in this session) > Jesse / Passivbot (candle-driven, 1m granularity) > freqtrade (candle-driven, zero slippage by design, optional detail timeframe) > Hummingbot (backtesting of V2 controllers on candles; market-making fills cannot be faithfully reproduced from candles) > OctoBot / OpenTrader.
- freqtrade backtests are systematically optimistic for strategies that (a) trade illiquid alts, (b) enter on fast dips where the live ask has already moved, or (c) use limit entries assumed filled whenever price touches. The XRP example above shows a single trade's profit shrinking from +4.19% to +0.54% purely from entry-price assumptions.
- freqtrade hyperopt is an efficient overfitting machine unless the user imposes their own walk-forward / out-of-sample discipline; the documentation's validation step re-uses the optimisation window.
- "Same code path" does not remove the gap. It removes logic divergence, not fill, latency, funding or outage divergence. Dry-run on live data for weeks is the only honest test, which is what freqtrade's own docs say.

### Gaps
- Whether freqtrade backtests include perpetual funding fees was not covered on the fetched page (background knowledge: it downloads funding-rate and mark-price data for futures backtests; unverified here).
- NautilusTrader fill-model parameter details (probabilistic fills, queue position, latency model) were not retrieved; the specific sub-page returned 404.
- LEAN's reality-modelling details (slippage, fill, fee, margin interest models) were not fetched.
- Hummingbot backtesting engine fidelity for market-making strategies is not documented on the pages fetched.
- Jesse's fill and fee assumptions were not retrieved beyond the "no look-ahead bias" claim.

## Which support US-accessible venues versus only offshore venues that US persons cannot legally use?

### Takeaway
For US-accessible crypto spot, the frameworks with first-class connectors are Hummingbot (Coinbase, Kraken, Gemini), freqtrade (Kraken, Binance.US via the `binanceus` id), Jesse (Coinbase, Binance US, Kraken Pro, Alpaca), NautilusTrader (Coinbase, Kraken, Interactive Brokers), LEAN (Coinbase, Kraken, Alpaca, IBKR and other US brokers), OctoBot (Coinbase, Binance US) and Lumibot (Alpaca, IBKR, Coinbase and Kraken via CCXT). Passivbot and hftbacktest are effectively offshore-only (Binance, Bybit, OKX, Bitget, Hyperliquid and similar). For regulated US futures, only NautilusTrader (IBKR), LEAN (IBKR, TradeStation, Tastytrade) and Lumibot (IBKR, Tradovate) have a clear path; I found no evidence that any framework yet connects to the new US-regulated perpetuals at Coinbase or Kraken/Bitnomial.

### Cited Findings
- freqtrade docs on Binance: "The current and non-exhaustive countries blocked are Canada, Malaysia, Netherlands and United States"; "US based users. Use exchange id: `binanceus`" — [freqtrade exchange notes](https://www.freqtrade.io/en/stable/exchanges/)
- freqtrade supports Kraken spot (stoploss on exchange; only 720 historic candles via API so `--dl-trades` is needed for backtest data) and Kraken Futures via exchange id `krakenfutures` (isolated margin, USD-settled). Coinbase and Gemini are not covered in freqtrade's exchange documentation or README list — [freqtrade exchange notes](https://www.freqtrade.io/en/stable/exchanges/); [freqtrade repo](https://github.com/freqtrade/freqtrade)
- freqtrade futures support is limited to Binance, Bitget, Bybit, Gate, Hyperliquid, Kraken Futures and OKX — [freqtrade exchange notes](https://www.freqtrade.io/en/stable/exchanges/)
- Hummingbot lists CEX spot connectors for Coinbase, Gemini, Kraken, Bitstamp alongside offshore venues; its perp connectors are Binance, Bitget, Gate.io, KuCoin, OKX, Bybit, Hyperliquid, Derive, dYdX, Lighter, Aevo and others — [hummingbot repo](https://github.com/hummingbot/hummingbot)
- Jesse live: Binance US Spot, Coinbase Spot, Kraken Pro Spot, Kraken Pro Futures, and Alpaca (US stocks and ETFs, public beta) — [Jesse supported exchanges](https://docs.jesse.trade/docs/supported-exchanges)
- NautilusTrader: Coinbase, Kraken and Interactive Brokers adapters are "stable"; Kalshi (US-regulated prediction market) is beta — [nautilus_trader repo](https://github.com/nautechsystems/nautilus_trader)
- LEAN/QuantConnect: Coinbase, Kraken, Alpaca (equities, options, crypto), Interactive Brokers (equities, options, futures, forex), TradeStation, Tastytrade, Tradier, Charles Schwab; Binance US not listed on the page fetched — [QuantConnect brokerages docs](https://www.quantconnect.com/docs/v2/cloud-platform/live-trading/brokerages)
- OctoBot: Coinbase (spot) and Binance US among supported exchanges — [OctoBot repo](https://github.com/Drakkar-Software/OctoBot)
- Lumibot: Alpaca (stocks, options, crypto), IBKR, Tradier, Schwab, Tradovate and TopstepX (futures), Coinbase Advanced and Kraken through CCXT — [lumibot brokers docs](https://lumibot.lumiwealth.com/brokers.html)
- Krypto-trading-bot lists Coinbase, Binance.US and Kraken (spot only), but is stale since Dec 2024 — [Krypto-trading-bot repo](https://github.com/ctubio/Krypto-trading-bot)
- Passivbot's exchange list is Bybit, OKX, Bitget, Bitunix, GateIO, Binance, Kucoin, Hyperliquid, WEEX, Lighter (perpetual futures) — [passivbot repo](https://github.com/enarjord/passivbot)
- hftbacktest live trading supports only Binance Futures and Bybit — [hftbacktest repo](https://github.com/nkaz001/hftbacktest)
- Hyperliquid: third-party guides state its Terms of Use classify US residents, citizens and companies as "Restricted Persons", enforced by front-end geofencing rather than identity checks; no US agency has banned it — [datawallet](https://www.datawallet.com/crypto/is-hyperliquid-available-in-the-usa); [OneKey blog](https://onekey.so/blog/ecosystem/geo-block-hyperliquid-dydx-us/) (secondary sources; primary ToS not retrieved)
- US-regulated crypto derivatives now exist: Coinbase launched CFTC-regulated perpetual-style futures for US traders in July 2025 — [The Block](https://www.theblock.co/post/363796/coinbase-launches-perpetual-futures)
- On 28/29 May 2026 the CFTC cleared Kalshi to list a bitcoin perpetual and gave Coinbase a no-action letter for perpetuals routed through a Coinbase affiliate (CFM, via Coinbase Bermuda as "foreign futures") — [The Block](https://www.theblock.co/news/regulation/2026-05-29-cftc-opens-door-for-crypto-perpetual-future-contracts-in-us-as-coinbase-kalshi-move-forward-403040); [CoinDesk](https://www.coindesk.com/policy/2026/05/28/u-s-cftc-opens-crypto-perp-door-with-approval-of-first-regulated-firm)
- Kraken launched "Kraken Derivatives US" on 15 July 2025 (CME-listed crypto futures via NinjaTrader), initially in a limited set of states, and later announced CFTC-regulated perpetual futures for US clients listed on Bitnomial — [Business Wire](https://www.businesswire.com/news/home/20250715200422/en/Kraken-Launches-US-Regulated-Derivatives-Offering-Creating-Unified-Access-to-Futures-and-Crypto-Spot-Markets); [Kraken blog](https://blog.kraken.com/product/kraken-derivatives-us/first-cftc-regulated-perpetual-futures-for-us-traders)
- Alpaca crypto: 20+ assets across 56 pairs quoted in USD, USDT, USDC and BTC; a 2022 press release says available in 49 US states excluding New York; current state list and fee schedule not confirmed — [Alpaca crypto docs](https://docs.alpaca.markets/docs/crypto-trading); [Business Wire 2022](https://www.businesswire.com/news/home/20220308005090/en/Alpaca-Crypto-API-Now-Offers-Over-20-New-Coins-and-Expands-Access-to-49-US-States)

### Inferences
- US-accessibility matrix (spot crypto): Coinbase Advanced → Hummingbot, Jesse, NautilusTrader, LEAN, OctoBot, Lumibot (CCXT), OpenTrader (CCXT), not freqtrade. Kraken → freqtrade, Hummingbot, Jesse, NautilusTrader, LEAN, Lumibot, OpenTrader. Gemini → Hummingbot only among those checked. Binance.US → freqtrade (`binanceus`), Jesse, OctoBot, Krypto-trading-bot.
- freqtrade's leveraged/short functionality is practically unavailable to a US person: every futures venue it supports is either geo-blocked for the US (Binance per freqtrade's own docs; Hyperliquid per its ToS) or an offshore perp venue. A US freqtrade user is realistically limited to long-only spot on Kraken or Binance.US, which also limits the pair universe versus what community strategies (NFI defaults to Binance futures per issue #1234) were tuned on.
- The "Kraken Futures" connectors in freqtrade (`krakenfutures`) and Jesse ("Kraken Pro Futures") point at Kraken's non-US futures platform; whether they work against Kraken Derivatives US / Bitnomial perps is unverified and should be assumed not to.
- For a US trader wanting legal leveraged or short crypto exposure in an automated framework, the proven route in November 2026 is CME crypto futures (including micro contracts) through Interactive Brokers using NautilusTrader, LEAN or Lumibot. Coinbase/Kraken US perps are new and framework support is unproven.

### Gaps
- I did not verify, per exchange, the US-person restrictions for Bybit, OKX, Bitget, Gate, KuCoin, MEXC or dYdX in this session (background knowledge: their global platforms exclude US persons; OKX operates a separate US entity). Only Binance (freqtrade docs) and Hyperliquid (secondary sources) are sourced above.
- No source found confirming that any framework supports Coinbase Financial Markets US perps or Kraken/Bitnomial US perps via API. CCXT's Coinbase derivative coverage was not checked.
- Whether LEAN local live trading with brokerage plugins requires a paid QuantConnect organisation tier was not verified.
- Gemini support in freqtrade, Jesse and NautilusTrader appears absent from the lists fetched, but generic CCXT access in freqtrade ("potentially many others") was not tested.
- State-level availability (for example New York) for Coinbase, Kraken, Gemini, Binance.US and Alpaca crypto was not researched.

## What do independent users report about real-world results of popular community strategies (e.g. NostalgiaForInfinity) versus their backtests?

### Takeaway
I found no verified, independent live track record for NostalgiaForInfinity or any other popular community strategy; the project itself publishes only backtests in commit comments. The limited evidence that exists (a GitHub issue, the community FAQ, freqtrade's own docs, and a freqtrade contributor's stated position) points the same way: live fills are materially worse than backtests and backtests should be treated as rough estimates.

### Cited Findings
- NFI's README makes no performance claims and says backtesting results are in the comments of individual commits; it carries donation addresses, a Patreon link and exchange referral links (Kucoin, Gate, Bybit, Bitget, Kraken, MEXC, OKX, HTX, Bitvavo, BitMart, Binance) — [NFI repo](https://github.com/iterativv/NostalgiaForInfinity)
- NFI recommended configuration: 6 to 12 open trades with unlimited stake, 40 to 80 pairs (volume pairlist), stablecoin quote pairs, leveraged tokens blacklisted, 5m timeframe that must not be overridden, `use_exit_signal` on and `exit_profit_only` off — [NFI repo](https://github.com/iterativv/NostalgiaForInfinity)
- User report (anecdote, one user, 22 to 26 Aug 2026, NFI X7 on Binance USDT-M futures, 3x isolated): backtest XRP entry 1.4889 and +4.19% versus live entry 1.5386 and +0.54%. The maintainer's reply did not dispute the gap and said the trades "doesn't look bad"; a freqtrade contributor (stash86) responded by linking a 2023 blog post arguing NFI should not be used for live trading — [NFI issue #1234](https://github.com/iterativv/NostalgiaForInfinity/issues/1234)
- Community FAQ (fork wiki, last modified Dec 2021, so dated): "Backtests don't have ticker data so the base is different too"; "See backtests as an estimation what it could do"; the strategy "generally only trades when there is an uptrend" and "Sometimes the strat doesn't trade for 3-4 days straight"; users should not set freqtrade's stoploss or ROI because the strategy manages exits itself; market orders can be expensive in fast dips and limit orders may never fill — [NFI community FAQ](https://github-wiki-see.page/m/cazzeken/NostalgiaForInfinity/wiki/Frequently-Asked-Questions)
- A 2026 third-party setup guide for NFI X8 reports no live or dry-run P&L for NFI; its headline figures are contributor backtest notes (e.g. "profit +44%", "161 losses down to zero") for signals shipped disabled, and generic "case study" numbers not tied to NFI. It warns that switching X7 to X8 with open positions is untested because NFI manages positions through its own grinding and de-risking logic — [alexbobes.com guide](https://alexbobes.com/crypto/automated-crypto-trading-with-freqtrade-and-nostalgiaforinfinity/)
- freqtrade's own documentation: bias is "often the main driver" of too-good-to-be-true profits, and "Many strategies, without the programmer knowing, have fallen prey to lookahead bias" — [freqtrade lookahead-analysis docs](https://www.freqtrade.io/en/stable/lookahead-analysis/)
- One blogger (commercial interest: sells a freqtrade-based product) reports running freqtrade for six months with a 67.9% win rate over 500+ trades, with no P&L and no verification — [dev.to comparison](https://dev.to/trendrider/freqtrade-vs-hummingbot-vs-ccxt-which-should-you-use-1ma7)
- One Medium user reports a strategy backtest falling from about 23% profit and 67% win rate to about 4% profit and 40% win rate after hyperopt, concluding that fewer parameters should be tuned — [Medium post](https://medium.com/@hangyulson1004/my-experience-based-tips-to-improve-profit-by-19-using-hyperparameter-optimization-on-a-trading-944cf534aec7) (anecdote)
- Hummingbot market-making experience (vendor-hosted interviews, so positively biased): one liquidity miner described being "somewhat, though not substantially profitable", another "break-even, possibly slightly profitable"; Hummingbot's own material calls inventory risk the main risk of market making — [Hummingbot interview](https://hummingbot.org/blog/interview-with-liquidity-miner-david-salter/); [Hummingbot inventory risk](https://hummingbot.org/blog/what-is-inventory-risk/)
- Passivbot: no first-hand liquidation reports were found via search; a third-party tracker warns about running high leverage and exposure and being liquidated after early gains — [futuresboard passivbot page](https://ecoppen.github.io/futuresboard/passivbot)

### Inferences
- The absence of any audited live record for NFI after 28,903 commits and years of use is itself informative. A strategy that is edited several times a day (5 commits on 23 Nov 2026 adding "protections" to individual signals) is being continuously re-fitted to recent losses; backtests of the current version on past data are therefore in-sample by construction.
- NFI's design (no fixed stoploss, strategy-managed exits, "grinding"/position adjustment, 6 to 12 concurrent positions in 40 to 80 alt pairs) is a dip-buying, average-down profile: many small wins and occasional large, long-held losers. That profile produces high win rates in backtests and is exactly the profile most damaged by freqtrade's zero-slippage, fill-at-open assumptions.
- NFI's incentives are donations and exchange referral fees, not performance; that is not evidence of bad faith, but users should not read popularity as proof of profitability.
- For a US user the published NFI configuration (Binance futures, large USDT alt universe) cannot be replicated; running it on Kraken or Binance.US spot is an untested variant with thinner books and fewer pairs.

### Gaps
- No Reddit r/freqtrade, r/algotrading or Hacker News threads were retrievable by search in this session; user sentiment from those venues is not represented. This is a search-tool limitation, not evidence that such threads do not exist.
- The 2023 blog post linked by stash86 arguing against using NFI live could not be located.
- No independent, verified live equity curve for NFI (any version), freqtrade-strategies repo strategies, Passivbot configs or Hummingbot controllers was found.
- The freqtrade/freqtrade-strategies repository was not fetched; its star count and disclaimers are not verified here.

## What licences would restrict building a private bot on top of them?

### Takeaway
None of the licences restrict private use, modification or running a bot for your own account. Copyleft matters only if you distribute the bot or (for GPL, arguably) derivative strategy code: freqtrade, OctoBot, Lumibot, Backtrader and NostalgiaForInfinity are GPL-3.0; NautilusTrader and Blankly are LGPL-3.0; Hummingbot, LEAN, Superalgos, OpenTrader and Kelp are Apache-2.0; Jesse, CCXT, hftbacktest, Gekko and Zenbot are MIT; Passivbot is public domain (Unlicense). The practical restrictions are commercial, not licence-based: Jesse's live-trading plugin is a closed, licence-keyed binary, and Krypto-trading-bot requires a BTC payment per API key.

### Cited Findings
- freqtrade: GNU GPL version 3 — [freqtrade LICENSE](https://github.com/freqtrade/freqtrade/blob/develop/LICENSE)
- NostalgiaForInfinity: GPL-3.0 — [NFI repo](https://github.com/iterativv/NostalgiaForInfinity)
- OctoBot: GPL-3.0 (or later); commercial licences offered to institutions on request — [OctoBot repo](https://github.com/Drakkar-Software/OctoBot)
- Lumibot: GPL-3.0 — [lumibot repo](https://github.com/Lumiwealth/lumibot)
- Backtrader: GPL-3.0 — [backtrader repo](https://github.com/mementum/backtrader)
- NautilusTrader: LGPL-3.0; dependency allow-list enforced as compatible with `LGPL-3.0-only` — [nautilus_trader repo](https://github.com/nautechsystems/nautilus_trader)
- Blankly: LGPL-3.0 — [blankly repo](https://github.com/blankly-finance/blankly)
- Hummingbot and Gateway and Dashboard: Apache-2.0; docs state all code is open sourced under Apache 2.0 or MIT — [hummingbot repo](https://github.com/hummingbot/hummingbot); [hummingbot docs](https://hummingbot.org/docs/)
- LEAN: Apache-2.0 — [LEAN repo](https://github.com/QuantConnect/Lean)
- Superalgos: Apache-2.0 — [Superalgos repo](https://github.com/Superalgos/Superalgos)
- OpenTrader: Apache-2.0 — [opentrader repo](https://github.com/Open-Trader/opentrader)
- Jesse core: MIT; live/paper trading requires the pre-built official plugin and an active licence key — [jesse repo](https://github.com/jesse-ai/jesse); [Jesse live docs](https://docs.jesse.trade/docs/livetrade)
- CCXT: MIT — [ccxt repo](https://github.com/ccxt/ccxt)
- hftbacktest: MIT — [hftbacktest repo](https://github.com/nkaz001/hftbacktest)
- Passivbot: Unlicense, "free and unencumbered software released into the public domain" — [passivbot repo](https://github.com/enarjord/passivbot)
- Krypto-trading-bot: MIT-licensed repository, but installation requires agreeing to "collaborative non-free software" and unlocking costs 0.00121 BTC per API key per exchange — [Krypto-trading-bot repo](https://github.com/ctubio/Krypto-trading-bot)

### Inferences
- For a private, never-distributed bot, GPL-3.0 imposes no obligation: GPL obligations trigger on conveying the software, and GPL-3.0 (unlike AGPL) has no network-use clause. None of the surveyed frameworks is AGPL.
- If the user ever wants to sell or share a bot built on freqtrade/OctoBot/Lumibot (or a strategy derived from NFI code), it would have to be released under GPL-3.0. Apache-2.0/MIT bases (Hummingbot, LEAN, Jesse core, CCXT) and LGPL (NautilusTrader, used as a library) leave proprietary distribution open.
- Jesse is best described as "open core": research and backtesting are MIT, but unattended live trading depends on a proprietary component and a vendor licence server, which is a continuity risk as well as a cost.

### Gaps
- This is not legal advice; whether a freqtrade strategy file is a "derivative work" of GPL freqtrade is a legal question I did not research.
- Tribeca's licence type was not verified.
- Jesse licence price and terms (lifetime versus subscription) are unverified.

## Which is the best base for (a) directional intraday to multi-day strategies, (b) market making, (c) cross-venue or funding arbitrage?

### Takeaway
(a) Directional: freqtrade is the most complete and most used candle-strategy bot, but for a US person it is long-only spot on Kraken/Binance.US; NautilusTrader or LEAN are the better bases if the user wants regulated futures or IBKR alongside Coinbase/Kraken. (b) Market making: Hummingbot is the purpose-built choice and has Coinbase, Kraken and Gemini connectors; NautilusTrader plus hftbacktest-style research is the higher-fidelity alternative. (c) Arbitrage: Hummingbot (Arbitrage and XEMM executors, Gateway for DEX legs) or NautilusTrader (multi-venue in one engine); genuine funding arbitrage needs perp venues that US persons mostly cannot use.

### Cited Findings
- freqtrade is designed around candle-based dataframe strategies with dry-run, backtesting, hyperopt, FreqAI, protections (StoplossGuard, MaxDrawdown) and stoploss-on-exchange — [freqtrade repo](https://github.com/freqtrade/freqtrade); [freqtrade plugins docs](https://www.freqtrade.io/en/stable/plugins/)
- freqtrade added websocket order book support only in 2026.10 (30 Oct 2026); its backtester is candle-based with no slippage — [freqtrade releases](https://github.com/freqtrade/freqtrade/releases); [freqtrade backtesting docs](https://www.freqtrade.io/en/stable/backtesting/)
- A competitor-authored comparison recommends freqtrade for "90% of retail traders" doing directional trading and Hummingbot for market making "if you have $10K+ capital", noting Hummingbot's limited backtesting and complex configuration — [dev.to comparison](https://dev.to/trendrider/freqtrade-vs-hummingbot-vs-ccxt-which-should-you-use-1ma7) (commercial interest)
- Hummingbot ships executors for Arbitrage, XEMM (cross-exchange market making), Grid, DCA, TWAP, Position and CLMM LP, with a market-making controller example (`pmm_mister`) — [hummingbot executors docs](https://hummingbot.org/strategies/v2-strategies/executors/); [hummingbot repo](https://github.com/hummingbot/hummingbot)
- Hummingbot's own material: inventory risk is the main risk of market making; sudden 5 to 10% moves in seconds can wipe out market makers on the wrong side — [Hummingbot inventory risk](https://hummingbot.org/blog/what-is-inventory-risk/); [Hummingbot academy](https://docs.hummingbot.org/academy-content/top-beginner-misconceptions-about-market-making/)
- NautilusTrader runs the same strategy and execution-algorithm code in backtest and live across CEX, DEX, IBKR, Betfair and prediction-market adapters, but v2 is still at release candidate and "not recommended for production" — [nautilus_trader repo](https://github.com/nautechsystems/nautilus_trader); [nautilus_trader releases](https://github.com/nautechsystems/nautilus_trader/releases)
- hftbacktest models queue position and latency for market-making research, with live trading limited to Binance Futures and Bybit — [hftbacktest repo](https://github.com/nkaz001/hftbacktest)
- LEAN covers equities, options, futures, forex and crypto with Coinbase, Kraken, IBKR, Alpaca and other US brokerages — [QuantConnect brokerages docs](https://www.quantconnect.com/docs/v2/cloud-platform/live-trading/brokerages)
- Passivbot is a perp-only contrarian grid/martingale system on offshore venues and Hyperliquid — [passivbot repo](https://github.com/enarjord/passivbot)
- Deployment: freqtrade, Hummingbot, Jesse, OctoBot, OpenTrader and LEAN all ship Docker paths; OctoBot (octobot.cloud), Lumibot (BotSpot) and QuantConnect offer paid hosting — [OctoBot repo](https://github.com/Drakkar-Software/OctoBot); [lumibot repo](https://github.com/Lumiwealth/lumibot); [LEAN repo](https://github.com/QuantConnect/Lean); [Jesse live docs](https://docs.jesse.trade/docs/livetrade)

### Inferences
- (a) Directional, small US account: freqtrade on Kraken spot is the lowest-effort path with the largest community, provided the user treats its backtests as optimistic and runs weeks of dry-run. If the plan includes shorting, leverage, CME crypto futures or equities, start with NautilusTrader (v1 stable line until v2 goes GA) or LEAN with Interactive Brokers instead; Lumibot is the simplest option for Alpaca/IBKR but is a small project with a commercial upsell. Jesse is technically attractive but live trading is paywalled and closed.
- (b) Market making, small US account: Hummingbot is the only maintained OSS framework with Coinbase/Kraken/Gemini spot connectors and built-in MM logic. Realistically a small retail account on US spot venues pays taker/maker fees without rebates and faces adverse selection; the vendor-hosted interviews report break-even to slightly profitable results at best. Latency is Python event-loop plus home/cloud network, which is not competitive with professional market makers on liquid pairs.
- (c) Arbitrage: cross-venue spot arbitrage between Coinbase/Kraken/Gemini is implementable in Hummingbot (Arbitrage/XEMM executors) or NautilusTrader, but requires pre-funded inventory on both venues and is fee-limited. Funding-rate (cash-and-carry) arbitrage needs a perp leg: the mature perp venues (Binance, Bybit, OKX, Hyperliquid) are closed to US persons, and the new US perps (Coinbase, Kraken/Bitnomial) lack confirmed framework connectors, so the US-legal variant today is spot (or ETF) versus CME futures basis through IBKR, for which NautilusTrader or LEAN is the base.
- Risk controls across the board are strategy-level (stops, cooldowns, drawdown halts) rather than account-level kill switches enforced outside the bot. For unattended operation the user should add an independent watchdog (exchange-side API key restrictions with withdrawals disabled, stop orders resting on the exchange, external equity monitor).
- Latency limits: all Python frameworks here (freqtrade, Hummingbot, Jesse, OctoBot, Lumibot) are unsuitable for sub-second edge; NautilusTrader's Rust core and hftbacktest's Rust live bot are the only ones designed with latency in mind.

### Gaps
- No quantitative latency benchmarks for any framework were retrieved.
- No documented incidents of framework bugs causing user losses were retrieved with a citable source, other than Hummingbot's v2.18.0 release note fixing "backtest stop-loss pricing" and an API throttler race condition. Passivbot's v8.1.0 notes mention "restart and PnL hardening", which implies earlier fragility but not a specific loss event.
- Hummingbot's account-level kill switch (a legacy client feature) was not confirmed on the pages fetched; only per-executor triple-barrier controls are sourced.
- Capital and fee thresholds at which market making becomes viable on Coinbase/Kraken/Gemini were not researched; the "$10K+" figure is one blogger's opinion.
- No evidence found, in either direction, on framework support for US-regulated perps, which determines whether funding arbitrage is feasible for a US person in an OSS framework.
