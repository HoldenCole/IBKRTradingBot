# Quadrant Weekly

A ten-page PDF built from the same data the routines log: quadrant balances, equities, macro and rates,
energy and commodities, technicals, the regime model, the paper books and the method.

## Build

```bash
python3 -m pip install -q pandas numpy python-dotenv loguru openpyxl matplotlib && python3 -m pip install -q --upgrade pillow
python3 -m src.report.build            # gathers data (about 10 minutes cold, member sweeps are cached 12h)
python3 -m src.report.build --cached   # re-render from the last gathered data
```

Output: `reports/Quadrant_Weekly_YYYY-MM-DD.pdf`, dated by the last price date. Rendering uses headless
Chromium through Playwright (`src/report/render.js`). If a page's content runs past the sheet the build prints
`OVERFLOW page N`: shorten that page's commentary and rebuild.

## Commentary

Narrative text is read from `reports/commentary/YYYY-MM-DD.json`. Every key is optional; a missing key falls
back to a sentence generated from the data. Inline `<b>` is allowed.

| key | where it appears | length that fits |
|---|---|---|
| `headline` | cover | one line, about 45 characters |
| `deck` | cover | 3 lines, about 300 characters |
| `changed`, `watch` | cover, lists | 4 items each, about 130 characters per item |
| `qb`, `nasdaq` | pages 2 and 3 ledes | 3 lines and 2 lines |
| `equities`, `macro`, `commodities`, `technicals`, `model`, `paper` | section ledes | up to 4 lines |
| `decision` | page 8 box | three `<p>` blocks, shown as three columns |

Every number written by hand must be checked against the tables on the same page before the PDF is sent.

## Design

- `report/quadrant_weekly.css` is the print stylesheet. `src/report/style.py` holds the colour tokens.
- Quadrant colours (1 blue, 2 green, 3 amber, 4 red) were checked for colour-blind separation on a white surface.
- Charts are inline SVG from `src/report/charts.py`. One y-scale per plot, text in ink, not in a series colour.
- Fonts are bundled in `report/fonts/`: Fraunces, Inter and JetBrains Mono, all under the SIL Open Font License.
