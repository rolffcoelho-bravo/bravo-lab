from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, StyleSheet1
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Image,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
FRONT_MEMO = REPORTS / "front_office_memo.md"
BASELINE_REPORT = REPORTS / "baseline_report.md"

OUT = REPORTS / "BRAVO_Lab_Executive_Report_v0.1.2_styled.pdf"
TMP = REPORTS / "_bravo_toc_probe.pdf"

PAGE_W, PAGE_H = A4

DEEP = colors.HexColor("#070D18")
GOLD = colors.HexColor("#F5A400")
WHITE = colors.HexColor("#F8FAFC")
INK = colors.HexColor("#111827")
BODY = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#D8DEE9")
SOFT = colors.HexColor("#F7F9FC")
BLUE = colors.HexColor("#123B5D")


TOC_ITEMS = [
    ("Executive summary", "summary"),
    ("Decision language and glossary", "glossary"),
    ("Current decision memo", "front_memo"),
    ("Visual evidence and interpretation", "visual_layer"),
    ("Portfolio question", "portfolio_question"),
    ("Market state", "market_state"),
    ("Data provenance and evidence classification", "data_provenance"),
    ("Regime diagnosis", "regime_diagnosis"),
    ("Baseline risk metrics", "baseline_risk"),
    ("Synthetic overlay results", "synthetic_overlay"),
    ("Active risk diagnostics", "active_risk"),
    ("Active risk by regime", "active_risk_regime"),
    ("Multi-asset stress signals", "multi_asset"),
    ("Brazil Stress Transmission Index", "bsti"),
    ("BSTI threshold validation", "bsti_validation"),
    ("BSTI threshold calibration", "bsti_calibration"),
    ("BSTI overlay policy selection", "policy_selection"),
    ("BSTI signal persistence", "persistence"),
    ("Drawdown, implementation, and attribution diagnostics", "diagnostics"),
    ("Model limits and final decision read", "limits"),
]


SECTION_ANCHORS = {
    "portfolio question": "portfolio_question",
    "market state": "market_state",
    "data provenance": "data_provenance",
    "regime diagnosis": "regime_diagnosis",
    "baseline risk metrics": "baseline_risk",
    "synthetic overlay results": "synthetic_overlay",
    "active risk diagnostics": "active_risk",
    "active risk by regime": "active_risk_regime",
    "multi-asset stress signals": "multi_asset",
    "brazil stress transmission index": "bsti",
    "bsti threshold validation": "bsti_validation",
    "bsti threshold calibration": "bsti_calibration",
    "bsti overlay policy selection": "policy_selection",
    "bsti signal persistence": "persistence",
    "drawdown and recovery diagnostics": "diagnostics",
    "regime and stress diagnostics": "diagnostics",
    "strategy help-hurt diagnostics": "diagnostics",
    "implementation drag diagnostics": "diagnostics",
    "option overlay attribution": "diagnostics",
    "option attribution by context": "diagnostics",
    "overlay decision matrix": "diagnostics",
    "model limits": "limits",
}


