"""Charts for the weekly report. Every function returns an inline SVG string.

House rules: one y-scale per plot; thin marks; hairline solid grids; text in
ink, never in a series colour; a legend whenever two or more series share a
plot; direct labels only at endpoints.
"""
from __future__ import annotations

import io
import itertools
import re

import matplotlib

matplotlib.use("svg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from src.portfolio import trend_cycle as tc  # noqa: E402
from src.report import style as S  # noqa: E402

_counter = itertools.count(1)
_FONTS = __import__("pathlib").Path(__file__).resolve().parents[2] / "report" / "fonts"
for _f in sorted(_FONTS.glob("Inter-*.otf")) + sorted(_FONTS.glob("JetBrainsMono-*.ttf")):
    matplotlib.font_manager.fontManager.addfont(str(_f))
MONO = ["JetBrains Mono", "DejaVu Sans Mono"]

plt.rcParams.update({
    "font.family": ["Inter", "DejaVu Sans"], "font.size": 7.2, "svg.fonttype": "none",
    "axes.edgecolor": S.HAIR, "axes.linewidth": 0.6, "axes.labelcolor": S.INK2,
    "xtick.color": S.MUTED, "ytick.color": S.MUTED, "xtick.labelsize": 6.6, "ytick.labelsize": 6.6,
    "xtick.major.size": 0, "ytick.major.size": 0, "xtick.major.pad": 3, "ytick.major.pad": 3,
    "axes.grid": False, "grid.color": S.GRID, "grid.linewidth": 0.6,
    "figure.facecolor": "none", "axes.facecolor": "none", "savefig.facecolor": "none",
    "lines.solid_capstyle": "round", "lines.solid_joinstyle": "round",
})


def svg(fig) -> str:
    plt.rcParams["svg.hashsalt"] = f"qw{next(_counter)}"
    buf = io.StringIO()
    fig.savefig(buf, format="svg", transparent=True)
    plt.close(fig)
    out = buf.getvalue()
    out = out[out.index("<svg"):]
    out = re.sub(r'\swidth="[\d.]+pt"\sheight="[\d.]+pt"', ' width="100%"', out, count=1)
    return out


def clean(ax, grid="y", right=True):
    for s in ("top", "left", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(S.HAIR)
    if grid:
        ax.grid(axis=grid, color=S.GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    if right:
        ax.yaxis.tick_right()
    ax.tick_params(length=0)


def time_ticks(ax, index: pd.DatetimeIndex, mode: str):
    """Integer x positions; ticks at period starts with compact labels."""
    pos, lab = [], []
    if mode == "month":
        for i in range(1, len(index)):
            if index[i].month != index[i - 1].month:
                pos.append(i); lab.append(index[i].strftime("%b") if index[i].month != 1 else index[i].strftime("%b\n%Y"))
    elif mode == "quarter":
        for i in range(1, len(index)):
            if index[i].month != index[i - 1].month and index[i].month in (1, 4, 7, 10):
                pos.append(i); lab.append(index[i].strftime("%b") if index[i].month != 1 else index[i].strftime("%Y"))
    elif mode == "half":
        for i in range(1, len(index)):
            if index[i].month != index[i - 1].month and index[i].month in (1, 7):
                pos.append(i); lab.append("Jul" if index[i].month == 7 else index[i].strftime("%Y"))
    elif mode == "year":
        for i in range(1, len(index)):
            if index[i].year != index[i - 1].year:
                pos.append(i); lab.append(index[i].strftime("%Y"))
    elif mode == "2year":
        for i in range(1, len(index)):
            if index[i].year != index[i - 1].year and index[i].year % 2 == 0:
                pos.append(i); lab.append(index[i].strftime("%Y"))
    ax.set_xticks(pos); ax.set_xticklabels(lab)
    ax.set_xlim(-0.5, len(index) - 0.5)


def end_tag(ax, x, y, text, dx=4):
    ax.annotate(text, (x, y), xytext=(dx, 0), textcoords="offset points", va="center", ha="left",
                fontsize=6.8, color=S.INK, fontweight="semibold", annotation_clip=False)
    ax.plot([x], [y], marker="o", ms=3.6, color=S.INK, mec="white", mew=0.9, zorder=5, clip_on=False)


def ribbon(ax, q: np.ndarray, label: str, code: str):
    """A strip of cells coloured by quadrant; consecutive equal states merge into one block."""
    ax.set_ylim(0, 1); ax.set_xlim(-0.5, len(q) - 0.5)
    start = 0
    for i in range(1, len(q) + 1):
        if i == len(q) or q[i] != q[start]:
            if not np.isnan(q[start]):
                ax.add_patch(Rectangle((start - 0.5, 0.08), i - start, 0.84, facecolor=S.Q[int(q[start])],
                                       edgecolor="white", linewidth=0.5))
            start = i
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])
    ax.text(-0.012, 0.5, label, transform=ax.transAxes, ha="right", va="center", fontsize=6.4, color=S.INK2)
    ax.text(1.012, 0.5, code, transform=ax.transAxes, ha="left", va="center", fontsize=6.6, color=S.INK,
            family=MONO)


def fmt_code(st) -> str:
    return f"{st.quadrant}-{st.in_quadrant:02d}-{st.on_side:02d}"


WINDOW = {"D": 170, "W": 150, "M": 168}
TICKS = {"D": "month", "W": "half", "M": "2year"}


def _spread(ys: list[float], gap: float, lo: float, hi: float) -> list[float]:
    """Nudge label positions apart so none sit closer than `gap` (keeps order)."""
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    out = list(ys)
    prev = lo - gap
    for i in order:
        out[i] = max(out[i], prev + gap); prev = out[i]
    over = out[order[-1]] - hi
    if over > 0:
        prev = hi + gap
        for i in reversed(order):
            out[i] = min(out[i], prev - gap); prev = out[i]
    return out


def stacked_balance(ax, hist: pd.DataFrame, prefix: str, title: str):
    """100% stacked area: below-zero quadrants at the bottom (declining, recovering), above-zero on top."""
    order = [4, 1, 2, 3]
    x = np.arange(len(hist))
    ys = [hist[f"{prefix}_q{q}"].values for q in order]
    ax.stackplot(x, ys, colors=[S.Q[q] for q in order], edgecolor="white", linewidth=0.35)
    ax.set_ylim(0, 100); ax.set_yticks([0, 50, 100]); ax.set_yticklabels(["0", "50", "100%"])
    clean(ax, grid=None, right=False)
    ax.spines["bottom"].set_visible(False)
    ax.text(0, 1.045, title, transform=ax.transAxes, fontsize=6.6, color=S.INK2, ha="left", va="bottom")
    mids, base = [], 0.0
    for y in ys:
        v = float(y[-1]); mids.append(base + v / 2); base += v
    pos = _spread(mids, 15.5, 6, 94)
    for q, y, yy in zip(order, ys, pos):
        ax.plot([1.022], [yy / 100], marker="s", ms=4.2, color=S.Q[q], transform=ax.transAxes, clip_on=False)
        ax.text(1.05, yy / 100, f"{float(y[-1]):.0f}%", transform=ax.transAxes, ha="left", va="center",
                fontsize=6.5, color=S.INK, fontweight="medium")


def qb_row(close: pd.Series, hist: pd.DataFrame | None, tf: str, name: str, with_balances: bool = True,
           bars_override: pd.Series | None = None, height: float | None = None) -> str:
    """One bar size: price with the two state ribbons, and (optionally) the member balances."""
    bars_ = bars_override if bars_override is not None else tc.to_bars(close, tf)
    n = WINDOW[tf]
    qc = tc.quadrants(tc.cycle(bars_)); qt = tc.quadrants(tc.trend(bars_))
    px = bars_.iloc[-n:]
    idx = px.index
    h = height or (2.3 if with_balances else 1.7)
    fig = plt.figure(figsize=(7.3, h))
    outer = fig.add_gridspec(1, 2 if with_balances else 1, width_ratios=[1.3, 1] if with_balances else [1],
                             wspace=0.33, left=0.062, right=0.945 if with_balances else 0.925, top=1 - 0.19 / h, bottom=0.25 / h)
    rib = 0.105 / max(h - 0.44 - 0.21, 0.3)          # each ribbon about a tenth of an inch tall at any figure height
    left = outer[0].subgridspec(3, 1, height_ratios=[1, rib, rib], hspace=0.07)
    ax = fig.add_subplot(left[0])
    x = np.arange(len(px))
    ax.plot(x, px.values, color=S.INK, linewidth=1.25)
    ma_n = {"D": 50, "W": 40, "M": 10}[tf]
    ma = bars_.rolling(ma_n).mean().iloc[-n:]
    ax.plot(x, ma.values, color=S.REF, linewidth=0.9)
    clean(ax)
    lo, hi = float(np.nanmin(px.values)), float(np.nanmax(px.values))
    ax.set_ylim(lo - (hi - lo) * 0.06, hi + (hi - lo) * 0.10)
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xticks([]); ax.set_xlim(-0.5, len(px) - 0.5)
    ax.plot([x[-1]], [px.values[-1]], marker="o", ms=3.8, color=S.INK, mec="white", mew=0.9, zorder=5, clip_on=False)
    ax.text(0, 1.045, f"{name}\u2002{px.values[-1]:,.0f}", transform=ax.transAxes, fontsize=6.8, color=S.INK, fontweight="semibold", ha="left", va="bottom")
    ax.plot([0.985, 1.0], [1.085, 1.085], color=S.REF, linewidth=0.9, transform=ax.transAxes, clip_on=False)
    ax.text(0.978, 1.085, f"{ma_n}-{S.UNIT[tf]} average", transform=ax.transAxes, fontsize=6.2, color=S.INK2, ha="right", va="center")
    # signals: the trend oscillator crossing its zero line (up = advance begins, down = decline begins)
    t_osc = tc.trend(bars_)
    side = (t_osc > 0).astype(float).where(t_osc.notna())
    flip = side.diff().reindex(idx)
    off = (hi - lo) * 0.075
    ups = np.where(flip.values == 1)[0]; dns = np.where(flip.values == -1)[0]
    ax.plot(ups, px.values[ups] - off, linestyle="none", marker="^", ms=4.6, color=S.Q[2], mec="white", mew=0.6, zorder=6)
    ax.plot(dns, px.values[dns] + off, linestyle="none", marker="v", ms=4.6, color=S.Q[4], mec="white", mew=0.6, zorder=6)
    ax_t = fig.add_subplot(left[1]); ribbon(ax_t, qt.reindex(idx).values, "Trend", "")
    ax_c = fig.add_subplot(left[2]); ribbon(ax_c, qc.reindex(idx).values, "Cycle", "")
    time_ticks(ax_c, idx, TICKS[tf]); ax_c.tick_params(axis="x", pad=2)
    if with_balances:
        h = hist.reindex(idx).ffill()
        right = outer[1].subgridspec(2, 1, hspace=0.42)
        a1 = fig.add_subplot(right[0]); stacked_balance(a1, h, "cyc", "S&P 500 members by cycle quadrant")
        a1.set_xticks([]); a1.set_xlim(-0.5, len(h) - 0.5)
        a2 = fig.add_subplot(right[1]); stacked_balance(a2, h, "trd", "S&P 500 members by trend quadrant")
        time_ticks(a2, idx, TICKS[tf])
    return svg(fig)


def quadrant_key() -> str:
    """How to read: one oscillator swing, coloured by the quadrant it is in."""
    fig, ax = plt.subplots(figsize=(3.5, 1.22))
    fig.subplots_adjust(left=0.0, right=1.0, top=1.0, bottom=0.0)
    t = np.linspace(-np.pi / 2, 3 * np.pi / 2, 400)
    y = np.sin(t)
    for q, m in ((1, t < 0), (2, (t >= 0) & (t < np.pi / 2)), (3, (t >= np.pi / 2) & (t < np.pi)), (4, t >= np.pi)):
        ax.plot(t[m], y[m], color=S.Q[q], linewidth=2.8, solid_capstyle="butt")
    ax.plot([t[0] - 1.5, t[-1] + 1.5], [0, 0], color=S.REF, linewidth=0.7, zorder=0)
    ax.text(t[-1] + 1.5, 0.09, "zero line", fontsize=5.8, color=S.MUTED, ha="right", va="bottom")
    lab = {1: (-np.pi / 2, -1, "center"), 2: (np.pi / 2 - 0.22, 1, "right"), 3: (np.pi / 2 + 0.22, 1, "left"), 4: (3 * np.pi / 2, -1, "center")}
    for q, (xx, sgn, ha) in lab.items():
        ax.text(xx, sgn * 2.02, f"{q}  {S.Q_NAME[q]}", fontsize=6.9, color=S.INK, fontweight="semibold", ha=ha, va="center")
        ax.text(xx, sgn * 1.5, S.Q_DESC[q], fontsize=6.1, color=S.INK2, ha=ha, va="center")
    ax.plot([0], [0], marker="^", ms=5, color=S.Q[2], mec="white", mew=0.6, zorder=6)
    ax.plot([np.pi], [0], marker="v", ms=5, color=S.Q[4], mec="white", mew=0.6, zorder=6)
    ax.set_xlim(t[0] - 1.6, t[-1] + 1.6); ax.set_ylim(-2.45, 2.45); ax.axis("off")
    return svg(fig)


def _axis_fmt(kind: str):
    if kind == "pp":
        return lambda v, _: f"{v:+.2f}"
    if kind == "yield":
        return lambda v, _: f"{v:.2f}%"
    if kind == "pct":
        return lambda v, _: f"{v:+.0f}%"
    if kind == "small":
        return lambda v, _: f"{v:,.2f}"
    return lambda v, _: f"{v:,.0f}"


def small_multiples(items: list[dict], ncols: int = 3, n: int = 252, row_h: float = 1.52, width: float = 7.3) -> str:
    """Grid of one-series line charts. item: {title, series, kind, sub, ma (optional int), band (optional)}"""
    nrows = int(np.ceil(len(items) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(width, row_h * nrows), squeeze=False)
    fig.subplots_adjust(left=0.012, right=0.945, top=1 - 0.36 / (row_h * nrows), bottom=0.2 / (row_h * nrows), wspace=0.36, hspace=0.36 / (row_h - 0.56) + 0.2)
    for ax, it in zip(axes.flat, items):
        full = it["series"].dropna()
        s_ = full.iloc[-n:]
        x = np.arange(len(s_))
        if it.get("ma"):
            ma = full.rolling(it["ma"]).mean().iloc[-n:]
            ax.plot(x, ma.values, color=S.REF, linewidth=0.9)
        ax.plot(x, s_.values, color=S.INK, linewidth=1.15)
        clean(ax)
        lo, hi = float(s_.min()), float(s_.max())
        ax.set_ylim(lo - (hi - lo) * 0.08, hi + (hi - lo) * 0.12)
        ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(3))
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(_axis_fmt(it.get("kind", "price"))))
        time_ticks(ax, s_.index, "quarter")
        ax.plot([x[-1]], [s_.values[-1]], marker="o", ms=3.4, color=S.INK, mec="white", mew=0.8, zorder=5, clip_on=False)
        ax.text(0, 1.2, it["title"], transform=ax.transAxes, fontsize=7.0, color=S.INK, fontweight="semibold", ha="left", va="bottom")
        ax.text(0, 1.05, it.get("sub", ""), transform=ax.transAxes, fontsize=6.3, color=S.INK2, ha="left", va="bottom")
    for ax in list(axes.flat)[len(items):]:
        ax.axis("off")
    return svg(fig)


