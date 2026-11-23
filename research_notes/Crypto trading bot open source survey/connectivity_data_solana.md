# Exchange Connectivity, Market Data and On-Chain (Solana / DEX) Trading Libraries — status as of 2026-11-23

Method notes for the report writer (apply to every section):

- **GitHub stars, license, last-commit** were read on 2026-11-23 from the shields.io badge JSON endpoints (`https://img.shields.io/github/{stars|license|last-commit}/<owner>/<repo>.json`), because the GitHub API itself was not reachable from the research sandbox. Stars are rounded as shields rounds them. "Last commit" is month-granular (for example "Oct 2026"); "today" means 2026-11-23.
- **Latest release version and date** were read on 2026-11-23 from the PyPI JSON API (`https://pypi.org/pypi/<pkg>/json`) and the npm registry (`https://registry.npmjs.org/<pkg>`).
- Anything tagged **[background, not re-verified]** is from my prior knowledge and was not confirmed against a live source in this session. Anything tagged **[unverified]** or **[conflict]** should not be presented as fact.
- Several official fee pages (Coinbase help centre, Coinbase learn pages, solana.com docs) returned HTTP 403/429 to the fetch tool, so some figures rest on secondary sources. This is flagged line by line.

---

## 1. What are the connectivity libraries (CEX, brokers, Solana, EVM), and what is their licence, popularity and maintenance status?

### Takeaway
CCXT (MIT, ~45k stars, released the same day as this research) is the only actively maintained "one library, many exchanges" option and covers every US spot venue; everything else is a thin single-venue wrapper. Several widely recommended packages are stale or abandoned in November 2026: ib_insync (dead since 2024), anchorpy (no commit since Mar 2025), jupiter-quote-api-node (no commit since Dec 2025), jito-py-rpc (Jun 2025), web3-flashbots (Jul 2024) and the 0x monorepo (Apr 2021).

### Cited Findings

#### 1a. Centralized exchange / broker connectivity