SECTION_INTROS = {
    "portfolio question": "BRAVO begins with a portfolio decision, not a chart. The question is whether Brazilian equity exposure should remain passive, monetize volatility through covered calls, protect downside through collars, or wait for stronger evidence.",
    "market state": "The market-state layer gives the first context for Brazilian risk. Local equity behavior is not enough. External Brazil exposure, global equity pressure, USD/BRL, and VIX help explain whether the current movement is isolated noise or part of a wider stress channel.",
    "data provenance": "This section protects the credibility of the work. A finished decision report must tell the reviewer what is observed, what is model-derived, what is synthetic, and what is only a rule-based signal.",
    "regime diagnosis": "The regime diagnosis classifies the local Brazilian equity environment before the stress-transmission layer is added. It uses realized volatility, volatility percentile, and drawdown to identify whether the overlay discussion is happening in calm, fragile, stress, or extreme-stress conditions.",
    "baseline risk metrics": "The baseline risk table is the first risk map. It shows whether the assets feeding BRAVO carry normal volatility, deep drawdown risk, tail risk, or unstable return patterns.",
    "synthetic overlay results": "This section compares passive exposure, covered-call income, collar protection, and stress-aware switching. The option overlays are synthetic, so the numbers are research evidence, not live tradability claims.",
    "active risk diagnostics": "This section asks whether each overlay earns the right to deviate from passive Brazilian equity. Return alone is insufficient. Tracking error, information ratio, hit rate, downside hit rate, and worst active period tell the reviewer whether the active decision is governable.",
    "active risk by regime": "This is one of the most important sections in the report. A strategy can look acceptable across the full sample and still fail inside a specific regime.",
    "multi-asset stress signals": "The multi-asset stress layer turns BRAVO from a simple local backtest into a stress-transmission framework. It identifies whether pressure is coming from Brazil drawdown, FX, external Brazil exposure, global equity pressure, or VIX.",
    "brazil stress transmission index": "BSTI is the central stress signal. It compresses multiple Brazil-related pressure channels into a 0 to 100 index while keeping the dominant channel visible. Its purpose is portfolio governance, not market prophecy.",
    "bsti threshold validation": "A stress index is useful only if its thresholds connect to future risk outcomes. This validation layer tests whether BSTI levels relate to future drawdowns and overlay behavior under elevated stress.",
    "bsti threshold calibration": "Calibration asks whether different threshold and weighting choices create a more useful governance signal. The goal is not to overfit the index. The goal is to test whether the signal becomes more decision-useful under alternative designs.",
    "bsti overlay policy selection": "This is where diagnosis becomes action. The BSTI rule maps stress levels into passive exposure, covered-call income, or collar protection.",
    "bsti signal persistence": "Persistence separates a real warning process from a random spike. A temporary stress print should not trigger the same response as a durable warning state.",
    "drawdown and recovery diagnostics": "This section tests the real trade-off of protection. An overlay may help during drawdowns and still damage the rebound.",
    "implementation drag diagnostics": "Implementation drag separates gross signal quality from net result. A strategy that looks good before friction can fail after transaction costs, taxes, liquidity, and roll mechanics.",
    "option overlay attribution": "Option attribution breaks the overlay into economic parts: premium income, protection cost, payoff effect, implementation drag, and net effect.",
    "overlay decision matrix": "The decision matrix turns the evidence into practical governance language: when a strategy is useful, when it is dangerous, and when the evidence remains unvalidated.",
    "model limits": "The limits section prevents overclaiming. BRAVO is a decision-support research prototype. The synthetic option layer needs real B3 option-chain validation before production use.",
}


CHARTS = [
    ("00_executive_risk_dashboard.png", "Executive risk dashboard"),
    ("01_cumulative_performance.png", "Cumulative performance path"),
    ("02_drawdown_profile.png", "Drawdown control map"),
    ("03_bsti_signal.png", "Brazil Stress Transmission Index"),
    ("04_bsti_policy_selection_mix.png", "BSTI policy-selection mix"),
    ("05_risk_return_positioning.png", "Risk-return positioning map"),
    ("06_bsti_transition_matrix.png", "BSTI state-transition matrix"),
    ("07_bsti_calibration_scores.png", "BSTI calibration scorecard"),
]


CHART_TEXT = {
    "00_executive_risk_dashboard.png": [
        "The dashboard is the decision surface of the project. It shows the current BSTI score, regime, dominant pressure channel, policy action, strongest information-ratio strategy, and strongest drawdown profile in one view.",
        "This image matters because it converts many processed outputs into a portfolio question: does the current state justify passive exposure, income capture, protection, or only monitoring? In the current run, the signal is calm and the policy action is passive, which means the model is disciplined enough not to force an overlay when the evidence does not demand it.",
    ],
    "01_cumulative_performance.png": [
        "This chart compares passive Brazilian equity, covered calls, collars, stress-aware switching, and the BSTI policy overlay under the same market history.",
        "The professional question is not which line looks most impressive. It is whether the improvement in path behavior is worth the active risk, transaction costs, liquidity limits, tax effects, and synthetic option assumptions. This is where BRAVO moves from return display to portfolio-governance reasoning.",
    ],
    "02_drawdown_profile.png": [
        "This chart shows how much each strategy loses from its previous peak. That is the practical test of protection because drawdowns are where portfolio discipline becomes visible.",
        "The collar is judged by whether it reduces left-tail pain. The covered call is judged by whether the income earned is worth the risk of capped recovery. This chart is important because it shows the cost of ignoring downside behavior when comparing overlays only by return.",
    ],
    "03_bsti_signal.png": [
        "BSTI translates several Brazil-related stress channels into one monitorable 0 to 100 signal.",
        "The chart is not a forecast. It is a governance signal. When the index moves toward warning or stress, the committee has a reason to inspect persistence, dominant channel, and overlay choice. That is the value: it turns scattered risk inputs into a disciplined escalation process.",
    ],
    "04_bsti_policy_selection_mix.png": [
        "This chart shows how often the BSTI rule selects passive equity, covered calls, or collars.",
        "A disciplined policy should not trade all the time. The mix shows whether BRAVO mostly preserves beta, selectively harvests volatility income, or moves toward protection during stress.",
    ],
    "05_risk_return_positioning.png": [
        "This chart places each strategy in annualized return and annualized volatility space.",
        "It prevents the report from becoming return-only. A strategy must be judged by its risk, drawdown, implementation burden, and mandate fit, not only by return.",
    ],
    "06_bsti_transition_matrix.png": [
        "This chart shows whether normal, warning, and stress states persist or quickly reverse.",
        "Persistence matters because a one-period warning should not trigger the same response as a durable stress state. This is the evidence behind escalation discipline.",
    ],
    "07_bsti_calibration_scores.png": [
        "This chart compares threshold and weighting choices for the BSTI signal.",
        "The value is auditability. The stress index is not treated as magic; it is tested against governance criteria such as precision, recall, signal frequency, and drawdown relevance.",
    ],
}