def ranked_bars(rows: list[tuple[str, float]], width: float = 3.45, row_h: float = 0.2, fmt="{:+.1f}%") -> str:
    """Horizontal bars from a zero baseline, one neutral colour (the categories are nominal)."""
    rows = sorted(rows, key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(width, row_h * len(rows) + 0.25))
    fig.subplots_adjust(left=0.34, right=0.86, top=0.99, bottom=0.03)
    y = np.arange(len(rows)); v = np.array([r[1] * 100 for r in rows])
    ax.barh(y, v, height=0.52, color=S.INK, linewidth=0)
    ax.axvline(0, color=S.INK2, linewidth=0.6)
    span = max(abs(v.min()), abs(v.max()), 1e-9)
    ax.set_xlim(min(v.min(), 0) - span * 0.02, max(v.max(), 0) + span * 0.02)
    for yy, vv in zip(y, v):
        ax.annotate(fmt.format(vv), (vv, yy), xytext=(-4 if vv < 0 else 4, 0), textcoords="offset points",
                    ha="right" if vv < 0 else "left", va="center", fontsize=6.6, color=S.INK)
    ax.set_yticks(y); ax.set_yticklabels([r[0] for r in rows], fontsize=6.9, color=S.INK)
    ax.tick_params(axis="y", pad=3 + (span and 26))
    ax.set_xticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    return svg(fig)


