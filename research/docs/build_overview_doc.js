// Rebuilds InvestmentSystemOverview.docx (plain-English overview). Run: node research/docs/build_overview_doc.js
// Numbers: research/evidence_current.json (matrix v9). Kept in-repo after the original scratchpad copy was lost.
const { Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, AlignmentType, LevelFormat, ShadingType, PageBreak } = require("docx");
const fs = require("fs");
const FONT = "Arial", NAVY = "1F3864", GREY = "595959";
const p = (text, o = {}) => new Paragraph({ spacing: { after: o.after ?? 160 }, ...(o.bullet ? { numbering: { reference: "bullets", level: 0 } } : {}),
  children: [new TextRun({ text, font: FONT, size: o.size ?? 21, bold: !!o.bold, italics: !!o.italics, color: o.color ?? "000000" })] });
const h = (text) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 280, after: 140 }, children: [new TextRun({ text, font: FONT, bold: true, size: 26, color: NAVY })] });
function table(headers, rows, w) {
  const total = w.reduce((a, b) => a + b, 0);
  const cell = (t, { bold = false, shade = null, align = AlignmentType.LEFT } = {}, width) => new TableCell({ width: { size: width, type: WidthType.DXA },
    shading: shade ? { type: ShadingType.CLEAR, fill: shade } : undefined, margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ alignment: align, children: [new TextRun({ text: String(t), font: FONT, size: 19, bold })] })] });
  return new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: w, rows: [
    new TableRow({ children: headers.map((x, i) => cell(x, { bold: true, shade: "D9E2F3", align: i ? AlignmentType.CENTER : AlignmentType.LEFT }, w[i])) }),
    ...rows.map(r => new TableRow({ children: r.map((x, i) => cell(x, { align: i ? AlignmentType.CENTER : AlignmentType.LEFT, bold: i === 0 }, w[i])) })) ] });
}
const spacer = () => new Paragraph({ spacing: { after: 120 }, children: [] });
const doc = new Document({
  numbering: { config: [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 200 } } } }] }] },
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1080, bottom: 1080, left: 1260, right: 1260 } } }, children: [
    new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: "A Season-Based Investment System", font: FONT, size: 34, bold: true, color: NAVY })] }),
    p("Plain-English overview of the research, the rules, and the results  ·  October 2026", { color: GREY, size: 20, after: 240 }),
    h("The conclusion, up front"),
    p("This is a rules-based way of investing that changes what it owns based on the economic “season” the market is in, checked once a month. It is not stock picking and not day trading — it trades about once a month, following written rules, with no predictions and no gut calls. In nearly twenty years of backtesting (2007–2026), the middle-risk version of the system would have earned about 15% per year while never losing more than about 14% from peak to bottom — a period in which the S&P 500 earned about 11% per year and at one point was down 55%. Higher-risk versions earned more with deeper swings. The same rules were then re-tested on a completely separate twenty-year period (1987–2006) that was never used to design them, and held up. The system went live with real money in September 2026, and every month’s decision is logged in advance in a public record that cannot be edited after the fact — so results are graded honestly, going forward, against a benchmark that cannot be fudged."),
    p("Every number in this document is a backtest — a careful simulation of the past — not a promise about the future. Our own planning assumes real results come in at roughly three-quarters of the backtested figures. The risks are listed plainly on the last page; read them before deciding anything.", { italics: true }),
    h("How it works (methodology)"),
    p("The system asks two simple questions on the last day of each month:"),
    p("Is the stock market trending up? (Is the S&P 500 above its own 10-month average price?)", { bullet: true }),
    p("Are commodity prices trending up? (Is a broad basket — oil, metals, crops — above its 10-month average?)", { bullet: true }),
    p("Two yes/no answers give four possible “seasons,” and each season has a pre-decided shopping list:"),
    table(["Season", "What's happening", "What the system owns (middle-risk version)"], [
      ["Growth", "Stocks up, commodities quiet", "Mostly large technology stocks, some bonds"],
      ["Reflation", "Stocks up, commodities up", "Stocks plus energy, gold, and commodities"],
      ["Stagflation", "Stocks down, commodities up", "Mostly cash-like holdings and safe bonds; a small bet against energy stocks"],
      ["Deflation", "Stocks down, commodities down", "Government bonds and gold (gold miners in the aggressive versions); a small bet against oil"] ], [1300, 2700, 5700]),
    spacer(),
    p("That is the whole engine. The month’s season is decided from finished data (no peeking), the matching list is bought, and nothing else happens until the next month-end. Along the way we tested dozens of “improvements” — checking the signals daily or weekly, reacting to news, credit-market warnings, volatility signals, buying dips — and rejected more than thirty of them because they failed a simple honesty test: an idea only counts if it worked in BOTH the modern period (2007–2026) and a separate earlier period (1987–2006). Fifteen ideas passed that bar and are in the system; everything else was written down and discarded. Trading costs and taxes are included in the planning numbers."),
    h("The risk framework"),
    p("There are four versions of the portfolio — same rules, different octane. You choose one based on how large a temporary drop you can genuinely sit through without selling. That choice is the single most important decision, so here is the worst backtested peak-to-bottom drop for each, in dollars, per $10,000 invested:"),
    table(["Version", "Style", "Worst drop (2007–2026)", "On $10,000"], [
      ["Conservative", "No leverage, defense first", "−10%", "−$1,020 at the worst point"],
      ["Moderate", "No leverage", "−14%", "−$1,430"],
      ["Aggressive", "Some leveraged funds", "−33%", "−$3,310"],
      ["Very Aggressive", "Leveraged funds throughout", "−47%", "−$4,680"] ], [1800, 3100, 2600, 2600]),
    spacer(),
    p("Guardrails: no borrowed money and no margin account (the “bets against” oil and energy use ordinary funds, kept small at 5–7% of the portfolio); everything is a large, liquid, exchange-traded fund; the system only trades monthly; and the season signal itself acts as the emergency brake — if markets break down, the next monthly check moves the portfolio into bonds, gold, and cash automatically. A written kill switch can halt all trading instantly."),
    h("The return profile (backtest, Jan 2007–Sep 2026)"),
    table(["", "Return / yr", "Worst drop", "Return per unit of downside*"], [
      ["Conservative", "+9.8%", "−10%", "1.62"], ["Moderate", "+15.4%", "−14%", "1.73"],
      ["Aggressive", "+27.3%", "−33%", "1.41"], ["Very Aggressive", "+35.3%", "−47%", "1.22"],
      ["S&P 500 (buy & hold)", "+11.0%", "−55%", "0.69"], ["Nasdaq 100 (buy & hold)", "+16.4%", "−53%", "0.96"] ], [2600, 2200, 2200, 3100]),
    p("*A standard measure (Sortino ratio): how much return you earn for each unit of downside pain. Higher is better; the point of the table is that every version of the system earned its returns more efficiently than simply holding the index.", { size: 18, color: GREY }),
    p("For planning we do not use these numbers as-is: we assume roughly three-quarters of the backtested return, and we model taxes at short-term rates since the system trades monthly. Even with both haircuts, the compounding case remains strong."),
    h("About the backtest — what's real and what's simulated"),
    p("The 2007–2026 test uses real fund prices wherever the funds existed. Leveraged funds launched around 2010; before that their returns are simulated with a standard method that we validated against the real funds after 2010 (and where the simulation disagreed with reality — one oil fund diverged badly in 2020 — we used the real, worse data). The separate 1987–2006 check uses equivalent older funds. Costs of trading are modeled; the season signal is always computed from completed months only, so the backtest never uses information it wouldn’t have had on the day. Two things a backtest cannot prove: that the future resembles the past, and that the person running it holds on during the ugly months. That second one is why the drop table above is in dollars."),
    h("How it performed in the big moments"),
    table(["Year", "What happened", "S&P 500", "Moderate", "Very Aggressive"], [
      ["2008", "Global financial crisis", "−37%", "+15%", "+44%"],
      ["2020", "COVID crash & rebound", "+18%", "+30%", "+140%"],
      ["2022", "Inflation; stocks AND bonds fell", "−18%", "+1%", "−31%"],
      ["2025", "Strong markets", "+18%", "+30%", "+50%"],
      ["2026 (to Sep)", "Commodity-led rally", "+14%", "+20%", "+33%"] ], [1500, 3100, 1700, 1700, 1700]),
    spacer(),
    p("The pattern to notice: in 2008 the system sat in bonds and gold while the index lost a third — that is the season signal doing its job. 2022 shows the honest limit: when inflation broke stocks and bonds at the same time, the leveraged version still lost 31% (the index lost 18%). The system reduces how often you get hurt; it does not make losing years impossible. And the 2020 leveraged figure (+140%) leans on simulated leverage math and gold miners in a wild year — treat it as the backtest’s best case, not its base case."),
    new Paragraph({ children: [new PageBreak()] }),
    h("The risks, plainly"),
    p("The model can simply stop working. Every rule here is built from history; markets can change. This is the biggest risk and no backtest removes it.", { bullet: true }),
    p("The drops are real. The aggressive versions have backtested drops of 33–47%, and the out-of-sample period showed a 60% drop for the highest tier. If you would sell in a panic partway down, the drop table — not the return table — is your table.", { bullet: true }),
    p("Leveraged funds carry extra risks: daily-reset math erodes them in choppy markets, and a single catastrophic day (a 1987-style crash) would hit the highest tier far harder than any backtest shows.", { bullet: true }),
    p("Taxes: monthly trading means gains are mostly taxed at the higher short-term rate. This is modeled in the planning numbers but it is a real drag versus buy-and-hold.", { bullet: true }),
    p("Key-person risk: this is operated by one person with automation being phased in. If the process stops being followed, the results do not apply.", { bullet: true }),
    p("Not investment advice: this document describes a personal research project and a personal portfolio. It is shared for discussion, not as a recommendation. Past performance — especially simulated past performance — does not guarantee future results. Anyone considering this should only use money they can leave invested for years and can watch drop by the amounts in the risk table without needing it back.", { bullet: true }),
    spacer(),
    p("Verification: every monthly decision since August 2026 is logged, timestamped, in an append-only record before any trade happens, alongside the exact target portfolios for all four risk versions. The live account is graded against that record — so within a few months there will be a track record that requires no trust in backtests at all.", { italics: true, color: GREY }),
  ] }] });
Packer.toBuffer(doc).then(buf => { fs.writeFileSync("InvestmentSystemOverview.docx", buf); console.log("written InvestmentSystemOverview.docx"); });