class BravoDoc(SimpleDocTemplate):
    def __init__(self, *args, **kwargs):
        self.section_pages = {}
        self.outline_added = set()
        super().__init__(*args, **kwargs)

    def afterFlowable(self, flowable):
        if hasattr(flowable, "_bookmarkName"):
            key = flowable._bookmarkName
            title = flowable._bookmarkTitle
            level = flowable._bookmarkLevel
            if key not in self.section_pages:
                self.section_pages[key] = self.page
            try:
                self.canv.bookmarkPage(key)
                if key not in self.outline_added:
                    self.canv.addOutlineEntry(title, key, level=level, closed=False)
                    self.outline_added.add(key)
            except Exception:
                pass


def read_text(path):
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="ignore")


def normalize(text):
    text = str(text)
    replacements = {
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "…": "...",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = text.replace("**", "")
    text = text.replace("__", "")
    text = text.replace("`", "")
    text = text.replace("ShockBridge Signal:", "BRAVO signal:")
    text = text.replace("ShockBridge Transmission Read", "Transmission Read")
    return text


def safe(text):
    return escape(normalize(text))


def P(text, style):
    return Paragraph(safe(text), style)


def P_raw(text, style):
    return Paragraph(text, style)


def make_styles():
    styles = StyleSheet1()

    styles.add(ParagraphStyle("CoverTitle", fontName="Helvetica-Bold", fontSize=42, leading=49, alignment=TA_CENTER, textColor=WHITE, spaceAfter=12))
    styles.add(ParagraphStyle("CoverSub", fontName="Helvetica", fontSize=11.4, leading=16.5, alignment=TA_CENTER, textColor=colors.HexColor("#CBD5E1"), spaceAfter=17))
    styles.add(ParagraphStyle("CoverGold", fontName="Helvetica-Bold", fontSize=8.8, leading=12, alignment=TA_CENTER, textColor=GOLD, spaceAfter=14))

    styles.add(ParagraphStyle("Kicker", fontName="Helvetica-Bold", fontSize=7.5, leading=10, alignment=TA_LEFT, textColor=GOLD, spaceBefore=7, spaceAfter=4))
    styles.add(ParagraphStyle("Title", fontName="Helvetica-Bold", fontSize=16.0, leading=19.2, alignment=TA_LEFT, textColor=INK, spaceAfter=7, keepWithNext=1))
    styles.add(ParagraphStyle("H2", fontName="Helvetica-Bold", fontSize=11.8, leading=14.3, alignment=TA_LEFT, textColor=BLUE, spaceBefore=6, spaceAfter=5, keepWithNext=1))
    styles.add(ParagraphStyle("Body", fontName="Helvetica", fontSize=9.65, leading=13.75, alignment=TA_JUSTIFY, textColor=BODY, spaceAfter=5))
    styles.add(ParagraphStyle("Lead", fontName="Helvetica-Bold", fontSize=9.55, leading=13.75, alignment=TA_LEFT, textColor=INK, spaceAfter=6))
    styles.add(ParagraphStyle("Bullet", fontName="Helvetica", fontSize=9.35, leading=13.45, leftIndent=13, firstLineIndent=-8, alignment=TA_JUSTIFY, textColor=BODY, spaceAfter=4))
    styles.add(ParagraphStyle("Cell", fontName="Helvetica", fontSize=8.15, leading=9.75, alignment=TA_LEFT, textColor=BODY))
    styles.add(ParagraphStyle("CellBold", fontName="Helvetica-Bold", fontSize=8.15, leading=9.75, alignment=TA_LEFT, textColor=INK))
    styles.add(ParagraphStyle("TOC", fontName="Helvetica", fontSize=9.2, leading=12.8, alignment=TA_LEFT, textColor=BLUE, spaceAfter=3))
    styles.add(ParagraphStyle("TOCBold", fontName="Helvetica-Bold", fontSize=9.2, leading=12.8, alignment=TA_LEFT, textColor=INK, spaceAfter=3))
    styles.add(ParagraphStyle("Caption", fontName="Helvetica", fontSize=8.85, leading=12.45, alignment=TA_JUSTIFY, textColor=BODY, spaceBefore=3, spaceAfter=4))
    styles.add(ParagraphStyle("Note", fontName="Helvetica", fontSize=8.4, leading=12.0, alignment=TA_JUSTIFY, textColor=MUTED, spaceAfter=7))

    return styles


def cover_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(DEEP)
    canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(1.8)
    canvas.line(0, PAGE_H - 18, PAGE_W, PAGE_H - 18)
    canvas.line(0, 18, PAGE_W, 18)
    canvas.restoreState()


def normal_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(0.8)
    canvas.line(doc.leftMargin, PAGE_H - 34, PAGE_W - doc.rightMargin, PAGE_H - 34)

    canvas.setFont("Helvetica-Bold", 6.6)
    canvas.setFillColor(GOLD)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - 25, "BRAVO LAB - EXECUTIVE REPORT")

    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.45)
    canvas.line(doc.leftMargin, 38, PAGE_W - doc.rightMargin, 38)

    canvas.setFont("Helvetica", 6.8)
    canvas.setFillColor(MUTED)
    canvas.drawString(doc.leftMargin, 24, "BRAVO Lab - Brazilian Risk, Allocation, Volatility & Options Lab - Research prototype - Not investment advice")

    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(GOLD)
    canvas.drawRightString(PAGE_W - doc.rightMargin, 24, str(doc.page))
    canvas.restoreState()


