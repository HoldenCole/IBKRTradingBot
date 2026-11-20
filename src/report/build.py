"""Build the weekly PDF report.

    python3 -m src.report.build            # gather data, render reports/Quadrant_Weekly_YYYY-MM-DD.pdf
    python3 -m src.report.build --cached   # reuse research/cache/report_data.pkl

Narrative text comes from reports/commentary/YYYY-MM-DD.json when it exists;
every key it leaves out falls back to a rule-based sentence built from the data.
"""
from __future__ import annotations

import argparse
import html
import json
import pickle
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from src.report import charts as C
from src.report import data as D
from src.report import style as S

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports"
BUILD = OUT / ".build"
FONTS = ROOT / "report" / "fonts"
TF = ("D", "W", "M")
UNITS = {"D": "day", "W": "week", "M": "month"}
ASSET = {"QQQ": "Nasdaq-100", "QLD": "Nasdaq-100, 2x", "TQQQ": "Nasdaq-100, 3x", "SPY": "S&P 500", "ERX": "Energy stocks, 2x",
         "XLE": "Energy stocks", "GLD": "Gold", "GDX": "Gold miners", "DBC": "Commodity basket", "TLT": "Long Treasuries",
         "TMF": "Long Treasuries, 3x", "SHY": "Short Treasuries", "SCO": "Crude oil, 2x short", "IEF": "7-10y Treasuries"}
FLAG_LINE = {
    "INTACT": "Both monthly readings for the S&P 500 are above zero. The long cycle has not broken.",
    "DETERIORATING": "One monthly reading for the S&P 500 is below zero. The long cycle is weakening.",
    "BROKEN": "Both monthly readings for the S&P 500 are below zero. The long cycle has broken.",
    "WASHOUT": "Half or more of S&P 500 members are in a monthly cycle decline. Historically the best long-horizon entry zone.",
}


# ---------- formatting ----------
def pct(v: float, d: int = 1) -> str:
    if v is None or not np.isfinite(v):
        return "n/a"
    return f"{v * 100:+.{d}f}%".replace("-", "−")


def signed(v: float, d: int = 1, unit: str = "") -> str:
    return (f"{v:+.{d}f}" + unit).replace("-", "−")


def level(r: dict) -> str:
    v = r["last"]
    if r["kind"] == "yield":
        return f"{v:.2f}%"
    if r["kind"] == "fx" or v < 20:
        return f"{v:,.3f}" if v < 10 else f"{v:,.2f}"
    return f"{v:,.2f}" if v < 1000 else f"{v:,.0f}"


def chg(r: dict, key: str) -> str:
    if r["kind"] == "yield":
        return "0 bp" if abs(r[key]) < 0.5 else signed(r[key], 0, " bp")
    return pct(r[key])


def e(x) -> str:
    return html.escape(str(x))


def sw(q: int, small: bool = False) -> str:
    return f'<span class="sw q{q}{" sm" if small else ""}">{q}</span>'


def code(st) -> str:
    return f"{st.quadrant}-{st.in_quadrant:02d}-{st.on_side:02d}"


def count_text(st, tf: str) -> str:
    side = "above" if st.quadrant in (2, 3) else "below"
    u = UNITS[tf]
    return f"{u} {st.in_quadrant} · {st.on_side} {u}{'' if st.on_side == 1 else 's'} {side} zero"


def microbar(v: float, scale: float) -> str:
    w = min(abs(v) / scale, 1) * 50
    left = 50 - w if v < 0 else 50
    return f'<span class="mb"><i style="left:{left:.1f}%;width:{w:.1f}%"></i></span>'


def weightbar(w: float, scale: float = 0.35) -> str:
    return f'<span class="wb"><i style="width:{min(w / scale, 1) * 100:.0f}%"></i></span>'


def wave_svg(stroke: float = 2.6, zero: bool = False) -> str:
    """The mark: one swing of an oscillator, coloured by the quadrant it is in."""
    t = np.linspace(-np.pi / 2, 3 * np.pi / 2, 161)
    xs = (t - t[0]) / (t[-1] - t[0]) * 60 + 2
    ys = 12 - np.sin(t) * 9
    parts = []
    for q, m in ((1, t <= 0.001), (2, (t >= 0) & (t <= np.pi / 2 + 0.001)), (3, (t >= np.pi / 2) & (t <= np.pi + 0.001)), (4, t >= np.pi)):
        pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in zip(xs[m], ys[m]))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{S.Q[q]}" stroke-width="{stroke}" stroke-linecap="butt"/>')
    z = '<line x1="0" y1="12" x2="64" y2="12" stroke="#5a6570" stroke-width="0.5"/>' if zero else ""
    return f'<svg viewBox="0 0 64 24" xmlns="http://www.w3.org/2000/svg">{z}{"".join(parts)}</svg>'