def stage_chart(now_stage: int | None) -> str:
    """S&P 500 return over the next 13 weeks, by week of a weekly trend decline (entry 84)."""
    labels = ["week 1", "week 2", "week 3", "weeks 4-5", "weeks 6-8"]
    old = [1.0, 1.3, 1.4, 5.3, 5.6]; mod = [1.2, 4.5, 5.6, 4.0, 2.5]
    fig, ax = plt.subplots(figsize=(3.3, 1.5))
    fig.subplots_adjust(left=0.02, right=0.9, top=0.8, bottom=0.15)
    x = np.arange(len(labels)); w = 0.3
    ax.bar(x - w / 2 - 0.02, old, w, color=S.REF, linewidth=0)
    ax.bar(x + w / 2 + 0.02, mod, w, color=S.INK, linewidth=0)
    ax.axhline(2.4, color=S.INK2, linewidth=0.7, linestyle=(0, (3, 2)))

    clean(ax); ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=6.6, color=S.INK2)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.0f}%")); ax.set_ylim(0, 6.6)
    ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(2))
    ax.plot([0.0], [1.115], marker="s", ms=4.5, color=S.REF, transform=ax.transAxes, clip_on=False)
    ax.text(0.03, 1.115, "1987-2006", transform=ax.transAxes, fontsize=6.4, color=S.INK2, va="center")
    ax.plot([0.25], [1.115], marker="s", ms=4.5, color=S.INK, transform=ax.transAxes, clip_on=False)
    ax.text(0.28, 1.115, "2007-2026", transform=ax.transAxes, fontsize=6.4, color=S.INK2, va="center")
    ax.plot([0.5, 0.55], [1.115, 1.115], color=S.INK2, linewidth=0.7, linestyle=(0, (3, 2)), transform=ax.transAxes, clip_on=False)
    ax.text(0.57, 1.115, "any week, +2.3% / +2.5%", transform=ax.transAxes, fontsize=6.4, color=S.INK2, va="center")
    if now_stage is not None:
        k = 0 if now_stage <= 1 else 1 if now_stage == 2 else 2 if now_stage == 3 else 3 if now_stage <= 5 else 4
        ax.annotate("now", (k, max(old[k], mod[k]) + 0.25), xytext=(0, 13), textcoords="offset points", ha="center", fontsize=6.6,
                    color=S.INK, fontweight="semibold", arrowprops=dict(arrowstyle="-|>", color=S.INK, lw=0.8, shrinkA=1, shrinkB=1))
    return svg(fig)