def add_heading(story, styles, kicker, title, anchor, level=0):
    story.append(P(kicker.upper(), styles["Kicker"]))
    p = P_raw(f'<a name="{anchor}"/>{safe(title)}', styles["Title"])
    p._bookmarkName = anchor
    p._bookmarkTitle = normalize(title)
    p._bookmarkLevel = level
    story.append(p)


def add_h2(story, styles, title, anchor=None):
    if anchor:
        p = P_raw(f'<a name="{anchor}"/>{safe(title)}', styles["H2"])
        p._bookmarkName = anchor
        p._bookmarkTitle = normalize(title)
        p._bookmarkLevel = 1
        story.append(p)
    else:
        story.append(P(title, styles["H2"]))


def add_paragraph(story, styles, text, lead=False):
    text = normalize(text).strip()
    if text:
        story.append(P(text, styles["Lead"] if lead else styles["Body"]))


def add_bullet(story, styles, text):
    text = normalize(text).strip()
    if text:
        story.append(P("- " + text, styles["Bullet"]))


def is_numbered_section(line):
    s = normalize(line).strip()
    m = re.match(r"^(\d{1,2})\.\s+(.+)$", s)
    if not m:
        return False

    title = m.group(2).strip()
    if title.endswith(".") or len(title) > 90:
        return False

    section_terms = [
        "Executive Signal", "Portfolio Question", "Market State", "Data Provenance",
        "Regime Diagnosis", "Baseline Risk Metrics", "Synthetic Overlay Results",
        "Active Risk Diagnostics", "Active Risk by Regime", "Multi-Asset Stress Signals",
        "Brazil Stress Transmission Index", "BSTI Threshold Validation", "BSTI Threshold Calibration",
        "BSTI Overlay Policy Selection", "BSTI Signal Persistence", "Drawdown and Recovery Diagnostics",
        "Regime and Stress Diagnostics", "Strategy Help-Hurt Diagnostics", "Implementation Drag Diagnostics",
        "Option Overlay Attribution", "Option Attribution by Context", "Overlay Decision Matrix", "Model Limits"
    ]

    return any(term.lower() in title.lower() for term in section_terms)


def is_heading(line):
    s = line.strip()
    return bool(re.match(r"^#{1,6}\s+\S+", s)) or is_numbered_section(s)


def clean_heading(line):
    line = re.sub(r"^#{1,6}\s*", "", line.strip())
    return normalize(line)


def get_anchor(title):
    lower = normalize(title).lower()
    for key, anchor in SECTION_ANCHORS.items():
        if key in lower:
            return anchor
    return None