# ---------- derived facts ----------
def technical_state(close: pd.Series) -> dict:
    mid = close.rolling(20).mean(); sd = close.rolling(20).std(ddof=0)
    lo = mid - 2 * sd
    below = close < lo
    run = 0
    for v in below.values[::-1]:
        if not v:
            break
        run += 1
    d = close.diff()
    u = d.clip(lower=0).ewm(alpha=0.5, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
    rsi2 = float((100 - 100 / (1 + u / dn.replace(0, np.nan))).iloc[-1])
    downs = 0
    for v in d.values[::-1]:
        if not v < 0:
            break
        downs += 1
    return {"close": float(close.iloc[-1]), "below": bool(below.iloc[-1]), "run": run,
            "depth": float(lo.iloc[-1] / close.iloc[-1] - 1), "rsi2": rsi2, "r1": float(close.iloc[-1] / close.iloc[-2] - 1),
            "r3": float(close.iloc[-1] / close.iloc[-4] - 1), "r5": float(close.iloc[-1] / close.iloc[-6] - 1),
            "z5": D.z5(close), "vs200": float(close.iloc[-1] / close.rolling(200).mean().iloc[-1] - 1), "downs": downs}


# Test 83: mean S&P/Nasdaq ETF return over the next five days after each trigger, win rate, and 1-in-20 worst low.
TRIGGERS = [
    ("Close below the lower band", lambda s: s["below"], ("+0.80%", "64%", "−8.4%"), ("+1.06%", "62%", "−9.3%")),
    ("Second straight close below it", lambda s: s["run"] >= 2, ("+1.11%", "71%", "−8.3%"), ("+1.48%", "66%", "−8.7%")),
    ("Close 1% or more below the band", lambda s: s["below"] and s["depth"] >= 0.01, ("+1.36%", "67%", "−10.8%"), ("+2.00%", "67%", "−15.2%")),
    ("Close 2% or more below the band", lambda s: s["below"] and s["depth"] >= 0.02, ("+2.56%", "71%", "−14.9%"), ("+3.42%", "76%", "−12.9%")),
    ("Five-day drop beyond 2 sigma", lambda s: s["z5"] <= -2, ("+0.93%", "67%", "−9.6%"), ("+1.29%", "64%", "−10.7%")),
    ("Three-day drop of 5% or more", lambda s: s["r3"] <= -0.05, ("+1.59%", "62%", "−13.3%"), ("+1.37%", "62%", "−14.7%")),
]


def facts(d: dict) -> dict:
    f = {}
    byname = {r["name"]: r for grp in ("indices", "sectors", "macro", "commodities") for r in d[grp]}
    f["r"] = byname
    f["sp"], f["ndx"] = byname["S&P 500"], byname["Nasdaq-100"]
    sect = sorted(d["sectors"], key=lambda r: r["wk"])
    f["sect_worst"], f["sect_best"] = sect[0], sect[-1]
    f["sect_down"] = sum(r["wk"] < 0 for r in sect)
    f["tech"] = {s: technical_state(d["px"][s]) for s in ("SPY", "QQQ")}
    st = d["states"]["S&P 500"]
    f["st"] = st
    f["flag"] = d["flag"]["flag"]
    f["stage"] = d["flag"]["weekly_stage"]
    f["growth_on"] = bool(d["classifier"]["spy"].iloc[-1] > 0)
    f["infl_on"] = bool(d["classifier"]["dbc"].iloc[-1] > 0)
    f["asof"] = d["asof"]
    f["month_end"] = (d["asof"] + pd.offsets.BMonthEnd(0))
    f["mq4"] = d["balances"]["M"]["cycle"]["q4"]
    return f


def auto_commentary(d: dict, f: dict) -> dict:
    sp, ndx, st = f["sp"], f["ndx"], f["st"]
    wq, mq = st["W"], st["M"]
    r = f["r"]
    flag = f["flag"]
    dir_w = "fell" if sp["wk"] < 0 else "rose"
    c = {}
    c["headline"] = {"INTACT": "The long cycle is intact", "DETERIORATING": "The long cycle is weakening",
                     "BROKEN": "The long cycle has broken", "WASHOUT": "A monthly washout"}[flag]
    c["deck"] = (f"The S&P 500 {dir_w} <b>{pct(abs(sp['wk']))[1:]}</b> this week to {sp['last']:,.0f}. The Nasdaq-100 moved {pct(ndx['wk'])}. "
                 f"Quadrant balances flag: <b>{flag}</b>, {f['stage']}.")
    c["changed"] = [
        f"<b>Stocks.</b> {f['sect_down']} of 11 S&P sectors fell. {f['sect_worst']['name']} {pct(f['sect_worst']['wk'])}, {f['sect_best']['name']} {pct(f['sect_best']['wk'])}.",
        f"<b>Weekly state.</b> S&P 500 cycle {code(wq['cycle'])}, trend {code(wq['trend'])}.",
        f"<b>Regime model.</b> The S&P 500 is {pct(d['classifier']['spy'].iloc[-1])} against its 10-month line, commodities {pct(d['classifier']['dbc'].iloc[-1])}. Next month is provisionally {d['prov_quadrant']}.",
        f"<b>Rates and volatility.</b> The 10-year yield moved {chg(r['US 10-year yield'], 'wk')} to {r['US 10-year yield']['last']:.2f}%. VIX closed at {r['VIX']['last']:.1f}.",
        f"<b>Commodities.</b> WTI {pct(r['WTI crude']['wk'])}, gold {pct(r['Gold']['wk'])}, natural gas {pct(r['Natural gas']['wk'])}.",
    ]
    c["watch"] = [
        f"<b>Month-end, {f['month_end']:%-d %b}.</b> SPY needs {pct(d['to_boundary']['spy'])} to sit on its 10-month line. DBC needs {pct(d['to_boundary']['dbc'])}.",
        f"<b>Monthly washout line.</b> 50% of members in a monthly cycle decline. Today {f['mq4']:.0f}%.",
        f"<b>Weekly stage.</b> Declines in weeks 1 to 3 have been poor entries. Week 4 onward has been better.",
    ]
    c["qb"] = (f"Daily cycle {code(st['D']['cycle'])}, weekly {code(wq['cycle'])}, monthly {code(mq['cycle'])}. "
               f"{d['balances']['D']['cycle']['q4']:.0f}% of members are in a daily cycle decline, {d['balances']['W']['cycle']['q4']:.0f}% weekly, {f['mq4']:.0f}% monthly.")
    c["nasdaq"] = "The same three bar sizes for the Nasdaq-100, then what each stage has meant for forward returns in two separate eras."
    c["equities"] = f"{f['sect_down']} of 11 sectors fell on the week. The equal-weight S&P 500 moved {pct(r['S&P 500 equal weight']['wk'])} against {pct(sp['wk'])} for the cap-weighted index."
    c["macro"] = (f"The 10-year yield closed at {r['US 10-year yield']['last']:.2f}%, {chg(r['US 10-year yield'], 'wk')} on the week. "
                  f"The dollar index moved {pct(r['Dollar index']['wk'])}. VIX {r['VIX']['last']:.1f}, MOVE {r['MOVE (bond vol)']['last']:.0f}.")
    c["commodities"] = (f"WTI closed at {r['WTI crude']['last']:.2f}, {pct(r['WTI crude']['wk'])} on the week and {pct(r['WTI crude']['mtd'])} this month. "
                        f"Gold {pct(r['Gold']['wk'])}, copper {pct(r['Copper']['wk'])}.")
    t = f["tech"]
    c["technicals"] = (f"SPY closed {'below' if t['SPY']['below'] else 'inside'} its lower Bollinger band with a 2-day RSI of {t['SPY']['rsi2']:.1f}. "
                       f"QQQ closed {'below' if t['QQQ']['below'] else 'inside'} its band with a 2-day RSI of {t['QQQ']['rsi2']:.1f}.")
    c["model"] = (f"{d['in_force'].title()} is in force for {pd.Period(d['ledger_month']).strftime('%B')}. "
                  f"On today's prices the next month would be {d['prov_quadrant'].title()}.")
    c["decision"] = ""
    return c


def load_commentary(d: dict, f: dict) -> dict:
    c = auto_commentary(d, f)
    p = OUT / "commentary" / f"{d['asof'].date()}.json"
    if p.exists():
        c.update({k: v for k, v in json.loads(p.read_text()).items() if v})
        c["_hand"] = True
    return c


# ---------- page parts ----------
def page(n: int, total: int, section: str, body: str, d: dict, cls: str = "") -> str:
    meta = f"Week {d['asof'].isocalendar().week} · {d['asof']:%-d %b %Y}"
    return f'''<section class="page {cls}">
<div class="rh"><div class="brand">{wave_svg(3.2)}<span>Quadrant Weekly</span></div><div>{e(section)}</div><div class="meta">{meta}</div></div>
{body}
<div class="rf"><span>Private research for one account. Signals are rules applied to prices, not advice. Sources and method on the last page.</span><span class="pg">{n:02d} / {total:02d}</span></div>
</section>'''


def sec(no: int, title: str, lede: str) -> str:
    return f'<div class="sec"><div class="no">{no:02d}</div><h2>{e(title)}</h2><p class="lede">{lede}</p></div>'


def state_cell(st, tf: str) -> str:
    return (f'<div class="st">{sw(st.quadrant)}<div><div class="nm">{S.Q_NAME[st.quadrant]} <span class="code">{code(st)}</span></div>'
            f'<div class="ct">{count_text(st, tf)}</div></div></div>')


def seg(b: dict) -> str:
    out = []
    for q in (4, 1, 2, 3):
        v = b[f"q{q}"]
        out.append(f'<i class="q{q}" style="flex:{max(v, 0.6):.2f}">{f"{v:.0f}" if v >= 9 else ""}</i>')
    return f'<div class="seg">{"".join(out)}</div>'


def board(d: dict) -> str:
    rows = []
    for name in ("S&P 500", "Nasdaq-100"):
        for k, osc in enumerate(("cycle", "trend")):
            lab = f'<div class="rl">{name}<small>{osc.title()}</small></div>'
            cells = "".join(f"<td>{state_cell(d['states'][name][tf][osc], tf)}</td>" for tf in TF)
            rows.append(f'<tr class="{"grp" if k == 0 else ""}"><td>{lab}</td>{cells}</tr>')
    for k, osc in enumerate(("cycle", "trend")):
        lab = f'<div class="rl">S&P 500 members<small>{osc.title()}, % in each quadrant</small></div>'
        cells = "".join(f"<td>{seg(d['balances'][tf][osc])}</td>" for tf in TF)
        rows.append(f'<tr class="{"grp" if k == 0 else ""}"><td>{lab}</td>{cells}</tr>')
    head = "".join(f'<th>{S.TF_NAME[tf]}<span class="tfn">{x}</span></th>' for tf, x in zip(TF, ("fast, feeds the weekly", "feeds the monthly", "the long cycle")))
    legend = "".join(f'<span>{sw(q, True)}<b>{S.Q_NAME[q]}</b> {S.Q_DESC[q]}</span>' for q in (1, 2, 3, 4))
    return (f'<div class="board"><table><tr><th>Quadrant balances</th>{head}</tr>{"".join(rows)}</table>'
            f'<div class="legend">{legend}</div></div>')


def flag_card(d: dict, f: dict) -> str:
    st = f["st"]
    growth = "ON" if f["growth_on"] else "OFF"
    agree = (f["flag"] in ("INTACT", "WASHOUT")) == f["growth_on"]
    vs = ("The two agree." if agree else
          "The two disagree. Since 1987 the model's exits were whipsaws more often than not while this flag was intact.")
    return f'''<div class="flag"><div class="lab">In or out flag</div><div class="val">{f["flag"].title()}</div>
<div class="stage">{e(f["stage"])}</div>
<p>{FLAG_LINE[f["flag"]]}</p>
<p>Weekly trend is in {UNITS["W"]} <b>{st["W"]["trend"].in_quadrant}</b> of its current quadrant, weekly cycle in week <b>{st["W"]["cycle"].in_quadrant}</b>. Monthly members in a cycle decline: <b>{f["mq4"]:.0f}%</b> against a 50% washout line.</p>
<p class="vs"><b>Regime model: growth dial {growth}.</b> {vs}</p></div>'''


def tiles(f: dict) -> str:
    r = f["r"]
    items = [("S&P 500", r["S&P 500"]), ("Nasdaq-100", r["Nasdaq-100"]), ("10-year yield", r["US 10-year yield"]),
             ("VIX", r["VIX"]), ("WTI crude", r["WTI crude"]), ("Gold", r["Gold"])]
    out = []
    for k, row in items:
        v = f"{row['last']:.2f}%" if row["kind"] == "yield" else (f"{row['last']:,.1f}" if row["last"] < 100 else f"{row['last']:,.0f}")
        if k == "WTI crude":
            v = f"${row['last']:.2f}"
        if k == "Gold":
            v = f"${row['last']:,.0f}"
        out.append(f'<div class="tile"><div class="k">{k}</div><div class="v">{v}</div>'
                   f'<div class="c"><span>Week</span>{chg(row, "wk")}</div><div class="c"><span>Year</span>{chg(row, "ytd")}</div></div>')
    return f'<div class="tiles">{"".join(out)}</div>'


def cover(d: dict, f: dict, c: dict, total: int) -> str:
    a = d["asof"]
    li = lambda xs: "".join(f"<li>{x}</li>" for x in xs)  # noqa: E731
    return f'''<section class="page cover">
<div class="mast"><div class="top"><span>WEEK {a.isocalendar().week} · {a.year}</span><span>Week ending {a:%A %-d %B %Y}</span></div>
<h1>Quadrant <em>Weekly</em></h1>
<div class="tag">Trend, cycle and regime across equities, rates, energy and commodities. One page of signals, then the evidence.</div>
<div class="wave">{wave_svg(2.2, zero=True)}</div></div>
<div class="body">
<div class="kicker">This week</div>
<div class="headline">{c["headline"]}</div>
<div class="deck">{c["deck"]}</div>
{board(d)}
<div class="trio">{flag_card(d, f)}
<div><h3>What changed</h3><ul class="pts">{li(c["changed"])}</ul></div>
<div><h3>What to watch</h3><ul class="pts">{li(c["watch"])}</ul></div></div>
{tiles(f)}
<div class="rf"><span>Private research for one account. Signals are rules applied to prices, not advice. Sources and method on the last page.</span><span class="pg">01 / {total:02d}</span></div>
</div></section>'''


def tf_head(d: dict, name: str, tf: str, members: bool) -> str:
    st = d["states"][name][tf]
    def it(osc):
        s = st[osc]
        return (f'<div class="it"><span class="lab">{osc}</span>{sw(s.quadrant)}<b>{S.Q_NAME[s.quadrant]}</b>'
                f'<span class="ct">{UNITS[tf]} {s.in_quadrant}</span><span class="code">{code(s)}</span></div>')
    mem = ""
    if members:
        b = d["balances"][tf]
        mem = f'<div class="mem">Members declining: cycle <b>{b["cycle"]["q4"]:.0f}%</b>, trend <b>{b["trend"]["q4"]:.0f}%</b></div>'
    return f'<div class="tfh"><div class="tf">{S.TF_NAME[tf]}</div>{it("cycle")}{it("trend")}{mem}</div>'


def qb_rows(d: dict, name: str, members: bool, height: float) -> str:
    out = []
    for tf in TF:
        fig = C.qb_row(d["idx_close"][name], d["balance_hist"][tf] if members else None, tf, name, with_balances=members,
                       bars_override=d["idx_monthly"][name] if tf == "M" else None, height=height)
        out.append(tf_head(d, name, tf, members) + f'<div class="fig">{fig}</div>')
    return "".join(out)


KEY_TEXT = '''<div class="keytxt"><p><b>Two oscillators.</b> Cycle turns fast, trend turns slowly. Each is always in one of four quadrants. The code <span class="code">4-03-25</span> reads: quadrant 4, third bar in it, 25th bar below zero. A low middle number means the move is young.</p>
<p><b>On the charts.</b> The strips under each price line show the quadrant through time. Triangles mark the trend crossing zero: up starts an advance, down starts a decline. The areas on the right count S&P 500 members in each quadrant.</p></div>'''


def page_qb(d, f, c, n, total):
    body = (sec(2, "Quadrant balances: S&P 500", c["qb"])
            + f'<div class="cols2" style="align-items:center"><div class="fig">{C.quadrant_key()}</div>{KEY_TEXT}</div>'
            + qb_rows(d, "S&P 500", True, 1.92))
    return page(n, total, "Quadrant balances", body, d)


def page_nasdaq(d, f, c, n, total):
    st = f["st"]["W"]["trend"]
    stage = st.in_quadrant if st.quadrant == 4 else None
    disc = '''<table class="t tight"><tr><th class="l">Weeks with weekly cycle and trend both declining</th><th>Monthly readings<br>both above zero</th><th>A monthly reading<br>below zero</th></tr>
<tr><td>S&P 500, next 4 weeks</td><td>+1.5% / +2.7%</td><td>−1.1% / +3.7%</td></tr>
<tr class="hl"><td>Next 13 weeks</td><td class="b">+4.6% / +7.0%</td><td class="b">−0.8% / +1.1%</td></tr>
<tr><td>Share of cases up at 13 weeks</td><td>80% / 81%</td><td>61% / 52%</td></tr>
<tr><td>Worst 13 weeks</td><td>−10% / −10%</td><td>−21% / −30%</td></tr>
<tr><td>Weeks in sample</td><td>65 / 68</td><td>33 / 21</td></tr></table>'''
    wash = '''<table class="t tight"><tr><th class="l">Members in a monthly cycle decline</th><th>Months</th><th>Next 6 months</th><th>Next 12 months</th><th>Next 24 months</th><th>Up at 12 months</th></tr>
<tr><td>Under 10%</td><td>72 / 93</td><td>+5.3% / +5.4%</td><td>+9.8% / +10.2%</td><td>+26.6% / +17.6%</td><td>86% / 81%</td></tr>
<tr><td>40 to 50%</td><td>13 / 12</td><td>+10.3% / −3.3%</td><td>+13.4% / −1.2%</td><td>+14.4% / +21.7%</td><td>69% / 67%</td></tr>
<tr class="hl"><td>50% or more: washout</td><td>7 / 13</td><td>+9.5% / +8.8%</td><td class="b">+17.5% / +21.4%</td><td>+33.0% / +39.2%</td><td>100% / 92%</td></tr></table>'''
    mq4 = f["mq4"]
    body = (sec(3, "Nasdaq-100, and what the stage has meant", c["nasdaq"])
            + qb_rows(d, "Nasdaq-100", False, 1.24)
            + '<div class="gap"></div><div class="cols2" style="grid-template-columns:3.3in minmax(0,1fr)"><div><h3>S&P 500, next 13 weeks<span class="sub">by week of a weekly trend decline</span></h3>'
            + f'<div class="fig">{C.stage_chart(stage)}</div></div>'
            + f'<div><h3>The monthly state decides<span class="sub">1987-2006 / 2007-2026</span></h3>{disc}</div></div>'
            + f'<div class="gap"></div><h3>The washout thesis<span class="sub">S&P 500 forward return by share of members in a monthly cycle decline, 1987-2006 / 2007-2026. Today: {mq4:.0f}%</span></h3>{wash}'
            + '<p class="src">Tests 84 and 85. Member history uses today\'s constituents, so past washouts are understated. The 40 to 50% zone is where 2008 passed through on the way down.</p>')
    return page(n, total, "Quadrant balances", body, d)


def perf_table(rows: list[dict], bars: bool = True) -> str:
    scale = max(abs(r["wk"]) for r in rows if r["kind"] != "yield") if any(r["kind"] != "yield" for r in rows) else 1
    out = ['<table class="t"><tr><th class="l"></th><th>Last</th><th>Week</th><th>Month to date</th><th>Year to date</th><th>From 1y high</th><th>vs 200-day</th></tr>']
    for r in rows:
        bar = "" if r["kind"] == "yield" or not bars else microbar(r["wk"], scale)
        y = r["kind"] == "yield"
        out.append(f'<tr><td>{e(r["name"])}<span class="sym">{e(r["sym"].replace("^", "").replace("=F", "").replace("=X", ""))}</span></td><td>{level(r)}</td>'
                   f'<td>{bar}{chg(r, "wk")}</td><td>{chg(r, "mtd")}</td><td>{chg(r, "ytd")}</td>'
                   f'<td>{"" if y else pct(r["off_high"])}</td><td>{"" if y else pct(r["vs200"])}</td></tr>')
    out.append("</table>")
    return "".join(out)


def sector_board(d: dict) -> str:
    scale = max(abs(r["wk"]) for r in d["sectors"])
    head = ('<table class="t tight"><tr><th class="l">Sector</th><th>Week</th><th>Month</th><th>Year</th><th>vs 200-day</th>'
            + "".join(f'<th class="c">{S.TF_NAME[tf]}<br>cycle · trend</th>' for tf in TF) + "</tr>")
    rows = []
    for r in sorted(d["sectors"], key=lambda r: -r["wk"]):
        ss = d["sector_states"].get(r["sym"])
        cells = ""
        for tf in TF:
            if ss:
                cy, tr = ss[tf]["cycle"], ss[tf]["trend"]
                cells += (f'<td class="c"><span class="pair">{sw(cy.quadrant, True)}<span class="n">{cy.in_quadrant:02d}</span>'
                          f'{sw(tr.quadrant, True)}<span class="n">{tr.in_quadrant:02d}</span></span></td>')
            else:
                cells += "<td></td>"
        rows.append(f'<tr><td>{e(r["name"])}<span class="sym">{r["sym"]}</span></td><td>{microbar(r["wk"], scale)}{pct(r["wk"])}</td>'
                    f'<td>{pct(r["mtd"])}</td><td>{pct(r["ytd"])}</td><td>{pct(r["vs200"])}</td>{cells}</tr>')
    return head + "".join(rows) + "</table>"


def sm_item(d, title, sym, kind="price", ma=200, r=None, sub=None):
    s = d["px"][sym] if isinstance(sym, str) else sym
    if sub is None and r is not None:
        sub = f"{level(r)}  ·  {chg(r, 'wk')} week"
    return {"title": title, "series": s, "kind": kind, "ma": ma, "sub": sub or ""}


def page_equities(d, f, c, n, total):
    r = f["r"]
    items = [sm_item(d, nm, sym, r=r[nm]) for nm, sym in (("S&P 500", "^GSPC"), ("Nasdaq-100", "^NDX"), ("Russell 2000", "^RUT"),
                                                          ("Dow Industrials", "^DJI"), ("S&P 500 equal weight", "RSP"))]
    rel = (d["px"]["RSP"] / d["px"]["SPY"]).dropna(); rel = rel / rel.iloc[-252] * 100
    wk0 = rel[rel.index <= d["anchors"]["wk"]].iloc[-1]
    items.append(sm_item(d, "Equal weight relative to cap weight", rel, sub=f"one year ago = 100  ·  {pct(rel.iloc[-1] / wk0 - 1)} week"))
    body = (sec(4, "Equities", c["equities"])
            + "<h3>Indices</h3>" + perf_table(d["indices"])
            + '<div class="gap"></div><h3>One year<span class="sub">daily close and 200-day average</span></h3>'
            + f'<div class="fig">{C.small_multiples(items, row_h=1.42)}</div>'
            + '<div class="gap"></div><h3>Sector board<span class="sub">ranked by the week. Each square is the quadrant, the number beside it is bars spent there</span></h3>'
            + sector_board(d)
            + '<p class="src">' + " ".join(f"{sw(q, True)} {S.Q_NAME[q]} &nbsp;" for q in (1, 2, 3, 4)) + " Sector states are computed on the SPDR sector funds.</p>")
    return page(n, total, "Equities", body, d)


def page_macro(d, f, c, n, total):
    r = f["r"]
    px = d["px"]
    curve = (px["^TNX"] - px["^IRX"]).dropna()
    items = [
        sm_item(d, "US 10-year yield", "^TNX", "yield", r=r["US 10-year yield"]),
        sm_item(d, "US 30-year yield", "^TYX", "yield", r=r["US 30-year yield"]),
        sm_item(d, "Curve: 10-year minus 3-month", curve, "pp", sub=f"{signed(curve.iloc[-1], 2)} points  ·  {signed((curve.iloc[-1] - curve[curve.index <= d['anchors']['wk']].iloc[-1]) * 100, 0, ' bp')} week"),
        sm_item(d, "Dollar index", "DX-Y.NYB", r=r["Dollar index"]),
        sm_item(d, "USD/JPY", "JPY=X", r=r["USD/JPY"]),
        sm_item(d, "High-yield bonds (HYG)", "HYG", r=r["High-yield bonds (HYG)"]),
        sm_item(d, "VIX", "^VIX", r=r["VIX"]),
        sm_item(d, "MOVE (bond volatility)", "^MOVE", r=r["MOVE (bond vol)"]),
        sm_item(d, "Long Treasuries (TLT)", "TLT", r=r["Long Treasuries (TLT)"]),
    ]
    body = (sec(5, "Macro and rates", c["macro"]) + "<h3>Rates, dollar, credit, volatility<span class=\"sub\">yield changes in basis points</span></h3>"
            + perf_table(d["macro"], bars=False)
            + '<div class="gap"></div><h3>One year<span class="sub">daily close and 200-day average</span></h3>'
            + f'<div class="fig">{C.small_multiples(items, row_h=1.44)}</div>'
            + '<p class="src">HYG and TLT are total-return prices. FX and index levels from Yahoo Finance.</p>')
    return page(n, total, "Macro and rates", body, d)


def stretch_table(d: dict) -> tuple[str, list[str]]:
    scale = max(abs(r["wk"]) for r in d["commodities"])
    out = ['<table class="t"><tr><th class="l"></th><th>Last</th><th>Week</th><th>Month to date</th><th>Year to date</th>'
           '<th>5-day sigma</th><th>vs 210-day</th><th class="l" style="padding-left:12pt">Mean-reversion read</th></tr>']
    hits = []
    for r in d["commodities"]:
        z, v = r["z5"], r["vs210"]
        if z <= -2 and v > 0:
            read, on = "Sold off hard, above trend: bounce rule met", True
            hits.append(r["name"])
        elif z <= -2:
            read, on = "Sold off hard, below trend: no edge", False
        elif z >= 2:
            read, on = "Stretched up: fading has not paid", False
        else:
            read, on = "No signal", False
        out.append(f'<tr class="{"hl" if on else ""}"><td>{e(r["name"].split(" (")[0])}<span class="sym">{e(r["sym"].replace("=F", ""))}</span></td><td>{level(r)}</td>'
                   f'<td>{microbar(r["wk"], scale)}{pct(r["wk"])}</td><td>{pct(r["mtd"])}</td><td>{pct(r["ytd"])}</td>'
                   f'<td>{signed(z, 1)}</td><td>{pct(v)}</td><td class="l{"" if on or abs(z) >= 2 else " mu"}" style="padding-left:12pt"><span class="dot{" on" if on else ""}"></span>{read}</td></tr>')
    out.append("</table>")
    return "".join(out), hits


def page_commodities(d, f, c, n, total):
    tbl, hits = stretch_table(d)
    by = {r["name"]: r for r in d["commodities"]}
    names = [("WTI crude", "CL=F"), ("Brent crude", "BZ=F"), ("Natural gas", "NG=F"), ("Gold", "GC=F"), ("Silver", "SI=F"),
             ("Copper", "HG=F"), ("Commodity index (DBC)", "DBC"), ("Energy equities (XLE)", "XLE"), ("Gold miners (GDX)", "GDX")]
    items = [sm_item(d, nm, sym, "small" if by[nm]["last"] < 20 else "price", r=by[nm]) for nm, sym in names]
    body = (sec(6, "Energy and commodities", c["commodities"])
            + '<h3>Levels and stretch<span class="sub">5-day move in units of its own 60-day volatility</span></h3>' + tbl
            + '<p class="src">Test 81: buying a 5-day drop beyond 2 sigma paid in energy, oil, commodities and gold only while price was still above its 210-day line. Below the line the sell-off continued. Informational, not traded.</p>'
            + '<div class="gap"></div><h3>One year<span class="sub">daily close and 200-day average</span></h3>'
            + f'<div class="fig">{C.small_multiples(items, row_h=1.5)}</div>')
    return page(n, total, "Energy and commodities", body, d)


def trigger_table(f: dict) -> str:
    t = f["tech"]
    out = ['<table class="t tight"><tr><th class="l">Buy trigger at the close</th><th class="l">SPY</th><th>Next 5 days</th><th>Up</th><th>1-in-20 low</th>'
           '<th class="l" style="padding-left:14pt">QQQ</th><th>Next 5 days</th><th>Up</th><th>1-in-20 low</th></tr>']
    for name, fn, hs, hq in TRIGGERS:
        a, b = fn(t["SPY"]), fn(t["QQQ"])
        cell = lambda on: f'<span class="dot{" on" if on else ""}"></span>{"fired" if on else "not fired"}'  # noqa: E731
        out.append(f'<tr class="{"hl" if a or b else ""}"><td>{name}</td><td class="l{"" if a else " mu"}">{cell(a)}</td><td>{hs[0]}</td><td>{hs[1]}</td><td>{hs[2]}</td>'
                   f'<td class="l{"" if b else " mu"}" style="padding-left:14pt">{cell(b)}</td><td>{hq[0]}</td><td>{hq[1]}</td><td>{hq[2]}</td></tr>')
    out.append("</table>")
    return "".join(out)


def swing_box(d: dict, f: dict) -> str:
    px = d["px"]
    rows, tot = [], 0.0
    for t in d["swing_trades"]:
        if t.get("exit_date"):
            continue
        last = float(px[t["symbol"]].iloc[-1]); ep = float(t["entry_px"])
        ret = last / ep - 1; tot += 0.5 * ret
        held = int((px[t["symbol"]].index > pd.Timestamp(t["entry_date"])).sum())
        sma5 = float(px[t["symbol"]].tail(5).mean())
        rows.append(f'<tr><td>{t["symbol"]}</td><td>{pd.Timestamp(t["entry_date"]):%-d %b}</td><td>{ep:,.2f}</td><td>{last:,.2f}</td>'
                    f'<td>{pct(ret)}</td><td>{held} of 10</td><td>close above {sma5:,.2f}</td></tr>')
    closed = [t for t in d["swing_trades"] if t.get("exit_date")]
    if not rows:
        tbl = '<p class="note">No open positions.</p>'
    else:
        tbl = ('<table class="t tight"><tr><th class="l">Open</th><th>Entered</th><th>Entry</th><th>Last</th><th>Open result</th><th>Days held</th><th>Exit rule today</th></tr>'
               + "".join(rows) + "</table>")
    return (f'<h3>Swing paper account<span class="sub">separate from the portfolio. Two half-size slots, SPY and QQQ, exit on a close above the 5-day average or after 10 days</span></h3>{tbl}'
            f'<p class="src">{len(closed)} closed trades since the log began on 13 November. Open result on the account at 1x: {pct(tot)}. Long-run test: +6.3% a year, worst drawdown −14% at 1x.</p>')


def page_technicals(d, f, c, n, total):
    px = d["px"]
    body = (sec(7, "Technicals", c["technicals"])
            + f'<div class="fig">{C.technical_chart(px["SPY"], "SPY  ·  S&P 500 ETF")}</div>'
            + f'<div class="fig" style="margin-top:4pt">{C.technical_chart(px["QQQ"], "QQQ  ·  Nasdaq-100 ETF")}</div>'
            + '<div class="gap"></div><h3>Which buy triggers fired on Friday<span class="sub">with what each has returned since 1993 (SPY) and 1999 (QQQ)</span></h3>'
            + trigger_table(f)
            + '<p class="src">Test 83. Next 5 days is the mean return from the trigger close. 1-in-20 low is the fifth-percentile worst low over those five days. Any day: SPY +0.23%, QQQ +0.26%. Open positions in the swing paper account are on page 9.</p>')
    return page(n, total, "Technicals", body, d)


def books_table(d: dict, tier: str = "AGG") -> str:
    books = [(f"In force, {pd.Period(d['ledger_month']).strftime('%B')}", d["in_force"].title(), d["allocs"][tier]),
             (f"Model, {pd.Period(d['prov_month']).strftime('%B')}", d["prov_quadrant"].title() + " (provisional)", d["prov_allocs"][tier])]
    if d["candidate"]:
        books.append(("Candidate", "25% stay-in (not adopted)", d["candidate"][tier]))
    tick = []
    for _, _, b in books:
        for k in sorted(b, key=lambda k: -b[k]):
            if k not in tick:
                tick.append(k)
    head = "".join(f'<th>{e(a)}<br><span style="text-transform:none;letter-spacing:0;font-weight:400">{e(b)}</span></th>' for a, b, _ in books)
    rows = []
    for k in tick:
        cells = "".join("<td>" + (f"{b[k] * 100:.1f}%{weightbar(b[k])}" if k in b else '<span style="color:var(--muted)">none</span>' + weightbar(0)) + "</td>"
                        for _, _, b in books)
        rows.append(f'<tr><td>{k}<span class="sym" style="font-family:var(--sans)">{ASSET.get(k, "")}</span></td>{cells}</tr>')
    return f'<table class="t tight"><tr><th class="l">Aggressive tier</th>{head}</tr>{"".join(rows)}</table>'


def page_model(d, f, c, n, total):
    dec = (f'<div class="box dec"><h3>Decision for 1 {pd.Period(d["prov_month"]).strftime("%B")}</h3><div class="cols3">{c["decision"]}</div></div>'
           if c.get("decision") else "")
    body = (sec(8, "Regime model", c["model"])
            + '<h3>The two dials<span class="sub">distance from the 10-month line. Above zero is on. The month-end reading sets next month\'s book</span></h3>'
            + f'<div class="fig">{C.classifier_chart(d["classifier"], d["regime_months"], (d["prov_month"], d["prov_quadrant"]), height=3.1)}</div>'
            + '<div class="gap"></div><h3>Books<span class="sub">weights by holding</span></h3>' + books_table(d)
            + '<div class="gap"></div>' + dec)
    return page(n, total, "Regime model", body, d)


def month_table(d: dict, tier: str = "AGG") -> tuple[str, str]:
    px, al = d["px"], d["allocs"][tier]
    base = d["anchors"]["mtd"]
    rows, tot = [], 0.0
    for k, w in sorted(al.items(), key=lambda kv: -kv[1]):
        r = float(px[k].iloc[-1] / px[k][px[k].index <= base].iloc[-1] - 1)
        tot += w * r
        rows.append(f'<tr><td>{k}<span class="sym" style="font-family:var(--sans)">{ASSET.get(k, "")}</span></td><td>{w * 100:.1f}%</td><td>{pct(r)}</td><td>{signed(w * r * 100, 1, " pts")}</td></tr>')
    rows.append(f'<tr class="hl"><td>Aggressive book, month to date</td><td>100%</td><td></td><td class="b">{pct(tot)}</td></tr>')
    note = ""
    for o in d["overrides"]:
        if o.get("ledger_month") == d["ledger_month"] and "exit QQQ" in o.get("override", "") and "QQQ" in al:
            q = px["QQQ"]; day = pd.Timestamp(o["date"])
            r_to = float(q[q.index <= day].iloc[-1] / q[q.index <= base].iloc[-1] - 1)
            r_all = float(q.iloc[-1] / q[q.index <= base].iloc[-1] - 1)
            alt = tot - al["QQQ"] * (r_all - r_to)
            note = (f"With QQQ sold at the {day:%-d %b} close and held as cash, the same book is {pct(alt)} month to date. "
                    f"The exit is worth {signed((alt - tot) * 100, 1)} points so far.")
    tbl = ('<table class="t tight"><tr><th class="l">Holding</th><th>Weight</th><th>Month to date</th><th>Contribution</th></tr>' + "".join(rows) + "</table>")
    return tbl, note


def page_paper(d, f, c, n, total):
    mt = d["mtm"]
    lab = {"CONS": "Conservative", "MOD": "Moderate", "AGG": "Aggressive", "VAGG": "Very aggressive", "SPY (bench)": "S&P 500"}
    rows = "".join(f'<tr><td>{lab.get(r.tier, r.tier)}</td><td>{pct(r.ret)}</td><td>{pct(r.maxDD)}</td></tr>' for r in mt.itertuples())
    since = pd.Timestamp(mt["since"].iloc[0])
    mtm = f'<table class="t tight"><tr><th class="l">Since {since:%-d %b %Y}</th><th>Return</th><th>Worst drawdown</th></tr>{rows}</table>'
    mtbl, note = month_table(d)
    ov = ""
    for o in d["overrides"][-1:]:
        ov += (f'<div><p><b>{pd.Timestamp(o["date"]):%-d %b}: {e(o["override"][:1].upper() + o["override"][1:])}.</b></p></div>'
               f'<div><p><b>Reason given.</b> {e(o["user_reason"][:1].upper() + o["user_reason"][1:])}.</p>'
               f'<p><b>Status.</b> {e(o["status"][:1].upper() + o["status"][1:])}. Re-entry: {e(o["re_entry_rule"])}.</p></div>')
        ov += f"<div><p><b>Effect so far.</b> {note}</p></div>" if note else "<div></div>"
    ov_box = f'<div class="box"><h3>Your overrides on file</h3><div class="cols3">{ov}</div></div>' if ov else ""
    ag = float(mt.loc[mt["tier"] == "AGG", "ret"].iloc[0]); sp = float(mt.loc[mt["tier"].str.startswith("SPY"), "ret"].iloc[0])
    lede = c.get("paper") or (f"Since the paper books went live on {since:%-d %B}, the Aggressive tier has returned {pct(ag)} against {pct(sp)} for the S&P 500. "
                              "These are model books marked at the close, with no costs.")
    body = (sec(9, "Paper portfolios and overrides", lede)
            + '<h3>Model books since go-live<span class="sub">four risk tiers and the S&P 500, cumulative return</span></h3>'
            + f'<div class="fig">{C.paper_chart(d["curves"])}</div>'
            + '<div class="gap"></div><div class="cols2" style="grid-template-columns:4.0in minmax(0,1fr);align-items:start">'
            + f'<div><h3>This month, holding by holding<span class="sub">{d["in_force"].title()} book, Aggressive tier</span></h3>{mtbl}</div>'
            + f'<div><h3>All tiers</h3>{mtm}<p class="src">Live tier: Aggressive. Marked daily at the close, no costs or taxes.</p></div></div>'
            + '<div class="gap"></div>' + ov_box
            + '<div class="gap"></div>' + swing_box(d, f))
    return page(n, total, "Paper portfolios", body, d)


def page_method(d, f, c, n, total):
    body = (sec(10, "Method and limits", "What each signal is, what has been tested, and what this report cannot tell you.")
            + f'''<div class="cols2 method"><div>
<h3>Quadrant balances</h3>
<p><b>Cycle</b> is the 5-bar simple average of the close minus the 15-bar average. <b>Trend</b> is a Coppock curve: a 10-bar weighted average of the 14-bar and 11-bar rates of change. Each is computed on daily, weekly and monthly bars. The current week and month count as bars in progress.</p>
<p>Quadrant 1 is below zero and rising. Quadrant 2 is above zero and rising. Quadrant 3 is above zero and falling. Quadrant 4 is below zero and falling. The names Recovering, Advancing, Rolling over and Declining are this report's labels.</p>
<p>Member balances are the share of {d["n_members"]} current S&P 500 members in each quadrant. The formulas were recovered from a desk workbook and reproduce its 18 index codes exactly and its 24 member values within 0.4 points.</p>
<h3>The flag</h3>
<p><b>Intact</b>: both S&P 500 monthly readings above zero. <b>Deteriorating</b>: one below. <b>Broken</b>: both below. <b>Washout</b>: 50% or more of members in a monthly cycle decline. The weekly stage is Early through week 3 of a decline and Mature from week 4.</p>
<p>The monthly readings are slow. They will read Intact through any ordinary correction and through the first months of a real bear market. March 2020 began with the flag intact.</p>
<h3>Regime model</h3>
<p>Two dials set one of four regimes each month. Growth is on when SPY closes the month above the average of its prior nine month-end closes. Inflation is on when the commodity fund DBC does the same. Each regime maps to a fixed book per risk tier (matrix v9). Books change only at month-end.</p>
</div><div>
<h3>What is adopted and what is not</h3>
<ul><li><b>Adopted and held:</b> the regime model and its monthly books.</li>
<li><b>Candidate, your decision:</b> the 25% stay-in. When growth is off but the flag is intact, hold 25% of the growth-on book. It raised return and Sortino in all eight tier and era cells and cost one point of drawdown in the modern era. That is a near miss under the house rule, so it is not adopted.</li>
<li><b>Paper only:</b> the swing account on SPY and QQQ.</li>
<li><b>Informational:</b> quadrant balances, buy triggers, commodity stretch reads. They do not trade.</li></ul>
<h3>Evidence standard</h3>
<p>Every figure quoted as history comes from the research log and is shown for two separate eras, 1987-2006 and 2007-2026, wherever the data allow. A rule is adopted only if every metric improves in both.</p>
<h3>Limits</h3>
<ul><li>Member history uses today's index constituents. Past breadth is survivorship-biased.</li>
<li>Forward-return tables are averages over few episodes. The washout row rests on 20 months.</li>
<li>Paper results ignore costs, taxes and slippage. Leveraged funds decay in choppy markets.</li>
<li>Prices are end-of-day from Yahoo Finance and can be revised. Futures are front-month continuous contracts.</li>
<li>Narrative text is written from the tables on these pages. Where it interprets, it says so.</li></ul>
<h3>Disclosure</h3>
<p>This report is produced for the personal use of one account holder. It is not investment advice, a solicitation, or a recommendation to any other person. Past results do not guarantee future results.</p>
<p class="src">Data through the close of {d["asof"]:%A %-d %B %Y}. Built {pd.Timestamp.now(tz="UTC"):%Y-%m-%d %H:%M} UTC.</p>
</div></div>
<div class="gap"></div><h3>Signal register</h3>
<table class="t tight"><tr><th class="l">Signal</th><th class="l">Question it answers</th><th class="l">Status</th><th class="l">Pages</th><th>Research log</th></tr>
<tr><td>Regime model</td><td class="l">Which book to hold next month</td><td class="l b">Adopted, traded</td><td class="l">8, 9</td><td>matrix v9</td></tr>
<tr><td>Quadrant balances flag</td><td class="l">Is the long cycle intact, breaking or washed out</td><td class="l">Informational</td><td class="l">1, 2, 3</td><td>tests 84, 85</td></tr>
<tr><td>Weekly stage</td><td class="l">Is a weekly decline young or mature</td><td class="l">Informational</td><td class="l">1, 3</td><td>test 84</td></tr>
<tr><td>25% stay-in</td><td class="l">Keep some growth exposure when the model exits and the flag is intact</td><td class="l">Candidate</td><td class="l">8</td><td>test 85</td></tr>
<tr><td>Closing buy triggers</td><td class="l">Is a bounce likely over the next week</td><td class="l">Paper account</td><td class="l">7, 9</td><td>tests 79, 83</td></tr>
<tr><td>Commodity stretch</td><td class="l">Has a real asset sold off hard while still in an uptrend</td><td class="l">Informational</td><td class="l">6</td><td>test 81</td></tr>
</table>''')
    return page(n, total, "Method", body, d)


def font_css() -> str:
    def face(fam, file, weight, style="normal"):
        fmt = "opentype" if file.endswith(".otf") else "truetype"
        return (f'@font-face{{font-family:"{fam}";src:url("file://{FONTS / file}") format("{fmt}");'
                f'font-weight:{weight};font-style:{style};}}')
    return "\n".join([
        face("Fraunces", "Fraunces-VF.ttf", "100 900"), face("Fraunces", "Fraunces-Italic-VF.ttf", "100 900", "italic"),
        face("Inter", "Inter-Regular.otf", 400), face("Inter", "Inter-Medium.otf", 500),
        face("Inter", "Inter-SemiBold.otf", 600), face("Inter", "Inter-Bold.otf", 700),
        face("JetBrains Mono", "JetBrainsMono-Regular.ttf", 400), face("JetBrains Mono", "JetBrainsMono-Medium.ttf", 500),
    ])


def build(d: dict) -> Path:
    f = facts(d)
    c = load_commentary(d, f)
    makers = [page_qb, page_nasdaq, page_equities, page_macro, page_commodities, page_technicals, page_model, page_paper, page_method]
    total = len(makers) + 1
    pages = [cover(d, f, c, total)] + [m(d, f, c, i + 2, total) for i, m in enumerate(makers)]
    css = (ROOT / "report" / "quadrant_weekly.css").read_text()
    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Quadrant Weekly, {d["asof"]:%-d %B %Y}</title>'
           f"<style>{font_css()}\n{css}</style></head><body>{''.join(pages)}</body></html>")
    BUILD.mkdir(parents=True, exist_ok=True)
    hp = BUILD / "report.html"
    hp.write_text(doc)
    pdf = OUT / f"Quadrant_Weekly_{d['asof'].date()}.pdf"
    out = subprocess.run(["node", str(ROOT / "src" / "report" / "render.js"), str(hp), str(pdf)], check=True,
                         capture_output=True, text=True).stdout.strip()
    if out:
        print(out)       # OVERFLOW lines: shorten that page's commentary and rebuild
    return pdf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cached", action="store_true", help="reuse the last gathered data")
    a = ap.parse_args()
    pk = D.CACHE / "report_data.pkl"
    if a.cached and pk.exists():
        d = pickle.load(open(pk, "rb"))
    else:
        d = D.gather()
        pickle.dump(d, open(pk, "wb"))
    print(build(d))


if __name__ == "__main__":
    main()