def technical_chart(close: pd.Series, name: str, n: int = 150) -> str:
    """Price with Bollinger(20,2) band, 200-day average, and a marker on every close below the lower band; RSI(2) beneath."""
    mid = close.rolling(20).mean(); sd = close.rolling(20).std(ddof=0)
    up, lo = mid + 2 * sd, mid - 2 * sd
    ma200 = close.rolling(200).mean()
    d = close.diff()
    u = d.clip(lower=0).ewm(alpha=0.5, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
    rsi2 = 100 - 100 / (1 + u / dn.replace(0, np.nan))
    c = close.iloc[-n:]; idx = c.index; x = np.arange(len(c))
    fig = plt.figure(figsize=(7.3, 2.62))
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 0.26], hspace=0.1, left=0.012, right=0.925, top=0.855, bottom=0.1)
    ax = fig.add_subplot(gs[0])
    ax.fill_between(x, lo.reindex(idx).values, up.reindex(idx).values, color=S.Q[1], alpha=0.10, linewidth=0)
    ax.plot(x, mid.reindex(idx).values, color=S.Q[1], linewidth=0.8, alpha=0.7)
    ax.plot(x, ma200.reindex(idx).values, color=S.REF, linewidth=1.0)
    ax.plot(x, c.values, color=S.INK, linewidth=1.25)
    below = (c < lo.reindex(idx)).values
    ax.plot(x[below], c.values[below], linestyle="none", marker="o", ms=4.4, color=S.Q[4], mec="white", mew=0.9, zorder=6)
    clean(ax); ax.set_xticks([]); ax.set_xlim(-0.5, len(c) - 0.5)
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.plot([x[-1]], [c.values[-1]], marker="o", ms=3.8, color=S.INK if not below[-1] else S.Q[4], mec="white", mew=0.9, zorder=7, clip_on=False)
    ax.text(0, 1.155, f"{name}\u2002{c.values[-1]:,.2f}", transform=ax.transAxes, fontsize=7.2, color=S.INK, fontweight="semibold", ha="left", va="bottom")
    # legend
    lx = 0.0
    for kind, lab in (("line", "price"), ("band", "Bollinger band (20-day, 2 SD)"), ("ref", "200-day average"), ("dot", "close below the lower band = buy trigger")):
        if kind == "line":
            ax.plot([lx, lx + 0.022], [1.075, 1.075], color=S.INK, linewidth=1.25, transform=ax.transAxes, clip_on=False)
        elif kind == "band":
            ax.add_patch(Rectangle((lx, 1.052), 0.022, 0.046, transform=ax.transAxes, facecolor=S.Q[1], alpha=0.18, linewidth=0, clip_on=False))
        elif kind == "ref":
            ax.plot([lx, lx + 0.022], [1.075, 1.075], color=S.REF, linewidth=1.0, transform=ax.transAxes, clip_on=False)
        else:
            ax.plot([lx + 0.011], [1.075], marker="o", ms=4.2, color=S.Q[4], mec="white", mew=0.8, transform=ax.transAxes, clip_on=False)
        ax.text(lx + 0.03, 1.075, lab, transform=ax.transAxes, fontsize=6.2, color=S.INK2, va="center")
        lx += 0.03 + 0.0078 * len(lab) + 0.03
    ax2 = fig.add_subplot(gs[1])
    r = rsi2.reindex(idx).values
    ax2.bar(x, r, width=0.72, color=np.where(r < 10, S.Q[4], S.REF), linewidth=0)
    ax2.axhline(10, color=S.INK2, linewidth=0.6)
    clean(ax2, grid=None); ax2.set_ylim(0, 100); ax2.set_yticks([10, 50, 90])
    time_ticks(ax2, idx, "month")
    ax2.text(0, 1.06, "2-day RSI (red below 10)", transform=ax2.transAxes, fontsize=6.2, color=S.INK2, ha="left", va="bottom")
    return svg(fig)