def is_table_line(line):
    s = line.strip()
    return s.startswith("|") and s.endswith("|")


def is_separator_row(cells):
    return all(re.match(r"^:?-{2,}:?$", c.replace(" ", "")) for c in cells)


def parse_table(lines):
    rows = []
    for line in lines:
        cells = [normalize(c.strip()) for c in line.strip().strip("|").split("|")]
        if cells and not is_separator_row(cells):
            rows.append(cells)
    return rows


def add_table(story, styles, rows):
    if not rows or len(rows) < 2:
        return

    max_cols = max(len(r) for r in rows)
    normalized = [r + [""] * (max_cols - len(r)) for r in rows]

    if max_cols > 7:
        key_cols = 2 if max_cols >= 9 else 1
        remaining = list(range(key_cols, max_cols))
        chunk_size = 5

        for start in range(0, len(remaining), chunk_size):
            chosen = list(range(key_cols)) + remaining[start:start + chunk_size]
            chunk = [[r[i] if i < len(r) else "" for i in chosen] for r in normalized]
            add_table(story, styles, chunk)
        return

    usable_width = 6.55 * inch
    col_widths = [usable_width / max_cols] * max_cols

    data = []
    for i, row in enumerate(normalized):
        st = styles["CellBold"] if i == 0 else styles["Cell"]
        data.append([Paragraph(safe(cell), st) for cell in row])

    table = Table(data, colWidths=col_widths, hAlign="LEFT", repeatRows=1, splitByRow=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), SOFT),
        ("LINEABOVE", (0, 0), (-1, 0), 0.75, GOLD),
        ("LINEBELOW", (0, 0), (-1, 0), 0.55, LINE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table)
    story.append(Spacer(1, 7))


def table_value(md, label, default="not available"):
    label_re = re.escape(label)
    patterns = [
        rf"\|\s*{label_re}\s*\|\s*([^|\n]+?)\s*\|",
        rf"{label_re}:\s*([^\n]+)",
        rf"{label_re}\s+([^\n]+)",
    ]
    for pat in patterns:
        m = re.search(pat, md, flags=re.I)
        if m:
            return normalize(m.group(1)).strip()
    return default


def regex_value(md, pattern, default="not available"):
    m = re.search(pattern, md, flags=re.I | re.S)
    if not m:
        return default
    return normalize(m.group(1)).strip()


def get_context(front, base):
    merged = front + "\n" + base

    data_window = regex_value(
        merged,
        r"Data window:\s*([^\n]+)",
        "2014-01-02 to 2026-06-09"
    )

    return {
        "bsti_score": table_value(merged, "Current BSTI score", table_value(merged, "BSTI 0-100")),
        "bsti_regime": table_value(merged, "Current BSTI regime", table_value(merged, "Latest classified regime")),
        "dominant_channel": table_value(merged, "Dominant pressure channel"),
        "policy_action": table_value(merged, "Current policy action"),
        "dominant_policy": table_value(merged, "Dominant historical policy choice"),
        "active_return": table_value(merged, "BSTI policy annualized active return"),
        "tracking_error": table_value(merged, "BSTI policy tracking error"),
        "information_ratio": table_value(merged, "BSTI policy information ratio"),
        "max_drawdown": table_value(merged, "BSTI policy max drawdown"),
        "data_window": data_window,
    }


def add_toc(story, styles, page_map=None):
    add_heading(story, styles, "Navigation", "Contents", "contents", 0)

    rows = [[P("Section", styles["TOCBold"]), P("Page", styles["TOCBold"])]]
    for label, anchor in TOC_ITEMS:
        page = ""
        if page_map:
            page = str(page_map.get(anchor, ""))
        rows.append([
            P_raw(f'<link href="#{anchor}"><font color="#123B5D">{safe(label)}</font></link>', styles["TOC"]),
            P(page, styles["TOC"])
        ])

    table = Table(rows, colWidths=[5.85 * inch, 0.65 * inch], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, GOLD),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, LINE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, LINE),
        ("BACKGROUND", (0, 0), (-1, 0), SOFT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table)
    story.append(Spacer(1, 10))
    story.append(P("The report is organized as a decision review: current signal, evidence stack, visual diagnostics, validation layer, policy rule, implementation limits, and final decision read.", styles["Note"]))
    story.append(PageBreak())



