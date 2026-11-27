# Kalshi daily high temperature: forecast model against market prices: pre-registration (entry 108)

Written 2026-11-27 before any market price was compared with a model probability. Nothing below may change
after results are seen.

User direction: weather first; markets that pay out soon and are liquid enough to get in and out of.

## Markets

Kalshi daily high-temperature series, settled on the NWS daily climate report, payout the next morning. The six
with a median of at least 5,000 contracts per market over the last 34 settled days (scan of 2026-11-27):
New York Central Park (KXHIGHNY, CLINYC), Los Angeles airport (KXHIGHLAX, CLILAX), Miami airport (KXHIGHMIA,
CLIMIA), Chicago Midway (KXHIGHCHI, CLIMDW), Austin Bergstrom (KXHIGHAUS, CLIAUS), Denver airport (KXHIGHDEN,
CLIDEN). The outcome is the market's own settlement value (the official high, whole degrees F).

Contract semantics: "greater" with floor F pays if the high is above F; "less" with cap C pays if below C;
"between" floor F and cap C pays if F <= high <= C.

## Forecast and fair value

Open-Meteo Previous Runs API (default model blend), hourly 2 m temperature at the station's coordinates, in
degrees F. Daily forecast high = maximum over the local standard-time calendar day (the NWS climate day).

- Decision T1, the day before at 14:00 New York time: the "previous_day2" forecast (runs about 48 hours before
  each hour), which existed before T1.
- Decision T0, the day itself at 08:00 local time: the "previous_day1" forecast (runs about 24 hours before each
  hour), which existed before T0.

Error model, per city and decision time: residual = settled high - forecast high, over the previous 45 settled
days only (no trading until 45 days of residuals exist). Mean m = forecast + mean residual; spread s = the
standard deviation of those residuals, at least 1.5 F. The high is treated as normal and rounded to a whole degree:
P(high = k) = N((k + 0.5 - m) / s) - N((k - 0.5 - m) / s).

## Prices, fees and the trade rule

Price = the YES price of the last trade at or before the decision time. A market is tradeable only if that trade
was within the previous 3 hours (the liquidity condition). Fill = that price plus 1 cent (buying YES) or
(1 - price) plus 1 cent (buying NO). Taker fee per contract = 0.07 x fill x (1 - fill), rounded up to the cent.

Buy YES if model probability - fill - fee >= 0.05; buy NO if (1 - model probability) - fill - fee >= 0.05.
At most one position per market and decision time, held to settlement. Each trade stakes the same dollar amount.
Return per dollar = (payout - fill - fee) / (fill + fee).

## Samples

Development: markets settling before 2025-07-01. Hold-out: 2025-07-01 to 2026-11-25, opened once and only if
the development gates pass.

## Gates (development, per decision time)

1. At least 300 trades.
2. Mean return per dollar above zero with a t-statistic of at least 3, standard errors clustered by city-day.
3. Positive in each half of the development sample (split at its middle date).
4. Positive in at least 4 of the 6 cities (cities with fewer than 20 development trades count as not positive).
5. Still positive with fills at 2 cents (not 1) of slippage.

Hold-out: mean return per dollar above zero with one-sided p below 0.05. Passing goes to a live paper bot with the
same rule; real money only after that and the investor's approval.

Also reported: the model's own calibration (predicted probability against outcome frequency), and the market's.