def classifier_chart(cl: pd.DataFrame, months: list[tuple[str, str]], prov: tuple[str, str] | None, n: int = 380, height: float = 2.25) -> str:
    """The regime model's two dials: distance of the S&P 500 and of commodities from their 10-month lines."""
    c = cl.iloc[-n:] * 100; idx = c.index; x = np.arange(len(c))
    fig = plt.figure(figsize=(7.3, height))
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 0.2 / (height - 0.7)], hspace=0.12, left=0.012, right=0.9, top=1 - 0.27 / height, bottom=0.25 / height)
    ax = fig.add_subplot(gs[0])
    ly = 1 + 0.13 / (height - 0.95)        # legend row a fixed distance above the plot
    ax.axhline(0, color=S.INK2, linewidth=0.7)
    ax.plot(x, c["spy"].values, color=S.INK, linewidth=1.25)
    ax.plot(x, c["dbc"].values, color=S.Q[3], linewidth=1.25)
    clean(ax); ax.set_xticks([]); ax.set_xlim(-0.5, len(c) - 0.5)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.0f}%"))
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(5))
    ends = _spread([float(c["spy"].iloc[-1]), float(c["dbc"].iloc[-1])], (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.1, *ax.get_ylim())
    for col, lab, yy, colr in (("spy", "S&P 500", ends[0], S.INK), ("dbc", "Commodities", ends[1], S.Q[3])):
        ax.plot([x[-1]], [c[col].iloc[-1]], marker="o", ms=3.6, color=colr, mec="white", mew=0.8, zorder=5, clip_on=False)
    ax.plot([0.0, 0.022], [ly, ly], color=S.INK, linewidth=1.25, transform=ax.transAxes, clip_on=False)
    ax.text(0.03, ly, f"S&P 500 vs its 10-month line ({c['spy'].iloc[-1]:+.1f}%): the growth dial", transform=ax.transAxes, fontsize=6.4, color=S.INK2, va="center")
    ax.plot([0.5, 0.522], [ly, ly], color=S.Q[3], linewidth=1.25, transform=ax.transAxes, clip_on=False)
    ax.text(0.53, ly, f"Commodities vs their 10-month line ({c['dbc'].iloc[-1]:+.1f}%): the inflation dial", transform=ax.transAxes, fontsize=6.4, color=S.INK2, va="center")
    # regime strip: the regime in force each month (set by the dials at the prior month-end); equal runs merged
    ax2 = fig.add_subplot(gs[1]); ax2.set_xlim(-0.5, len(c) - 0.5); ax2.set_ylim(0, 1)
    full = cl.copy(); me = full.groupby(full.index.to_period("M")).last()
    names = {(True, True): "Reflation", (True, False): "Growth", (False, True): "Stagflation", (False, False): "Deflation"}
    derived = {str(p + 1): names[(bool(r.spy > 0), bool(r.dbc > 0))] for p, r in me.iloc[:-1].iterrows()}
    derived.update({m: q.title() for m, q in months})
    per = idx.to_period("M")
    bounds = [0] + [i for i in range(1, len(idx)) if per[i] != per[i - 1]] + [len(idx)]
    runs = []
    for a_, b_ in zip(bounds[:-1], bounds[1:]):
        nm = derived.get(str(per[a_]), "")
        if runs and runs[-1][2] == nm:
            runs[-1][1] = b_
        else:
            runs.append([a_, b_, nm])
        ax2.text((a_ + b_ - 1) / 2, -0.4, per[a_].strftime("%b") if per[a_].month != 1 else per[a_].strftime("%Y"),
                 ha="center", va="top", fontsize=6.2, color=S.MUTED) if b_ - a_ > 9 else None
    for a_, b_, nm in runs:
        ax2.add_patch(Rectangle((a_ - 0.5, 0.05), b_ - a_, 0.9, facecolor="#eceae3", edgecolor="white", linewidth=1.4))
        if nm and b_ - a_ > 16:
            ax2.text((a_ + b_ - 1) / 2, 0.5, nm, ha="center", va="center", fontsize=6.0, color=S.INK2)
    ax2.axis("off")
    ax2.text(-0.004, 0.5, "", transform=ax2.transAxes)
    return svg(fig)