def add_summary(story, styles, ctx):
    add_heading(story, styles, "Executive summary", "What BRAVO Lab is deciding", "summary", 0)

    add_paragraph(story, styles, "BRAVO Lab is a portfolio-governance research prototype for Brazilian market risk. Its purpose is not to predict the market. Its purpose is to convert data, stress signals, synthetic option overlays, and active-risk diagnostics into a structured decision conversation.", lead=True)

    add_paragraph(story, styles, "The practical question is simple and valuable: when Brazilian risk changes state, should the portfolio remain passive, harvest volatility income through covered calls, protect downside through collars, or wait because the signal is not persistent enough? BRAVO gives that question a reproducible evidence stack instead of leaving it to intuition.")

    add_paragraph(story, styles, "The project demonstrates the full chain from market data to decision language: data ingestion, volatility and drawdown diagnostics, regime classification, synthetic option-overlay comparison, active-risk measurement, multi-asset stress transmission, BSTI construction, threshold validation, calibration, policy selection, and implementation limits. That is the value of the report: it shows a working research pipeline, not a decorative backtest.")

    add_paragraph(story, styles, "The current read is deliberately conservative. The latest BSTI state is calm, the dominant pressure channel is Brazil drawdown pressure, and the current policy action is passive Brazil equity. The important insight is that the system is not forcing action. It is creating discipline: monitor the signal, check persistence, compare policy behavior, and only escalate to income or protection overlays when evidence justifies it.")

    add_table(story, styles, [
        ["Decision field", "Current project read"],
        ["BSTI score", ctx["bsti_score"]],
        ["BSTI regime", ctx["bsti_regime"]],
        ["Dominant pressure channel", ctx["dominant_channel"]],
        ["Current policy action", ctx["policy_action"]],
        ["Dominant historical policy choice", ctx["dominant_policy"]],
        ["BSTI policy annualized active return", ctx["active_return"]],
        ["Tracking error", ctx["tracking_error"]],
        ["Information ratio", ctx["information_ratio"]],
        ["Max drawdown", ctx["max_drawdown"]],
        ["Data window", ctx["data_window"]],
    ])

def add_glossary(story, styles):
    add_heading(story, styles, "Decision language", "Glossary for the report", "glossary", 0)

    add_paragraph(story, styles, "The report uses portfolio and risk language because BRAVO is designed to support decisions, not simply display charts. These terms make the logic readable before the reviewer enters the technical repository.", lead=True)

    glossary = [
        ("BSTI", "Brazil Stress Transmission Index. A 0 to 100 composite stress index built from Brazil-related pressure channels."),
        ("BSTI regime", "The interpretation of the BSTI score: calm, fragile, stress, or extreme stress."),
        ("Dominant pressure channel", "The risk source contributing most strongly to the current stress state."),
        ("Stress breadth", "How many pressure channels are active at the same time."),
        ("Covered call", "An income overlay that sells upside participation in exchange for option premium."),
        ("Collar", "A protection overlay that combines downside protection with limited upside participation."),
        ("Tracking error", "How far an overlay deviates from passive Brazilian equity exposure."),
        ("Information ratio", "How much active return is generated per unit of tracking error."),
        ("Governance score", "A calibration score used to compare whether thresholds and channel weights produce useful decision signals."),
        ("Synthetic overlay", "A research approximation using option-pricing assumptions. It is not yet live B3 option-chain evidence."),
    ]

    for term, meaning in glossary:
        story.append(P_raw(f"<b>{safe(term)}.</b> {safe(meaning)}", styles["Body"]))



def add_chart(story, styles, filename, title):
    path = FIGURES / filename
    if not path.exists():
        return

    source = str(path)
    img_reader = ImageReader(source)
    iw, ih = img_reader.getSize()

    max_width = 6.68 * inch
    max_height = 3.28 * inch
    scale = min(max_width / iw, max_height / ih)

    story.append(P(title, styles["H2"]))
    story.append(Image(source, width=iw * scale, height=ih * scale))
    story.append(Spacer(1, 4))

    for paragraph in CHART_TEXT.get(filename, []):
        story.append(P(paragraph, styles["Caption"]))

    story.append(Spacer(1, 7))


def add_visual_layer(story, styles):
    add_heading(story, styles, "Visual evidence", "Visual evidence and decision interpretation", "visual_layer", 0)

    add_paragraph(
        story,
        styles,
        "The visual layer is the fastest inspection layer of BRAVO. It shows whether the project is merely calculating numbers or actually translating Brazilian market stress into portfolio decisions. The sequence matters: first the current decision read, then the strategy path, then drawdown behavior, then the stress index, then the policy rule, then persistence and calibration.",
        lead=True
    )

    add_paragraph(
        story,
        styles,
        "The value is not the image itself. The value is the decision story each image supports: whether the system preserves beta, when it harvests income, when it protects downside, whether stress persists, and whether the BSTI rule is auditable enough to guide a real risk discussion.",
    )

    for filename, title in CHARTS:
        add_chart(story, styles, filename, title)