| Library | Repo | Licence | Stars | Latest release / last commit | Language | What it is for (plain) | Limits |
|---|---|---|---|---|---|---|---|
| CCXT | [ccxt/ccxt](https://github.com/ccxt/ccxt) | MIT | ~45k | v4.5.94 on PyPI and npm, 2026-11-23; commits daily | JS/TS, Python, C#, PHP, Go, Java, Rust | One uniform API to fetch prices/candles/order books and place orders on ~105 exchanges | Lowest-common-denominator API; exchange-specific features need `params` overrides; near-daily releases mean pin your version |
| cryptofeed | [bmoscon/cryptofeed](https://github.com/bmoscon/cryptofeed) | PyPI metadata says AGPL-3.0-or-later; GitHub shows "not identifiable" **[conflict — read LICENSE file]** | ~3k | v3.0.5, 2026-11-18; commit ~2026-11-18 | Python | Websocket market-data collector (trades, L2/L3 books, funding) normalised across exchanges; data only, no order placement | Licence must be checked; data ingestion only |
| Coinbase Advanced Trade SDK | [coinbase/coinbase-advanced-py](https://github.com/coinbase/coinbase-advanced-py) | Apache-2.0 | ~366 | v1.8.4, 2026-06-19; commit Oct 2026 | Python | Official REST + websocket client for Coinbase Advanced (spot and the US futures endpoints) | Coinbase only |
| Kraken (community) | [btschwertfeger/python-kraken-sdk](https://github.com/btschwertfeger/python-kraken-sdk) | Apache-2.0 | ~89 | v3.5.1, 2026-09-28; commit Nov 2026 | Python | Spot + Kraken Futures REST/websocket client | Community project, small user base |
| Kraken CLI | [krakenfx/kraken-cli](https://github.com/krakenfx/kraken-cli) | MIT | ~816 | commit Oct 2026 | not checked | Repo under Kraken's GitHub org; contents not reviewed in this session | **[unverified scope]** |
| Binance connector | [binance/binance-connector-python](https://github.com/binance/binance-connector-python) | MIT | ~3k | v3.13.0, 2026-04-30; commit ~2026-11-18 | Python | Official thin wrapper for Binance REST/websocket | Targets Binance.com (not legally usable by US persons); Binance.US needs a base-URL change |
| python-binance | [sammchardy/python-binance](https://github.com/sammchardy/python-binance) | MIT | ~7.2k | v1.0.37, 2026-06-08; commit Jun 2026 | Python | Popular community Binance client, has a `tld='us'` switch **[background, not re-verified]** | Same US caveat |
| pybit (Bybit) | [bybit-exchange/pybit](https://github.com/bybit-exchange/pybit) | MIT (PyPI) | ~678 | v5.17.2, 2026-11-10 | Python | Official Bybit v5 client | Bybit is not available to US persons **[background, not re-verified]** |
| python-okx | [okxapi/python-okx](https://github.com/okxapi/python-okx) | not specified on GitHub or PyPI | ~863 | v0.4.5, 2026-11-18; commit Sep 2026 | Python | OKX v5 client | No declared licence; CCXT lists a separate `okxus` id (see section 7) |
| Hyperliquid SDK | [hyperliquid-dex/hyperliquid-python-sdk](https://github.com/hyperliquid-dex/hyperliquid-python-sdk) | MIT | ~1.9k | v0.24.0, 2026-06-04; commit Jun 2026 | Python | Official client for the Hyperliquid on-chain perp/spot order book: signs orders with an Ethereum-style key | Hyperliquid's terms exclude US persons (section 3) |
| dYdX v4 clients | [dydxprotocol/v4-clients](https://github.com/dydxprotocol/v4-clients) | AGPL-3.0 (npm metadata) | ~119 | PyPI `dydx-v4-client` 1.1.6, 2026-02-12; npm `@dydxprotocol/v4-client-js` 3.6.1, 2026-11-18 | Python, TS | Clients for the dYdX v4 chain (perps) | Python client lags the TS client by nine months; perps not open to US (section 3) |
| alpaca-py | [alpacahq/alpaca-py](https://github.com/alpacahq/alpaca-py) | Apache-2.0 | ~1.6k | v0.45.0, 2026-11-05; commit today | Python | Official Alpaca broker API (stocks, options, crypto spot) with paper trading | Crypto liquidity is Alpaca's own venue, not a major exchange book |
| ib_insync | [erdewit/ib_insync](https://github.com/erdewit/ib_insync) | BSD-2-Clause | ~3.3k | v0.9.86, 2023-07-02; last commit Mar 2024 | Python | Was the standard async wrapper for Interactive Brokers TWS/Gateway | **Unmaintained** — do not start new work on it |
| ib_async | [ib-api-reloaded/ib_async](https://github.com/ib-api-reloaded/ib_async) | BSD-2-Clause | ~1.8k | v2.1.0, 2025-12-08; last commit Dec 2025 | Python | Community successor fork of ib_insync | No commits for ~11 months as of Nov 2026 — treat as slow-moving |
| tastytrade | [tastyware/tastytrade](https://github.com/tastyware/tastytrade) | MIT | ~261 | v13.2.3, 2026-08-07; commit Aug 2026 | Python | Unofficial SDK for the tastytrade Open API | Unofficial |

- tastytrade's official developer site describes a REST/JSON API covering equities, options, futures, futures options and cryptocurrency — [tastytrade Open API](https://developer.tastytrade.com/)
- Robinhood has an official Crypto Trading API with two versions; only v2 ("place crypto orders with fee tiers") counts toward volume tiers, and v2 orders are charged the standard (taker) rate until the reduced/standard fee rollout completes — [Robinhood crypto fee tiers](https://robinhood.com/us/en/support/articles/crypto-fee-tiers), [Robinhood Crypto Trading API](https://robinhood.com/us/en/support/articles/crypto-api)
- IBKR crypto executes on Paxos Trust Company or Zero Hash; the product page lists 24/7 trading and non-marketable limit orders — [IBKR crypto commissions](https://www.interactivebrokers.com/en/pricing/commissions-cryptocurrencies.php?re=amer)
- CME crypto futures and options moved to 24/7 trading (CME press release dated 2026-06-01; originally planned for 2026-05-29), with a Saturday maintenance window of 2:00–3:45 a.m. CT; availability "varies by clearing firm" at launch — [CME press release](https://www.cmegroup.com/media-room/press-releases/2026/6/01/cme_group_announceslaunchof247cryptocurrencyfuturesandoptionstra.html), [CME 24/7 client document](https://www.cmegroup.com/globex/files/client-facing-cryptocurrency-futures-and-options-expansion-to-24-7-trading.pdf), [Optimus Futures](https://www.optimusfutures.com/Bitcoin.php)
- Micro Bitcoin futures (MBT) are 0.1 BTC, cash-settled to the CME CF Bitcoin Reference Rate, tick = 5 index points = $0.50 — [CME MBT overview](https://www.cmegroup.com/education/lessons/micro-bitcoin-futures-product-overview.html)

#### 1b. Solana

| Library | Repo | Licence | Stars | Latest release / last commit | Language | What it is for (plain) | Limits |
|---|---|---|---|---|---|---|---|
| solders | [kevinheavey/solders](https://github.com/kevinheavey/solders) | Apache-2.0 | ~449 | v0.29.0, 2026-08-13; commit Oct 2026 | Python (Rust core) | Low-level building blocks: keypairs, addresses, transactions, signing. The "pen and paper" for writing Solana transactions in Python | Does nothing by itself — no strategy, no network client |
| solana-py | [michaelhly/solana-py](https://github.com/michaelhly/solana-py) | MIT | ~1.4k | v0.42.0, 2026-11-11; commit today | Python | RPC client: sends transactions built with solders to a Solana node and reads balances/accounts | Python is slower than Rust/TS for latency-sensitive work |
| anchorpy | [kevinheavey/anchorpy](https://github.com/kevinheavey/anchorpy) | MIT | ~279 | v0.21.0, 2025-03-26; last commit Mar 2025 | Python | Lets Python call Solana programs written with the Anchor framework (most DEXs) | **Stale** (20 months without a commit) |
| Anchor | [solana-foundation/anchor](https://github.com/solana-foundation/anchor) | Apache-2.0 | ~5.2k | commit ~2026-11-20 | Rust/TS | The framework most Solana programs are written in | Developer tool, not a trading tool |
| @solana/kit | [anza-xyz/kit](https://github.com/anza-xyz/kit) | MIT | ~703 | v8.6.0, 2026-10-28; commit today | TypeScript | Current official JS SDK for Solana | — |
| @solana/web3.js | [solana-foundation/solana-web3.js](https://github.com/solana-foundation/solana-web3.js) | MIT | ~2.8k | v3.2.1, 2026-11-10 | TypeScript | Older-lineage JS SDK that most DEX SDKs still depend on | — |
| Jupiter JS client | [jup-ag/jupiter-quote-api-node](https://github.com/jup-ag/jupiter-quote-api-node) | none on GitHub; npm `@jup-ag/api` says MIT | ~246 | v6.0.48, 2025-12-28; last commit Dec 2025 | TypeScript | Typed HTTP client for Jupiter's swap "quote" API (asks Jupiter for the best route across Solana DEXs) | No commit since Dec 2025 while Jupiter moved to Swap API V2 in Mar 2026 (see below) |
| Jupiter Rust client | [jup-ag/jupiter-swap-api-client](https://github.com/jup-ag/jupiter-swap-api-client) | none specified | ~204 | last commit Dec 2025 | Rust | Same, for Rust | Same staleness |
| Meteora DLMM SDK | [MeteoraAg/dlmm-sdk](https://github.com/MeteoraAg/dlmm-sdk) | none on GitHub; npm `@meteora-ag/dlmm` says ISC | ~312 | v1.9.14, 2026-07-23; commit Nov 2026 | TypeScript (+Rust) | Create/adjust/close liquidity positions in Meteora "DLMM" pools (you act as the market maker and earn swap fees) | Licence ambiguity; LP risk (section 5) |
| Raydium SDK V2 | [raydium-io/raydium-sdk-V2](https://github.com/raydium-io/raydium-sdk-V2) | GPL-3.0 | ~354 | v0.2.85-alpha, 2026-11-14 | TypeScript | Swap and LP on Raydium pools | Still versioned "alpha"; GPL |
| Orca Whirlpools | [orca-so/whirlpools](https://github.com/orca-so/whirlpools) | custom ("SEE LICENSE IN LICENSE") | ~569 | `@orca-so/whirlpools` 8.0.1, 2026-06-17; commit Oct 2026 | TS/Rust | Swap and concentrated-liquidity LP on Orca | Custom licence — read before reuse |
| Pump.fun SDKs | npm [@pump-fun/pump-sdk](https://www.npmjs.com/package/@pump-fun/pump-sdk), [@pump-fun/pump-swap-sdk](https://www.npmjs.com/package/@pump-fun/pump-swap-sdk); docs repo [pump-fun/pump-public-docs](https://github.com/pump-fun/pump-public-docs) | MIT (npm) | docs repo ~489 | pump-sdk 4.3.1, 2026-10-22; pump-swap-sdk 2.2.0, 2026-10-19 | TypeScript | Buy/sell on the Pump.fun bonding curve and PumpSwap AMM | Venue where 96% of detected Solana sandwich attacks occurred (section 5) |
| Jito clients | [jito-labs/jito-py-rpc](https://github.com/jito-labs/jito-py-rpc), [jito-labs/jito-js-rpc](https://github.com/jito-labs/jito-js-rpc), npm `jito-ts` | Apache-2.0 | ~73 / ~88 | jito-py-rpc 0.1.5, 2025-06-03; jito-ts 4.2.1, 2025-09-10 | Python / JS | Submit "bundles" (up to 5 transactions that land together or not at all) with a tip to validators | Thin and rarely updated; the JSON-RPC is simple enough to call directly |
| Yellowstone gRPC | [rpcpool/yellowstone-grpc](https://github.com/rpcpool/yellowstone-grpc) | AGPL-3.0 (server); npm client `@triton-one/yellowstone-grpc` Apache-2.0 | ~1k | client v10.0.0, 2026-10-31; commit ~2026-11-18 | Rust/TS | Geyser plugin: a firehose of account/transaction updates straight from a validator — the low-latency data feed serious Solana bots use | Needs a paid RPC provider that exposes it |
| Helius SDK | [helius-labs/helius-sdk](https://github.com/helius-labs/helius-sdk) | MIT | ~299 | v3.5.0, 2026-11-13 | TypeScript | Client for Helius RPC/enhanced APIs | The PyPI package `helius` (0.0.3, 2023) is not a maintained equivalent |

- Jupiter's current recommended API is **Swap API V2** at `https://api.jup.ag/swap/v2`, with `GET /order` + `POST /execute` (meta-aggregator across Metis, JupiterZ, Dflow and OKX) or `GET /build` (Metis router only, you send the transaction yourself) — [Jupiter developer docs index](https://developers.jup.ag/docs/llms.txt)
- Jupiter states the Ultra Swap API "is no longer actively maintained and has been superseded by Swap V2"; Ultra and Metis were unified into one Swap API that went live in March 2026 — [Jupiter Ultra fees doc](https://developers.jup.ag/docs/ultra/fees.md), [Jupiter changelog 2026-03](https://developers.jup.ag/changelog/2026-03)
- `lite-api.jup.ag` was scheduled for deprecation on 2026-01-31, then postponed with a new date "TBA" — [Jupiter changelog 2025-11](https://developers.jup.ag/changelog/2025-11), [Jupiter migration guide](https://developers.jup.ag/docs/portal/migration)
- Jupiter API access tiers: keyless 0.5 requests/sec; Free key 1 RPS; Developer $25/mo 10 RPS; Launch $100/mo 50 RPS; Pro $500/mo 150 RPS; `/swap/v2/execute` has its own bucket (20/50/100 RPS) — [Jupiter developer docs index](https://developers.jup.ag/docs/llms.txt)
- Jupiter fee schedule published for Ultra: 0 bps for pegged pairs and buying JUP/JLP/jupSOL, 2 bps SOL–stable, 5 bps LST–stable, 10 bps everything else, 50 bps for tokens under 24 hours old; integrators can add fees and Jupiter keeps 20% of them. The `/build` route carries no Jupiter swap fee — [Jupiter Ultra fees doc](https://developers.jup.ag/docs/ultra/fees.md), [Jupiter developer docs index](https://developers.jup.ag/docs/llms.txt)
- Jupiter **Trigger V2** (`https://api.jup.ag/trigger/v2`) covers limit orders (single, OCO, OTOCO) and DCA, uses JWT challenge-response auth, and has a $10 minimum per order/round; "Recurring" is still listed as a product but DCA runs on the Trigger V2 flow — [Jupiter developer docs index](https://developers.jup.ag/docs/llms.txt)
- Jupiter also runs a transaction-landing endpoint (`https://tx.jup.ag`) that requires an API key and a tip of at least 0.001 SOL — [Jupiter developer docs index](https://developers.jup.ag/docs/llms.txt)
- Meteora DLMM places liquidity in discrete price "bins"; fees are dynamic ("surge pricing" with volatility); the docs warn LPs to monitor positions to manage impermanent loss, and label DLMM as open beta — [Meteora DLMM docs](https://docs.meteora.ag/overview/products/dlmm), [Meteora strategies doc](https://docs.meteora.ag/overview/products/dlmm/strategies-and-use-cases)
- Helius pricing page: Free $0 (1M credits, 10 RPC req/s, 1 sendTransaction/s); Developer $49/mo (10M credits, 50 RPS); Business $499/mo (100M credits, 200 RPS, LaserStream gRPC included); Professional $999/mo. gRPC streaming on mainnet starts at the $499 tier. (The page's own "last updated" stamp reads 2025-01-20, so re-check.) — [Helius pricing](https://www.helius.dev/pricing)

#### 1c. EVM and Hyperliquid

| Library | Repo | Licence | Stars | Latest release / last commit | Language | What it is for |
|---|---|---|---|---|---|---|
| web3.py | [ethereum/web3.py](https://github.com/ethereum/web3.py) | MIT | ~5.5k | v8.0.0, 2026-08-31; commit Oct 2026 | Python | Talk to Ethereum-style chains from Python |
| ethers.js | [ethers-io/ethers.js](https://github.com/ethers-io/ethers.js) | MIT | ~8.7k | v6.17.0, 2026-06-18 | TS | Same, for JavaScript (older standard) |
| viem | [wevm/viem](https://github.com/wevm/viem) | MIT (npm) | ~3.6k | v2.58.4, 2026-11-21; commit today | TS | Same, newer and most actively developed |
| Uniswap SDKs | [Uniswap/sdks](https://github.com/Uniswap/sdks) | MIT (npm) | ~139 | `@uniswap/v3-sdk` 3.31.11 and `@uniswap/v4-sdk` 2.4.7, both 2026-11-09 | TS | Compute Uniswap quotes, routes and LP positions |
| 0x | legacy [0xProject/0x-monorepo](https://github.com/0xProject/0x-monorepo); npm `@0x/swap-ts-sdk` | ISC (npm) | ~1.4k | monorepo last commit Apr 2021; swap SDK 2.1.1, 2024-10-10 | TS | DEX aggregator (the Swap API is a hosted HTTP service; the old repo is dead) |
| 1inch | [1inch/1inch-sdk](https://github.com/1inch/1inch-sdk) | MIT | ~24 | commit Sep 2026 | TS | DEX aggregator SDK (tiny user base) |
| Flashbots (Python) | [flashbots/web3-flashbots](https://github.com/flashbots/web3-flashbots) | MIT | ~430 | last commit Jul 2024 | Python | Send private transaction bundles to Ethereum block builders — **stale** |
| Flashbots (JS) | npm `@flashbots/ethers-provider-bundle` | ISC | — | v1.0.0, 2024-02-06 | TS | Same for ethers — **stale** |
| mev-boost | [flashbots/mev-boost](https://github.com/flashbots/mev-boost) | MIT | ~1.5k | commit Nov 2026 | Go | Validator-side software, not a trader tool |
| Hyperliquid TS (community) | npm [@nktkas/hyperliquid](https://www.npmjs.com/package/@nktkas/hyperliquid) | MIT | — | v0.33.3, 2026-08-02 | TS | Community TypeScript client for Hyperliquid |

#### 1d. Data wrangling and charting

| Library | Repo | Licence | Stars | Latest release | What it is for |
|---|---|---|---|---|---|
| polars | [pola-rs/polars](https://github.com/pola-rs/polars) | MIT | ~40k | v2.1.0, 2026-10-25 | Fast table/dataframe engine (a quicker pandas) for crunching price history |
| pandas | [pandas-dev/pandas](https://github.com/pandas-dev/pandas) | BSD-3-Clause | ~51k | v3.1.1, 2026-11-04 | The standard Python table library; most trading libraries speak pandas |
| DuckDB | [duckdb/duckdb](https://github.com/duckdb/duckdb) | MIT | ~43k | v2.0.1, 2026-11-20 | In-process SQL database that queries Parquet/CSV files directly — good for tick archives on a laptop |
| plotly.py | [plotly/plotly.py](https://github.com/plotly/plotly.py) | MIT | ~19k | v7.1.0, 2026-09-15 | Interactive charts (candlesticks, equity curves) |
| backtesting.py | [kernc/backtesting.py](https://github.com/kernc/backtesting.py) | AGPL-3.0 | ~9.3k | v0.6.6, 2026-07-22; commit Aug 2026 | Small candle-based strategy backtester |

- Adjacent full frameworks, for context only: freqtrade (GPL-3.0, ~57k stars, commit today), hummingbot (Apache-2.0, ~21k), nautilus_trader (LGPL-3.0, ~32k, v1.231.0 2026-08-02) — [freqtrade](https://github.com/freqtrade/freqtrade), [hummingbot](https://github.com/hummingbot/hummingbot), [nautilus_trader](https://github.com/nautechsystems/nautilus_trader)

### Inferences
- For a US retail bot the practical stack is CCXT (or the official Coinbase/Kraken SDK) for CEX, `ib_async` or the native IB API for IBKR/CME, and solders + solana-py (Python) or @solana/kit + the venue SDKs (TypeScript) for Solana. The Solana DEX SDKs (Jupiter client, Meteora, Raydium, Orca, Pump) are all TypeScript-first; a pure-Python Solana bot ends up calling Jupiter's HTTP API directly and hand-building instructions.
- "Stale" matters more on-chain than on CEX: Jupiter renamed and re-based its API twice in ~12 months (v6 → Ultra → Swap V2), so a client library that has not been committed to since Dec 2025 is likely pointing at legacy endpoints. I did not inspect the `@jup-ag/api` 6.0.48 source to confirm which base URL it uses.
- Licence traps for anyone planning to redistribute a bot: backtesting.py and dYdX clients are AGPL, Raydium SDK is GPL-3.0, cryptofeed's licence is ambiguous between sources, Orca's is custom, and Meteora's and Jupiter's GitHub repos carry no licence file that GitHub recognises. For private, non-distributed use these are not obstacles.

### Gaps
- GitHub API was unreachable; exact star counts, open-issue counts and release notes were not read. Shields.io rounding applies.
- cryptofeed licence: PyPI says AGPL-3.0-or-later, GitHub cannot classify the file. Not resolved.
- No official Python SDK from Kraken, Gemini or Robinhood was identified in this session; `krakenfx/kraken-cli` exists but was not inspected.
- Whether Kraken Derivatives US (Bitnomial perps via NinjaTrader Clearing) exposes a public trading API was not established.
- `ib_async` crypto order support (Paxos/Zero Hash routing, order types accepted via API) was not verified; IBKR's page only confirms non-marketable limit orders exist.
- tastytrade crypto fees via API were not confirmed from an official page.

---

## 2. The viral "cheating toolkit": what are solders, backtesting.py, jupiter-quote-api-node, dlmm-sdk, polars and plotly, what bot do they imply, and do they confer an edge?

### Takeaway
The six repositories are ordinary, free, public plumbing: two pieces for touching Solana DEXs (a Jupiter swap client and a Meteora liquidity-pool SDK), one transaction-signing library, one hobby-grade backtester, one dataframe engine and one charting library. Together they sketch a Solana DEX swap / liquidity-provision bot with a Python research layer, but they contain no strategy, no data feed, no transaction-landing infrastructure and no risk management, so they confer no trading edge by themselves.

### Cited Findings
- **kevinheavey/solders** — Apache-2.0, ~449 stars, v0.29.0 (2026-08-13). Python bindings over Rust for Solana primitives (keys, transactions, signing) — [repo](https://github.com/kevinheavey/solders), [PyPI](https://pypi.org/project/solders/)
- **kernc/backtesting.py** — AGPL-3.0, ~9.3k stars, v0.6.6 (2026-07-22). Candle (OHLC) based backtesting of a strategy on a price series — [repo](https://github.com/kernc/backtesting.py), [PyPI](https://pypi.org/project/backtesting/)
- **jup-ag/jupiter-quote-api-node** — ~246 stars, no GitHub-recognised licence (npm package `@jup-ag/api` declares MIT), v6.0.48 (2025-12-28), last commit Dec 2025. TypeScript client for Jupiter's swap quote API — [repo](https://github.com/jup-ag/jupiter-quote-api-node), [npm](https://www.npmjs.com/package/@jup-ag/api)
- Jupiter itself now directs developers to Swap API V2 (`api.jup.ag/swap/v2`, live March 2026) and says Ultra is superseded; the legacy Metis `/swap/v1/quote` route is described as legacy with migration guides — [Jupiter developer docs index](https://developers.jup.ag/docs/llms.txt)
- **MeteoraAg/dlmm-sdk** — ~312 stars, no GitHub-recognised licence (npm `@meteora-ag/dlmm` declares ISC), v1.9.14 (2026-07-23), commit Nov 2026. SDK for Meteora's Dynamic Liquidity Market Maker pools — [repo](https://github.com/MeteoraAg/dlmm-sdk), [npm](https://www.npmjs.com/package/@meteora-ag/dlmm)
- Meteora's own docs say DLMM strategies "do not remove impermanent loss or out-of-range risk" and tell LPs to monitor and adjust positions — [Meteora strategies doc](https://docs.meteora.ag/overview/products/dlmm/strategies-and-use-cases)
- **pola-rs/polars** — MIT, ~40k stars, v2.1.0 (2026-10-25). Dataframe engine — [repo](https://github.com/pola-rs/polars)
- **plotly/plotly.py** — MIT, ~19k stars, v7.1.0 (2026-09-15). Charting — [repo](https://github.com/plotly/plotly.py)
- Scale check: these are small or generic projects. The three Solana-specific repos have ~250–450 stars each; the two with tens of thousands of stars (polars, plotly) are general data-science tools used far outside trading — shields.io readings above, 2026-11-23.
- The environment such a bot operates in is adversarial: Bitquery (via CryptoSlate, 2026-10-12) counted 6,850,144 sandwich attacks by 2,545 bot wallets on Solana between 2025-10-30 and 2026-10-07, hitting 2,154,994 wallets, with Pump.fun/PumpSwap accounting for 96% — [CryptoSlate](https://cryptoslate.com/solana-sandwich-bots-took-29-7-million-before-costs-bitquery-estimates/)

### Inferences
- The list is mixed-language: jupiter-quote-api-node and dlmm-sdk are TypeScript, the other four are Python. A working bot would need a TypeScript execution process plus a Python research process (or would skip the two TS libraries and call the HTTP APIs directly). A list that mixes them without comment reads like a collage of popular repo names rather than a description of a running system.
- What the combination implies: (a) swap tokens through the Jupiter aggregator; (b) open and rebalance concentrated-liquidity positions on Meteora DLMM to farm swap fees, typically on volatile or memecoin pairs; (c) analyse results with polars and chart them with plotly; (d) "backtest" with backtesting.py.
- The backtest layer does not fit the trading layer. backtesting.py simulates buying and selling one instrument on candles; it has no concept of liquidity bins, pool fees, impermanent loss, priority fees, Jito tips, failed transactions or sandwich losses. Any backtest of a DLMM LP strategy built on it would be structurally optimistic. (Based on the library's documented scope **[background, not re-verified]**.)
- What is missing from the list is exactly what determines outcomes on Solana: a paid low-latency RPC/Geyser feed, a transaction-landing path (Jito or a sender service), token-safety checks (mint/freeze authority), position sizing, and a source of historical pool data. None of the six supplies these.
- "Cheating" is a misnomer. Every item is open source and free; thousands of competitors — including the professional sandwich bots in the Bitquery data — use the same or better tooling. Edge would have to come from strategy, speed or information, not from the library list.
- Legal note for a US retail user: the access status of Jupiter and Meteora front-ends for US persons is unsettled in the sources found (section 3).

### Gaps
- I did not locate or read the original viral post, so its exact claims are not characterised here.
- I did not open the `@jup-ag/api` source to confirm which API generation v6.0.48 targets.
- Meteora's terms of use regarding US persons were not retrieved.

---

## 3. Which deep-liquidity venues are legally usable by a US retail trader in November 2026, and what are the lowest-tier maker/taker fees?

### Takeaway
At the smallest account tier, US spot fees range from effectively zero at Binance.US (0% maker / ~0.02% taker, but thin liquidity) to 0.60% / 1.20% at Gemini; Coinbase Advanced (0.50% / 0.90%, secondary-sourced) and Kraken Pro (0.40% / 0.80%) sit in between, which makes taker-driven intraday strategies uneconomic for small accounts on the deep-liquidity spot venues. The cheap routes are the new CFTC-regulated perpetual-style futures (Coinbase Financial Markets since July 2025, Kraken Derivatives US since June 2026) and CME micros via a futures broker; Hyperliquid has the lowest percentage fees of all but its terms exclude US persons.

### Cited Findings

#### Spot (lowest tier)

| Venue | Maker | Taker | As of | Source / confidence |
|---|---|---|---|---|
| Coinbase Advanced (US) | 0.50% | 0.90% | effective 2026-09-16; first discount tier now starts at $10K 30-day volume (was $25K) | [CryptoDaily](https://cryptodaily.co.uk/2026/09/coinbase-advanced-fees-usdc-vip-tiers) — secondary; Coinbase's own page ([help.coinbase.com](https://help.coinbase.com/en/coinbase/trading-and-funding/advanced-trade/advanced-trade-fees)) returned HTTP 403. Earlier 2026 schedule was 0.60% / 1.20%; older guides quote 0.40% / 0.60% **[conflict across dates]** |
| Kraken Pro (US) | 0.40% | 0.80% | 2026-07-09 | [Kraken blog](https://blog.kraken.com/product/pro/new-kraken-pro-fee-tiers). Tier 2 at $2.5K volume: 0.30% / 0.60%; Tier 3 at $10K volume or $20K assets on platform: 0.22% / 0.38%. For US clients only spot volume and assets-on-platform count toward tier |
| Gemini ActiveTrader / API | 0.60% | 1.20% | page dated 2026-09-01 | [Gemini API fee schedule](https://gemini.com/fees/api-fee-schedule). ≥$10K: 0.40% / 0.80%; ≥$25K: 0.25% / 0.50%; ≥$75K: 0.125% / 0.25% |
| Binance.US | 0.00% | 0.0190% (prose rounds to 0.02%); BNB/USD 0.0095% | change announced 2026-04-22; live page undated | [Binance.US fee page](https://www.binance.us/en/fee), [The Block](https://www.theblock.co/news/markets/2026-04-22-binance-us-slashes-trading-fees-cryptocurrencies-bid-to-attract-users-398477) |
| Robinhood (exchange routing, Legend, API v2) | 0.50% (Tier 1 example) | 0.95% (Tier 1 example) | undated; "rolling out gradually" | [Robinhood crypto fee tiers](https://robinhood.com/us/en/support/articles/crypto-fee-tiers). Range across tiers stated as 0.00%–0.95%; full table is in a PDF not retrieved |
| Robinhood (default market-maker routing) | no explicit fee; Robinhood receives $0.95 per $100 notional from its market maker | — | 2026-06-15 | [Robinhood crypto order routing](https://robinhood.com/support/articles/crypto-order-routing/) (via search summary) |
| Interactive Brokers (Paxos / Zero Hash) | 0.18% of trade value, min $1.75/order (capped at 1%) | same | page read 2026-11 | [IBKR crypto commissions](https://www.interactivebrokers.com/en/pricing/commissions-cryptocurrencies.php?re=amer). 0.15% above $100K/month. Plus $0.15/month Paxos account fee from June 2026 — [IBKR FAQ](https://www.interactivebrokers.com/support/faq/content/1473558174) |
| Alpaca | 0.15% | 0.25% | docs last updated Sep 2025 | [Alpaca crypto fees](https://docs.alpaca.markets/docs/crypto-fees) (Tier 1 = $0–$100K 30-day volume) |
| tastytrade | ~0.75% BTC/ETH, ~1% others, built into price | — | 2026 third-party review | [CryptoSlate review](https://cryptoslate.com/brokers/tastytrade-review/) **[unverified against tastytrade's own schedule]** |

- Binance.US cut fees because volumes collapsed; headlines cite a ~0.20% market share — [Yahoo Finance](https://finance.yahoo.com/news/binance-us-cuts-fees-near-205834438.html), [The Block](https://www.theblock.co/amp/post/370097/crypto-exchange-binance-us-cuts-fees-as-trading-volumes-remain-abysmal)

#### US-regulated derivatives

- **Coinbase Financial Markets (CFM)** launched CFTC-regulated "perpetual-style" futures for US customers on 2025-07-21: nano Bitcoin and nano Ether contracts, up to 10x leverage, with launch coverage quoting fees "as low as 0.02%" — [The Block](https://www.theblock.co/post/363796/coinbase-launches-perpetual-futures), [Decrypt](https://decrypt.co/331180/coinbase-opens-perpetuals-trading-us-customers?amp=1), [CryptoSlate](https://cryptoslate.com/coinbase-starts-cftc-regulated-perpetuals-for-us-traders-offering-10x-leverage-and-0-02-fees/)
- A Coinbase futures product-page footnote says trading fees exclude a $0.15 per-contract charge for exchange, NFA and clearing fees (seen via search snippet only) — [Coinbase futures product page](https://www.coinbase.com/futures/slr-26jun26-cde) **[unverified current rate]**
- Coinbase Derivatives files its per-side, per-contract fee schedule with the CFTC; a 2026 filing lists the nano Bitcoin Perp (BIP) with changes effective 2026-08-17, but the amounts could not be read reliably — [CFTC filing](https://www.cftc.gov/filings/orgrules/rules08032613651.pdf)
- On 2026-05-29 CFM was reportedly cleared to connect US clients to offshore perpetuals/options on Deribit as a foreign futures market — a separate product from the domestic perp-style contracts — [DEXTools news](https://www.dextools.io/news/coinbase-cftc-clearance-us-crypto-perpetual-futures-june-2026) (secondary source)
- **Kraken Derivatives US**: Payward completed its acquisition of Bitnomial around 2026-05-01; Kraken launched CFTC-regulated perpetual futures for US clients on Kraken Pro on 2026-06-15, listed on Bitnomial and offered through NinjaTrader Clearing, LLC d/b/a Kraken Derivatives US (FCM, NFA ID 0309379) — [Bitnomial](https://bitnomial.com/news/2026-05-01/payward-completes-acquisition-bitnomial/), [The Block](https://www.theblock.co/news/markets/2026-06-15-kraken-launches-crypto-perps-trading-in-us-on-kraken-pro-404751), [Kraken blog](https://blog.kraken.com/product/kraken-derivatives-us/first-cftc-regulated-perpetual-futures-for-us-traders)
- Kraken US perp fee, **current page (last updated 2026-10-30)**: all-in $0.0113 per contract per side (commission $0.0003 + exchange/clearing $0.001 + NFA $0.01); funding settles daily at 3:00 pm CT — [Kraken US futures fees](https://support.kraken.com/articles/us-futures-fees). An earlier version of the same page (2026-06-15, seen in a search snippet) showed $0.15 per contract per side ($0.03 + $0.10 + $0.02) **[conflict — the page appears to have been revised; contract size not stated on the fee page, so the bps-equivalent cannot be computed]**
- Kraken Derivatives US also offers CME-listed futures: MES/MNQ $0.39 and ES/NQ $1.29 commission per contract per side; crypto CME contract commissions are shown in the order form rather than on the page — [Kraken US futures fees](https://support.kraken.com/articles/us-futures-fees)
- Kraken launched regulated US spot margin trading in May 2026 — [The Block](https://www.theblock.co/news/markets/2026-05-06-kraken-launches-regulated-crypto-spot-margin-trading-us-bitnomial-deal-400247)
- Kraken's non-US futures schedule, for comparison only: 0.02% maker / 0.05% taker under $5M — [Kraken blog](https://blog.kraken.com/product/pro/new-kraken-pro-fee-tiers)
- Gemini publishes a derivatives schedule (0.02% maker / 0.07% taker at $0 volume, charged in GUSD) — [Gemini API fee schedule](https://gemini.com/fees/api-fee-schedule). US-retail eligibility for that product was not confirmed **[unverified]**
- **CME via a futures broker**: IBKR lists an exchange-fee recovery charge of $1.15 per Micro Bitcoin contract for non-members (broker commission is additional) — [IBKR CME fees](https://investors.interactivebrokers.com/en/accounts/fees/CME.php)

#### On-chain venues and US-person restrictions

- **Hyperliquid**: terms define "Restricted Persons" to include anyone residing, located or incorporated in the United States (and Ontario); enforcement is by geofencing rather than KYC — [Datawallet](https://www.datawallet.com/crypto/is-hyperliquid-available-in-the-usa), [TokenTax](https://tokentax.co/blog/what-is-hyperliquid). As of 2026-09-04 a US entry was a stated aspiration, not a fact — [The Block](https://theblock.co/news/regulation/2026-09-04-trump-wants-hyperliquid-enter-us-how-it-could-happen-413594)
- Hyperliquid base fees (tier 0, 14-day volume under $5M): perps 0.045% taker / 0.015% maker; spot 0.070% taker / 0.040% maker; staking HYPE gives 5–40% discounts; maker rebates only for accounts with >0.5% of maker volume — [Hyperliquid fee docs](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees)
- **dYdX**: opened to US traders for the first time in December 2025 with spot trading on Solana only; perpetuals remain unavailable to US users. dYdX said post-entry fees would be cut to roughly 50–65 bps — [The Block](https://www.theblock.co/post/382180/dydx-spot-trading-solana-us-traders), [Yellow](https://yellow.com/news/dydx-brings-spot-trading-to-america-while-perpetual-contracts-remain-unavailable), [AOL/Benzinga](https://www.aol.com/finance/defi-giant-dydx-coming-america-030511627.html)
- **Jupiter**: a Jupiter help article says Jupiter Mobile is not accessible in certain jurisdictions including the United States, and versions of its terms list the US among places where it does not interact with wallets; a 2026 review states Jupiter "is not available to U.S. residents under its published terms" — [Jupiter help centre](https://jupiverse.zendesk.com/hc/en-us/articles/22632755720732-Why-is-Jupiter-Mobile-not-available-in-my-country), [Jupiter mobile terms](https://jup.ag/mobile/terms), [CryptoSlate](https://cryptoslate.com/?p=527306) **[the current full web-app terms were not retrieved; versions seen were dated 2022 and 2024]**

### Inferences
- Fee arithmetic for a small account: a market-order round trip costs about 1.8% at Coinbase Advanced entry tier, 1.6% at Kraken Pro tier 1, 2.4% at Gemini, ~0.5% at Alpaca, ~0.36% at IBKR (before the $1.75 minimum, which dominates below ~$970 per order), and ~0.04% at Binance.US. Against typical BTC spreads of a fraction of a basis point (section 4), exchange fees — not spreads — are the binding cost for intraday strategies.
- Resting limit orders (maker) halve the cost at Coinbase/Kraken/Gemini but still leave 0.8–1.2% round trip at the lowest tier; reaching $10K of 30-day volume at Kraken (0.22% / 0.38%) materially changes viability.
- The per-contract pricing of US perp-style futures and CME micros is structurally cheaper than spot percentages for intraday trading, but the exact basis-point cost depends on contract sizes and current broker commissions that were not verified here.
- Binance.US's near-zero fees come with thin books; whether spreads there offset the fee saving was not measured.
- On-chain venues are not a clean legal route for a US retail trader: Hyperliquid and Jupiter both publish terms that exclude US persons, and using a VPN to bypass geofencing breaches those terms.

### Gaps
- Coinbase Advanced official US tier table (all tiers) could not be fetched; the 0.50% / 0.90% entry tier is from secondary coverage.
- Current Coinbase US perp-style futures fee in bps or dollars per contract for retail on Coinbase Advanced: not confirmed. Contract list beyond nano BTC/ETH (SOL, XRP etc.) not confirmed.
- Kraken US perp contract sizes, margin and available underlyings; and the reason for the $0.15 → $0.0113 change.
- CME Micro Bitcoin/Ether exchange fee from CME's own schedule, and retail commissions at IBKR, tastytrade, NinjaTrader, Schwab for MBT/MET.
- Robinhood's full tier table and whether API v2 users can yet obtain maker pricing.
- Whether Gemini derivatives are open to US retail; whether Crypto.com, OKX US or Bitstamp US offer cheaper entry tiers (not researched).
- State-by-state availability (for example New York) for each venue.

---

## 4. What are typical bid-ask spreads and depth for BTC, ETH and SOL on these venues versus small caps and Solana memecoins?

### Takeaway
The only dated 2026 measurement found (Solidus Labs, Feb–Apr 2026) shows BTC and ETH trading at well under 1 bp of realised one-second range for sub-$1K trades on centralised venues and on Hyperliquid, versus roughly 2–3 bps on AMM DEXs before fees and gas; no current venue-by-venue Kaiko spread table for US exchanges, and no reliable spread/depth statistics for small caps or memecoins, were found.

### Cited Findings
- Solidus Labs "The Ex Files" covers 2026-02-01 to 2026-04-29 and measures intra-candle (one-second high–low over mid) realised spread, equal-weighted, taker side; venues are anonymised except Hyperliquid, SolFi (Solana) and Uniswap (Ethereum) — [Solidus Labs](https://www.soliduslabs.com/reports/the-ex-files)
- BTC mean spread by trade size (bps), same report: <$1K — CEX-1 0.01, US broker-dealer BD-1 0.13, BD-2 0.03, Hyperliquid 0.08, SolFi 2.84, Uniswap 2.15. $1K–$10K — CEX-1 0.15, BD-1 0.36, Hyperliquid 0.38, SolFi 10.30, Uniswap 6.11. >$100K — CEX-1 3.30, Hyperliquid 2.96, SolFi 13.26, Uniswap 165.54 — [Solidus Labs](https://www.soliduslabs.com/reports/the-ex-files)
- ETH pooled (all sizes): CEX-1 1.13 bps, Hyperliquid 1.71, Uniswap 16.27, SolFi 2.57; the report notes CEX spreads run roughly 2x wider on ETH than BTC — [Solidus Labs](https://www.soliduslabs.com/reports/the-ex-files)
- The same report finds one US broker-dealer's BTC spreads 3–5x higher in the US session than in Asia — [Solidus Labs](https://www.soliduslabs.com/reports/the-ex-files)
- Kaiko (qualitative): spreads on Coinbase and Kraken tightened after spot ETF approvals; tighter BTC spreads on offshore exchanges "primarily reflect their competitive fee structures and market maker incentives, rather than true liquidity advantages over U.S. venues" — [crypto.news citing Kaiko](https://crypto.news/us-spot-crypto-exchanges-nearly-double-market-share-as-etf-era-reshapes-liquidity/), [Kaiko research](https://research.kaiko.com/insights/a-cheatsheet-for-bid-ask-spreads)
- Kaiko (June 2025): the average SOL-USD spread more than halved during H1 2025, with 15 direct SOL-USD spot markets versus 20 each for BTC and ETH — [Kaiko research](https://research.kaiko.com/insights/traders-position-for-potential-sol-etf)
- Spot ETFs have concentrated BTC liquidity into US weekday hours — [The Block](https://www.theblock.co/amp/post/279353/bitcoin-weekend-trading)
- Memecoin market quality proxy: among Jupiter-routed trades on Pump.fun venues, orders set with 20–50% slippage tolerance were sandwiched 14 times as often as those under 3% — which shows that double-digit-percent slippage settings are common enough on memecoins to be studied as a category — [CryptoSlate](https://cryptoslate.com/solana-sandwich-bots-took-29-7-million-before-costs-bitquery-estimates/)
- Jupiter itself charges 50 bps on tokens under 24 hours old versus 2 bps on SOL–stable — a five-to-twenty-five-fold fee step before any price impact — [Jupiter Ultra fees doc](https://developers.jup.ag/docs/ultra/fees.md)

### Inferences
- For BTC/ETH (and by extension SOL majors) on US venues, the quoted spread is one to two orders of magnitude smaller than the lowest-tier taker fee; a small account's cost problem is fees, not spread.
- On AMM DEXs the comparable realised spread is several bps for majors even at retail size, and pool fees, aggregator fees, priority fees and tips come on top. For memecoins, cost is dominated by price impact in shallow pools and by MEV, and can reach percent-level per trade; no rigorous dataset quantifying this by token age or pool size was found.
- The Solidus metric is a realised one-second price range, not a quoted bid-ask spread, and venues are anonymised, so it cannot be mapped to "Coinbase vs Kraken" directly.

### Gaps
- No 2026 Kaiko/CCData table of quoted spread and 1% depth for BTC/ETH/SOL by named US exchange was retrievable (paywalled or not indexed).
- No measured SOL figures in the Solidus report.
- No reliable statistics on spread/depth for small-cap CEX listings or for Solana memecoin pools (by liquidity bucket) were found; this must be measured directly from order books / pool reserves.
- Binance.US book depth after its fee cut was not measured.

---

## 5. What are the realistic costs and risks of on-chain trading on Solana?

### Takeaway
Network fees on Solana are small, but the real costs are adversarial: a documented 6.85 million sandwich attacks in under a year (96% on Pump.fun venues), a token-launch graduation rate near 0.2%, and studies classifying ~99% of Pump.fun launches as pump-and-dumps or rug pulls. Protection (Jito bundles, `jitodontfront`, tight slippage) reduces but does not eliminate these risks, and the default free infrastructure (1 request/second Jito, keyless 0.5 RPS Jupiter) is too thin for competitive execution.

### Cited Findings
- **Sandwich attacks**: 6,850,144 attacks by 2,545 bot wallets hit 2,154,994 distinct wallets between 2025-10-30 and 2026-10-07; gross extraction $29.7M before costs; Pump.fun's launch curve and PumpSwap accounted for 96% of detected attacks (Bitquery estimate, published 2026-10-12) — [CryptoSlate](https://cryptoslate.com/solana-sandwich-bots-took-29-7-million-before-costs-bitquery-estimates/)
- In a 63-attack fee sample from the same study, bots kept 68% of gross proceeds and 18 attacks lost money after costs; other bots' trades made up 39% of the gross take — [CryptoSlate](https://cryptoslate.com/solana-sandwich-bots-took-29-7-million-before-costs-bitquery-estimates/)
- Slippage setting matters: 20–50% slippage trades were sandwiched 14x as often as under-3% trades, though sub-0.5% trades were hit more often than 1–3% trades (observational) — [CryptoSlate](https://cryptoslate.com/solana-sandwich-bots-took-29-7-million-before-costs-bitquery-estimates/)
- **Jito bundles**: minimum tip 1,000 lamports; bundle = up to 5 transactions, executed in order, all-or-nothing in one slot; default rate limit 1 request per second per IP per region with HTTP 429 beyond; `sendTransaction` with `bundleOnly=true` gives revert protection; Jito suggests a 70% priority fee / 30% tip split for `sendTransaction` — [Jito docs](https://docs.jito.wtf/lowlatencytxnsend/)
- Jito warns the 1,000-lamport floor may not win the auction in busy periods, and publishes a live tip-floor API (`bundles.jito.wtf/api/v1/bundles/tip_floor`). The documentation's sample response (dated 2024-09, illustrative only) shows 50th percentile 0.00001 SOL, 95th 0.00145 SOL, 99th 0.010 SOL — [Jito docs](https://docs.jito.wtf/lowlatencytxnsend/)
- An IMC 2026 paper reports that over 86% of single-transaction Jito bundles carry tips too small to obtain priority placement — [IMC 2026 paper](https://cnitarot.github.io/papers/imc26_solana.pdf) (figure via search summary; paper not read in full)
- `jitodontfront`: adding a read-only account whose pubkey starts with `jitodontfront` makes the block engine reject bundles unless that transaction is first; Jito says this "may reduce" sandwiching but is not a guarantee — [Jito docs](https://docs.jito.wtf/lowlatencytxnsend/), [Solana MEV-protection guide](https://solana.com/developers/guides/advanced/mev-protection)
- Tip floors vary by provider: Helius's bundle guide cites 5,000 lamports; Helius Sender Max and Jupiter's `tx.jup.ag` require 0.001 SOL (1,000,000 lamports) — [Helius send-bundle docs](https://docs.helius.dev/docs/sending-transactions/send-bundle.md), [Helius Sender Max](https://www.helius.dev/docs/sending-transactions/sender-max.md), [Jupiter developer docs index](https://developers.jup.ag/docs/llms.txt)
- **Failed transactions**: Blockworks Research is cited for "more than 60% of non-vote transactions fail on Solana" — [Blockworks](https://blockworks.com/news/solana-spam-problem) (article undated in results; likely pre-2026 — treat as historical)
- **Token-launch survival**: a July 2026 preprint analysing 832,941 Pump.fun launches (2026-05-08 to 2026-06-10) found a pooled graduation rate of 0.198% (95% CI 0.189–0.208%), down 3.18x from 0.63% in Sep–Oct 2025 — [arXiv 2607.02823](https://arxiv.org/abs/2607.02823)
- Pump.fun's daily graduation rate later spiked to 6.7% in late July 2026 after the BOOST incentive change; The Block notes BOOST applies after bonding and does not mechanically raise graduation — [The Block](https://theblock.co/news/defi/2026-07-29-pump-fun-token-graduation-rate-jumps-boost-changes-launch-incentives-409815)
- Pump.fun activity fell ~80% in the three months to mid-June 2026 as traders rotated to perps — [The Block](https://theblock.co/news/ecosystems/2026-06-16-pump-fun-activity-craters-80-three-months-solana-fees-lower-traders-rotate-perps-404806)
- **Rug pulls**: Solidus Labs' 2025 report found ~361,000 of ~388,000 Raydium pools showed soft-rug-pull traits (median $2,832 per rug) and classified ~99% of Pump.fun launches as pump-and-dumps or rug pulls (flag-based definition) — [Solidus Labs](https://www.soliduslabs.com/reports/solana-rug-pulls-pump-dumps-crypto-compliance), [The Defiant](https://thedefiant.io/news/defi/alarming-99-of-memecoin-launches-on-pumpfun-are-pump-and-dumps-or-rug-pulls-report)
- A 2026 academic preprint flagged 76,469 rug-pull candidates among 100,063 tokens issued on three Solana DEXs in early 2025 — [arXiv 2603.24625](https://arxiv.org/abs/2603.24625)
- Bitquery (Oct 2026, reported second-hand): 74% of ~2.9 million sampled Solana memecoin buyers had net losses within two weeks — [Analytics Insight](https://www.analyticsinsight.net/meme-coin/how-to-spot-memecoin-scams-and-risky-token-launches) (secondary source)
- **Liquidity provision risk (Meteora DLMM)**: Meteora's docs say dynamic fees are meant to compensate for impermanent loss but strategies "do not remove impermanent loss or out-of-range risk"; concentrated "spot" shapes carry the highest IL risk when price leaves the bin range — [Meteora strategies doc](https://docs.meteora.ag/overview/products/dlmm/strategies-and-use-cases)
- **Network state**: full Firedancer reached mainnet in December 2025; Cointelegraph reported on 2026-10-21 that the Alpenglow consensus upgrade went live on mainnet — [DEXTools news](https://www.dextools.io/news/solana-firedancer-alpenglow-ecosystem-momentum-june-2026), [Cointelegraph](https://cointelegraph.com/news/solanas-alpenglow-launches-mainnet-99-faster-finality) (Alpenglow date rests on a single report; confirm before citing)

### Inferences
- Per-trade explicit cost stack for a swap via Jupiter on a liquid pair: Jupiter fee 0–10 bps (50 bps for new tokens) + pool fee + base/priority fee + optional Jito tip (≥0.000001 SOL, realistically orders of magnitude higher in contested moments, up to the 0.001 SOL minimum on premium senders). For a $100 trade a 0.001 SOL tip alone is a noticeable fraction of a percent; fixed tips penalise small accounts.
- The dominant losses for retail are not fees but adverse selection: sandwiching when slippage tolerance is wide, buying tokens that never graduate (≈99.8% in the May–June 2026 sample), and soft rugs. Token-level checks (is mint authority revoked? is freeze authority revoked? who holds the LP?) are necessary but none of the libraries surveyed performs them automatically.
- Meteora DLMM LP on memecoins is a short-volatility position against informed and bot flow; fee income shown in dashboards is gross of impermanent loss.
- Bundles protect against reverts and reorder risk inside the bundle, not against a bad price: a transaction with wide slippage can still be filled at the worst allowed price.

### Gaps
- Solana base fee per signature (commonly stated as 5,000 lamports) and the priority-fee formula could not be re-verified because [solana.com/docs/core/fees](https://solana.com/docs/core/fees) returned HTTP 429. **[background, not re-verified]**
- No current (2026) median priority fee or Jito tip percentile data was retrieved; the tip-floor API must be queried live.
- No current measured failed-transaction rate for 2026.
- Prevalence of tokens with live mint or freeze authority, and loss statistics attributable to them, were not found in a citable source.
- No independent profitability data for retail Meteora DLMM LPs was found.

---

## 6. What rate limits and reliability issues matter for an unattended bot?

### Takeaway
Free-tier limits are tight enough to shape bot design: Kraken's REST counter allows roughly one call every three seconds sustained at the Starter tier, Jito's public endpoint allows one request per second, Jupiter's keyless tier half a request per second, and Hyperliquid ties an address's request budget to its traded volume. Websockets, not REST polling, are required for anything faster than minute bars.

### Cited Findings
- **Kraken REST**: per-key call counter; max 15 (Starter), 20 (Intermediate), 20 (Pro); decay 0.33/s, 0.5/s, 1/s; ledger/trade-history calls cost 2, others 1; breach returns `EAPI:Rate limit exceeded`; too many concurrent requests return `EService: Throttled` with a retry timestamp; order placement/cancel uses a separate matching-engine limiter — [Kraken REST rate limits](https://docs.kraken.com/exchange/guides/rest/ratelimits.md)
- **Coinbase Exchange API** (the institutional "Exchange" product, not Advanced Trade): public endpoints 10 requests/second per IP with bursts to 15, token-bucket — [Coinbase Exchange rate limits](https://docs.cdp.coinbase.com/exchange/rest-api/rate-limits.md)
- **Hyperliquid**: 1,200 weight per minute per IP for REST (most info calls weigh 20; `l2Book`/`allMids` weigh 2); websockets capped at 10 connections, 1,000 subscriptions, 2,000 messages/minute; each address gets ~1 request per 1 USDC traded with a 10,000-request initial buffer, and when exhausted is limited to one request every 10 seconds; 1,000 open orders by default — [Hyperliquid rate limits](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits)
- **Jito**: 1 request/second per IP per region by default; higher limits by ticket — [Jito docs](https://docs.jito.wtf/lowlatencytxnsend/)
- **Jupiter**: keyless 0.5 RPS; Free key 1 RPS; paid 10/50/150 RPS at $25/$100/$500 per month; 60-second sliding window per organisation — [Jupiter developer docs index](https://developers.jup.ag/docs/llms.txt)
- **Helius RPC**: Free plan 10 RPC requests/second and 1 `sendTransaction`/second; `sendBundle` capped at 5/second per project — [Helius pricing](https://www.helius.dev/pricing), [Helius sendBundle reference](https://docs.helius.dev/docs/api-reference/sender/sendbundle.md)
- **Robinhood API**: v2 orders are charged the taker rate until maker/taker rollout completes — a cost, not a rate, limitation — [Robinhood crypto fee tiers](https://robinhood.com/us/en/support/articles/crypto-fee-tiers)
- **CME 24/7**: weekly Saturday maintenance window 2:00–3:45 a.m. CT, and round-the-clock access depends on the clearing firm — [CME 24/7 client document](https://www.cmegroup.com/globex/files/client-facing-cryptocurrency-futures-and-options-expansion-to-24-7-trading.pdf), [Optimus Futures](https://www.optimusfutures.com/Bitcoin.php)
- **Vendor outage example**: Databento reported CME crypto products unavailable in its live feed (dataset GLBX.MDP3) in March 2026 and ran a temporary separate gateway — [Databento status](https://status.databento.com/incidents/zyy9nvqmr3bz)
- **API churn**: Jupiter announced a lite-api shutdown for 2026-01-31, then postponed it indefinitely; it replaced Ultra with Swap V2 in March 2026 — [Jupiter changelog 2025-11](https://developers.jup.ag/changelog/2025-11), [Jupiter changelog 2026-03](https://developers.jup.ag/changelog/2026-03)
- **Fee-schedule churn in 2026**: Coinbase Advanced (changed at least twice, latest 2026-09-16), Kraken Pro (2026-07-09), Binance.US (2026-04-22), Gemini (page dated 2026-09-01), Kraken US perps (page revised between 2026-06-15 and 2026-10-30) — sources in section 3.
- **CCXT release cadence**: v4.5.94 was published on the day of this research (2026-11-23) — [PyPI ccxt](https://pypi.org/project/ccxt/)

### Inferences
- An unattended bot should: use websockets for data and private order updates; implement exponential backoff on 429/`Rate limit exceeded`; reconcile positions from REST on reconnect; pin library versions (CCXT ships almost daily, and exchange API changes land without notice); and re-read fee schedules programmatically or on a calendar, since four of the five US spot venues changed fees in 2026.
- Hyperliquid's volume-linked request budget penalises quote-heavy, low-fill strategies run from small accounts.
- For IBKR-based execution, the dependency on a locally running TWS/Gateway session and the low activity of `ib_async` are the main operational risks (maintenance evidence in section 1; IBKR's daily restart behaviour is **[background, not re-verified]**).
- For Solana, a free RPC plan (1 `sendTransaction`/second, no gRPC) is adequate for slow rebalancing but not for anything latency-sensitive; gRPC streaming starts at $499/month at Helius.

### Gaps
- Coinbase **Advanced Trade** REST and websocket limits were not retrieved (docs URL returned 404). My recollection is ~30 requests/second private and ~10/second public **[background, not re-verified]**.
- Binance.US, Gemini, Robinhood and Alpaca rate limits were not researched.
- No uptime/incident statistics for the US exchanges' APIs in 2026 were gathered.
- Kraken's separate order-rate (matching-engine) limits were not extracted.

---

## 7. Does CCXT cover the US venues well, including their futures products? And what market-data sources exist?

### Takeaway
CCXT lists every US spot venue relevant here — Coinbase Advanced, Coinbase Exchange, Kraken, Gemini, Binance.US, Alpaca, OKX US, Crypto.com, Bitstamp — all with websocket ("Pro") support bundled into the free MIT package, but none of them is among CCXT's twelve "certified" exchanges, Robinhood is absent, and I found no confirmation that CCXT supports the new US perp products (Coinbase CFM perp-style futures; Kraken's Bitnomial-listed perps). For history, free sources (exchange REST candles, Binance bulk dumps, Tardis's free first-of-month files) cover candles and samples; full tick and order-book history is a paid product.

### Cited Findings

#### CCXT
- CCXT's current README states support for 105 exchange markets and "100+ cryptocurrency exchanges and prediction markets", in JavaScript/TypeScript, Python, C#, PHP, Go, Java and Rust — [CCXT README (npm latest)](https://cdn.jsdelivr.net/npm/ccxt@latest/README.md)
- Certified exchanges per the README: binance, bybit, gate, okx, kucoin, bitget, hyperliquid, bingx, mexc, cryptocom, hashkey, woofipro — [CCXT README](https://cdn.jsdelivr.net/npm/ccxt@latest/README.md)
- Exchange ids present with a "CCXT Pro" (websocket) badge: `coinbase` (labelled Coinbase Advanced), `coinbaseexchange`, `coinbaseinternational`, `kraken`, `krakenfutures`, `gemini`, `binanceus`, `hyperliquid`, `dydx`, `alpaca`, `okxus`, `cryptocom`, `bitstamp`. `robinhood` is not in the (partly truncated) list — [CCXT README](https://cdn.jsdelivr.net/npm/ccxt@latest/README.md)
- CCXT's own docs state CCXT Pro is bundled in the main `ccxt` package with no separate purchase — [CCXT docs comparison page](https://docs.ccxt.com/docs/comparisons/ccxt-vs-kraken-api)
- Kraken Futures is a separate CCXT client (`krakenfutures`) with its own streaming methods — [CCXT docs comparison page](https://docs.ccxt.com/docs/comparisons/ccxt-vs-kraken-api)
- Coinbase exposes CFM (US futures) positions through Advanced Trade REST endpoints (`List Futures Positions`, `Get Futures Position`) — [Coinbase CDP docs](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/futures/list-futures-positions)
- Kraken's US perps are listed on Bitnomial and offered through NinjaTrader Clearing d/b/a Kraken Derivatives US — a different entity and venue from the non-US Kraken Futures platform — [Kraken blog](https://blog.kraken.com/product/kraken-derivatives-us/first-cftc-regulated-perpetual-futures-for-us-traders)
- A targeted search found no CCXT issue, PR or changelog entry about Coinbase CFM perp-style futures or Kraken/Bitnomial perps (absence of evidence, one search) — search run 2026-11-23, no citable page.

#### Market data sources

| Source | Cost | What you get | Evidence |
|---|---|---|---|
| Exchange REST candles via CCXT / official SDKs | free | OHLCV candles, recent trades, current order book for each venue | [CCXT README](https://cdn.jsdelivr.net/npm/ccxt@latest/README.md) |
| Binance public data dumps | free | Bulk historical files for Binance.com markets; helper repo ~2.6k stars, last commit Oct 2026, no licence specified | [binance/binance-public-data](https://github.com/binance/binance-public-data) |
| Tardis.dev | paid; prices only in the order form | Tick-level historical data: trades, order book, quotes, funding, liquidations. Plans by market type (Spot, Perpetuals, Derivatives, Options, All Exchanges) and subscriber type (Academic, Solo, Professional, Business). First day of every month is free for all exchanges and data types without an API key; one-month free trial covers days 1–10 of the prior month. Monthly billing unlocks 4 months of history, quarterly 12 months, yearly 4 years. Coinbase Exchange and Coinbase Derivatives are only in the All Exchanges plan; Kraken spot, Kraken Futures, Binance US (Spot plan) and Hyperliquid are covered | [Tardis billing FAQ](https://docs.tardis.dev/faq/billing-and-subscriptions); clients: [tardis-python](https://github.com/tardis-dev/tardis-python) (MPL-2.0, v5.1.2 2026-11-22), [tardis-machine](https://github.com/tardis-dev/tardis-machine) (MPL-2.0) |
| Databento | paid, usage-based | CME crypto futures are in dataset GLBX.MDP3; client is Apache-2.0, v0.90.0 (2026-11-03). No Coinbase/Kraken spot dataset surfaced in search | [Databento status incident](https://status.databento.com/incidents/zyy9nvqmr3bz), [databento-python](https://github.com/databento/databento-python) |
| Massive (the Python client formerly published under Polygon.io now lives at `massive-com/client-python`, MIT, ~1.5k stars) | paid | Crypto ("Currencies") product exists in the site menu; no crypto plan pricing was visible on the pricing page fetched | [massive-com/client-python](https://github.com/massive-com/client-python), [Massive pricing](https://massive.com/pricing?product=currencies) |
| Coin Metrics community data | free | Community CSV data repo (~59 stars, last commit May 2026, licence not identifiable by GitHub) | [coinmetrics/data](https://github.com/coinmetrics/data) |
| Coinbase institutional market data | paid | Historical datasets from Coinbase Exchange for backtesting | [Coinbase market data](https://www.coinbase.com/institutional/market-data) |
| QuantConnect Coinbase dataset | bundled with QuantConnect | 970 pairs from January 2015, tick to daily | [QuantConnect docs](https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/quantconnect/coinbase-crypto-price-data) |
| CoinGecko / CoinMarketCap APIs | CoinGecko Basic $35/mo, Analyst $129/mo; CoinMarketCap Startup $79/mo billed yearly | Aggregated daily/hourly prices — not exchange-grade ticks | [CoinGecko pricing](https://coingecko.com/api/pricing), [CoinMarketCap pricing](https://coinmarketcap.com/api/pricing) |
| Kaiko | enterprise | Institutional tick, order-book and reference data; S&P Global led an extension of its Series B to $110M | [Kaiko](https://www.kaiko.com/resources/a-cheatsheet-for-bid-ask-spreads) |
| Solana on-chain streams | Helius gRPC from $499/mo; open-source plugin free to self-host | Real-time account/transaction firehose (Yellowstone gRPC / Geyser) | [Helius pricing](https://www.helius.dev/pricing), [yellowstone-grpc](https://github.com/rpcpool/yellowstone-grpc) |

- cryptofeed can be used to record your own tick/order-book history from websockets going forward — [bmoscon/cryptofeed](https://github.com/bmoscon/cryptofeed)

### Inferences
- For US **spot**, CCXT coverage is broad and websocket-capable, but "not certified" means these integrations do not carry CCXT's highest support tier; edge cases (order types, fee reporting, websocket reconnects) should be tested per venue, and the official Coinbase SDK is a sensible fallback for Coinbase.
- For US **futures**, assume CCXT does not cover them until proven otherwise. `krakenfutures` targets Kraken's non-US futures platform, so it should not be assumed to reach the Bitnomial-listed US perps; Coinbase CFM endpoints sit inside the Advanced Trade API that CCXT's `coinbase` class wraps, so partial support is plausible (my recollection is that CCXT's `coinbase` class implements CFM position/balance calls **[background, not re-verified]**). CME micros require a futures broker API (IBKR, tastytrade, NinjaTrader), which CCXT does not provide.
- A small-account researcher can go a long way for free: exchange candles via CCXT, Binance bulk dumps as a deep-liquidity reference series (data use is not restricted to people who can trade there), Tardis first-of-month samples for order-book realism, and self-recorded websocket data. Paying for Tardis is the natural next step when order-book-level backtests on Coinbase/Kraken are needed.
- Funding-rate history matters only for perps; Tardis's Derivatives plan and Binance's bulk files are the standard archives, and the new US perp-style contracts (launched July 2025 and June 2026) have at most 4–16 months of history.

### Gaps
- CCXT support for Coinbase CFM perp-style futures and for Kraken Derivatives US was not confirmed either way; needs a direct read of `ccxt/ts/src/coinbase.ts` and the CCXT changelog.
- Exact contents of Binance bulk dumps (klines, trades, aggTrades, book snapshots, funding rates at data.binance.vision) were not re-verified **[background, not re-verified]**.
- Tardis dollar pricing, CoinAPI pricing, Kaiko pricing, CryptoDataDownload's current terms, and Massive's crypto plan price were not obtained. The Polygon.io → Massive rename is inferred from the GitHub organisation name and was not confirmed on the vendor's page.
- Per-venue REST candle depth limits (how far back and how many bars per call for Coinbase, Kraken, Gemini) were not verified; Kraken's OHLC endpoint is commonly reported to return only the most recent 720 bars **[background, not re-verified]**.
- Funding-rate history endpoints for Coinbase and Kraken US perps were not identified.
- Whether Databento carries any spot-crypto venue was not established.
