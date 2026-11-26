# Intraday forex test harness

Pre-registered test bench for intraday technical rules on spot forex, from the plan in
`reports/Intraday forex TA tools and repos.md`. Result of the first run: test 88 in `TESTS.md`.

```bash
python3 -m research.fx_intraday.data              # download / refresh minute bid-ask bars (FXCM public, ~550 MB cache)
python3 -m research.fx_intraday.run --pair EURUSD # run every pre-registered trial and gate on the development sample
python3 -m pytest -q tests/test_fx_harness.py     # engine, cost and hold-out lock tests
```

| File | Role |
|---|---|
| `PREREGISTRATION.md` | Rules, parameters, costs, gates, hold-out policy. Written before results; never edited after |
| `data.py` | Downloader and loader. Refuses the hold-out (from 2024-12-01) without a token |
| `costs.py` | max(feed spread, base spread) x stress; stop slippage; spread filter |
| `engine.py` | Minute bid/ask simulator: entries at the next bar open, stop-first on ambiguous minutes, gaps fill at the open |
| `rules.py` | The 20 trials |
| `stats.py` | Summaries, SPA / StepM, random-entry null, trade-count power |
| `registry.py` | `trials.csv` (every variant ever run) and `holdout_log.csv` (each rule opens its hold-out once) |
| `run.py` | Runs the protocol and writes `results/` |

To test a new idea: add it to the pre-registration with a date, commit, then add the rule and run.
Every variant run counts toward the snooping correction.