def remove_visual_block_and_noise(md):
    lines = md.splitlines()
    result = []
    skip_visual = False
    skip_files = False

    for line in lines:
        s = normalize(line).strip()
        lower = s.lower()

        if not s:
            if not skip_visual and not skip_files:
                result.append(line)
            continue

        if s == "##":
            continue

        if "target report length" in lower:
            continue

        if re.match(r"^\d{1,2}\.\s*Generated Evidence Files", s, flags=re.I) or "generated evidence files" in lower:
            skip_files = True
            continue

        if skip_files:
            if re.match(r"^\d{1,2}\.\s+(Model Limits|Final|Conclusion)", s, flags=re.I):
                skip_files = False
                result.append(line)
            else:
                continue
            continue

        if lower.startswith("premium visual evidence layer") or lower.startswith("visual evidence"):
            skip_visual = True
            continue

        if skip_visual:
            if re.match(r"^1\.\s*Executive Signal", s, flags=re.I) or re.match(r"^3\.\s*Portfolio Question", s, flags=re.I):
                skip_visual = False
                result.append(line)
            else:
                continue
            continue

        if re.match(r"!\[[^\]]*\]\([^)]+\)", s):
            continue

        if lower.startswith("figure:") or lower.endswith(".png"):
            continue

        if "figure note:" in lower:
            continue

        if "see reports/figures" in lower:
            continue

        if re.match(r"^[A-Z]:\\", s):
            continue

        if any(token in lower for token in ["scripts/", "scripts\\", ".py", ".md", "reports/", "reports\\", "data/processed"]):
            if "reproducible csv" in lower or "csv outputs" in lower:
                result.append(line)
            continue

        result.append(line)

    cleaned = "\n".join(result)

    cleaned = re.sub(
        r"2\.\s*Report Map.*?(?=3\.\s*Portfolio Question)",
        "",
        cleaned,
        flags=re.I | re.S,
    )

    return cleaned


def baseline_from_portfolio_question(md):
    match = re.search(r"3\.\s*Portfolio Question", md, flags=re.I)
    if match:
        return md[match.start():]
    match = re.search(r"Portfolio Question", md, flags=re.I)
    if match:
        return md[match.start():]
    return md


def add_markdown(story, styles, md):
    md = remove_visual_block_and_noise(md)
    lines = md.splitlines()

    para = []
    table_lines = []

    def flush_para():
        nonlocal para
        if not para:
            return
        text = " ".join(x.strip() for x in para if x.strip())
        para = []
        if text:
            add_paragraph(story, styles, text)

    def flush_table():
        nonlocal table_lines
        if not table_lines:
            return
        rows = parse_table(table_lines)
        table_lines = []
        add_table(story, styles, rows)

    for raw in lines:
        line = raw.rstrip()
        s = line.strip()

        if s == "##":
            flush_para()
            continue

        if is_table_line(s):
            flush_para()
            table_lines.append(s)
            continue

        if table_lines:
            flush_table()

        if not s:
            flush_para()
            continue

        if is_heading(s):
            flush_para()
            title = clean_heading(s)
            lower = title.lower()

            chart_titles = [
                "executive risk dashboard",
                "cumulative performance path",
                "drawdown control map",
                "brazil stress transmission index",
                "bsti policy-selection mix",
                "risk-return positioning map",
                "bsti state-transition matrix",
                "bsti calibration scorecard",
            ]
            if lower in chart_titles:
                continue

            anchor = get_anchor(title)
            add_h2(story, styles, title, anchor=anchor)

            for key, intro in SECTION_INTROS.items():
                if key in lower:
                    add_paragraph(story, styles, intro, lead=True)
                    break

            continue

        if s.startswith("- "):
            flush_para()
            add_bullet(story, styles, s[2:])
            continue

        if re.match(r"^\d+\.\s+", s):
            flush_para()
            add_bullet(story, styles, s)
            continue

        if s.lower().startswith("interpretation:") and any(
            term in s.lower()
            for term in [
                "one-page visual summary",
                "shows whether the overlay logic",
                "tests whether the strategy",
                "displays warning",
                "shows how the model distributes",
                "places each strategy",
                "shows whether the stress signal",
                "ranks calibration candidates",
            ]
        ):
            continue

        para.append(s)

    flush_para()
    flush_table()


def add_front_memo(story, styles, front):
    add_heading(story, styles, "Front-office decision memo", "Current decision read", "front_memo", 0)

    add_paragraph(
        story,
        styles,
        "This is the decision entrance of BRAVO. It shows what the model reads now, which policy action is implied, which evidence supports the signal, and what a committee must check before any action is considered.",
        lead=True
    )

    front = re.sub(r"\n?##\s*\n?", "\n", front)
    front = re.sub(r"\n?Visual Evidence.*$", "", front, flags=re.I | re.S)
    add_markdown(story, styles, front)


def add_repo_note(story, styles):
    add_heading(story, styles, "Model limits", "Model limits and final decision read", "limits", 0)

    add_paragraph(story, styles, "BRAVO is a research prototype for decision support. It uses public market data, model-derived diagnostics, and synthetic option-overlay assumptions. The project is not investment advice and it is not production trading infrastructure yet.", lead=True)
    add_paragraph(story, styles, "The next validation step is real B3 option-chain integration: observed strikes, maturities, bid-ask spreads, liquidity filters, transaction costs, taxes, roll rules, and mandate constraints.")
    add_paragraph(story, styles, "The technical reproducibility materials, code, processed outputs, and figure-generation logic are available in the project repository. They are intentionally not listed inside this finished executive report.")
    add_paragraph(story, styles, "The value of the project is the decision chain: transforming Brazilian market data into stress diagnostics, comparing overlay behavior, evaluating active risk, validating a stress index, defining policy selection, and communicating the result as a governance memo.")


def build_story(styles, front, baseline, ctx, page_map=None):
    story = []

    story.append(Spacer(1, 164))
    story.append(P("BRAVO Lab", styles["CoverTitle"]))
    story.append(P("Brazilian Risk, Allocation, Volatility & Options Lab", styles["CoverSub"]))
    story.append(P("Executive Report", styles["CoverSub"]))
    story.append(P("v0.1.2", styles["CoverGold"]))
    story.append(Spacer(1, 30))
    story.append(P("Brazilian Equity Risk, Volatility Transmission, Synthetic Protection Logic, BSTI Policy Selection, and Portfolio-Governance Diagnostics.", styles["CoverSub"]))
    story.append(Spacer(1, 74))
    story.append(P("CREATED BY", styles["CoverGold"]))
    story.append(P("Rodolfo Pereira", styles["CoverSub"]))
    story.append(P("Research, portfolio risk, derivatives overlays, and market transmission analysis", styles["CoverSub"]))
    story.append(P("Research prototype - Not investment advice", styles["CoverGold"]))
    story.append(PageBreak())

    add_toc(story, styles, page_map=page_map)
    add_summary(story, styles, ctx)
    add_glossary(story, styles)
    story.append(PageBreak())
    add_front_memo(story, styles, front)
    add_visual_layer(story, styles)

    story.append(PageBreak())

    add_heading(story, styles, "Evidence stack", "Original BRAVO evidence, styled and explained", "full_evidence", 0)
    add_paragraph(story, styles, "The next sections preserve the original report's substance while improving readability. The evidence remains the same project logic: market state, data provenance, regime diagnosis, baseline risk, synthetic overlays, active risk, multi-asset stress, BSTI validation, calibration, policy selection, persistence, implementation drag, option attribution, and final limits.", lead=True)

    if baseline.strip():
        add_markdown(story, styles, baseline)
    else:
        add_paragraph(story, styles, "The baseline report was not found. Regenerate the project report before producing the PDF.", lead=True)

    add_repo_note(story, styles)

    return story


def build_once(path, styles, story):
    doc = BravoDoc(
        str(path),
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=62,
        bottomMargin=56,
        title="BRAVO Lab Executive Report v0.1.2 styled",
        author="Rodolfo Pereira",
    )
    doc.build(story, onFirstPage=cover_page, onLaterPages=normal_page)
    return doc.section_pages


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    front = read_text(FRONT_MEMO)
    full_baseline = read_text(BASELINE_REPORT)
    baseline = baseline_from_portfolio_question(full_baseline)

    ctx = get_context(front, full_baseline)
    styles = make_styles()

    probe_story = build_story(styles, front, baseline, ctx, page_map=None)
    page_map = build_once(TMP, styles, probe_story)

    final_story = build_story(styles, front, baseline, ctx, page_map=page_map)
    build_once(OUT, styles, final_story)

    try:
        TMP.unlink()
    except Exception:
        pass

    print(f"PDF generated: {OUT}")


if __name__ == "__main__":
    main()
