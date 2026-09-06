"""The executive PDF: five sections, real vector charts, print-ready A4."""
from datetime import datetime, timezone

import pdfkit
from pdfkit import Document

INK = "#1C1D21"
FAINT = "#6B6D76"
LEDGER = "#2B4570"
GREEN = "#2F6F4E"
AMBER = "#8A6D3B"
RED = "#B5541B"

SENTIMENT_COLOURS = {"positive": GREEN, "neutral": AMBER, "negative": RED}


def build(report):
    primary = report["primary"]
    competitor = report.get("competitor")
    comparison = report.get("comparison")
    doc = Document()

    def footer(document):
        page_number = len(document.pages) + 1
        document.line(document.margin, document.margin + 12,
                      document.width - document.margin, document.margin + 12,
                      colour="#E4E1D8", width=0.6)
        document.text(document.margin, document.margin + 2,
                      primary["label"] + " · review intelligence report", size=7,
                      colour=FAINT)
        document.text(document.margin, document.margin + 2, str(page_number), size=7,
                      colour=FAINT, align="right", width=document.content_width)

    doc.set_footer(footer)
    footer(doc)

    cover(doc, report)
    section_dashboard(doc, primary, report)
    section_themes(doc, primary)
    section_temporal(doc, primary)
    section_bottlenecks(doc, primary)
    section_framework(doc, primary)
    if comparison:
        section_competitor(doc, primary, competitor, comparison)
    section_method(doc, report)
    return doc.render(primary["label"] + " — review intelligence report")


# --- cover ----------------------------------------------------------------

def cover(doc, report):
    primary = report["primary"]
    doc.rect(doc.margin, doc.y - 4, doc.content_width, 3, fill=LEDGER)
    doc.y -= 22
    doc.text(doc.margin, doc.y, "REVIEW INTELLIGENCE REPORT", size=7.6, font="F2",
             colour=FAINT)
    doc.y -= 30
    doc.text(doc.margin, doc.y, primary["label"], size=25, font="F5")
    doc.y -= 18
    generated = datetime.now(timezone.utc).strftime("%d %B %Y")
    line = (str(primary["kpis"]["total_reviews"]) + " reviews analysed · "
            + str(primary["kpis"]["coded_units"]) + " coded statements · generated "
            + generated)
    doc.text(doc.margin, doc.y, line, size=9, colour=FAINT)
    doc.y -= 14
    if report.get("competitor"):
        doc.text(doc.margin, doc.y, "Benchmarked against " + report["competitor"]["label"],
                 size=9, colour=LEDGER)
        doc.y -= 14
    doc.text(doc.margin, doc.y, "Source: " + report["meta"]["source_label"], size=8,
             colour=FAINT)
    doc.y -= 22


# --- 1. executive dashboard ----------------------------------------------

def section_dashboard(doc, primary, report):
    kpis = primary["kpis"]
    doc.heading("1  Executive dashboard", size=14, rule=True, gap_before=6)

    tiles = [
        (str(kpis["net_sentiment_score"]), "Net sentiment score",
         "positive share minus negative share, -100 to +100",
         GREEN if kpis["net_sentiment_score"] > 20 else
         RED if kpis["net_sentiment_score"] < 0 else AMBER),
        (str(kpis["total_reviews"]), "Reviews analysed",
         str(kpis["coded_units"]) + " statements coded", LEDGER),
        (("%.2f" % kpis["average_rating"]) if kpis["average_rating"] else "—",
         "Average star rating", "as published on the listing", LEDGER),
        (str(int(round(kpis["negative_ratio"] * 100))) + "%", "Negative sentiment",
         str(kpis["negative"]) + " of " + str(kpis["total_reviews"]) + " reviews",
         RED if kpis["negative_ratio"] > 0.3 else AMBER),
    ]
    doc.ensure(110)
    tile_width = (doc.content_width - 3 * 10) / 4
    top = doc.y - 78
    for index, (value, label, note, accent) in enumerate(tiles):
        pdfkit.kpi_tile(doc, doc.margin + index * (tile_width + 10), top, tile_width, 78,
                        value, label, note, accent)
    doc.y = top - 18

    doc.ensure(190)
    box_top = doc.y - 170
    doc.rect(doc.margin, box_top, doc.content_width, 170, fill="#FFFFFF",
             stroke="#E4E1D8", radius=4)
    doc.text(doc.margin + 16, box_top + 152, "SENTIMENT VALENCE", size=7, font="F2",
             colour=FAINT)
    segments = [
        ("Positive", kpis["positive"], GREEN),
        ("Neutral", kpis["neutral"], AMBER),
        ("Negative", kpis["negative"], RED),
    ]
    pdfkit.donut(doc, doc.margin + 92, box_top + 74, 56, segments, thickness=22,
                 centre_label=str(kpis["net_sentiment_score"]), centre_sub="NSS")
    pdfkit.donut_legend(doc, doc.margin + 176, box_top + 116, segments)

    findings = key_findings(primary, report)
    text_x = doc.margin + 360
    doc.text(text_x, box_top + 152, "WHAT THIS SAYS", size=7, font="F2", colour=FAINT)
    y = box_top + 136
    for finding in findings:
        for line in pdfkit.wrap("• " + finding, 8.2, doc.content_width - 380):
            doc.text(text_x, y, line, size=8.2)
            y -= 11.4
        y -= 3
    doc.y = box_top - 16


def key_findings(primary, report):
    kpis = primary["kpis"]
    out = []
    bottleneck = primary["bottlenecks"][0] if primary["bottlenecks"] else None
    if bottleneck:
        out.append(bottleneck["issue"] + " is the largest friction point, in "
                   + str(bottleneck["reviewers"]) + " reviews.")
    negative_categories = [entry for entry in primary["content"]["summary"]
                           if entry["mean_valence"] < -0.15 and entry["mentions"] >= 2]
    if negative_categories:
        out.append("Most negative category: " + negative_categories[0]["category"]
                   + " (" + str(negative_categories[0]["mentions"]) + " mentions).")
    positive_categories = [entry for entry in primary["content"]["summary"]
                           if entry["mean_valence"] > 0.15 and entry["mentions"] >= 2]
    if positive_categories:
        out.append("Strongest asset: " + positive_categories[0]["category"] + ".")
    rating_gap = [item for item in primary["contradictions"]
                  if item["kind"] == "rating-vs-text"]
    if rating_gap:
        out.append(str(len(rating_gap)) + " review(s) carry a star rating that "
                   "contradicts the text — the average rating flatters you.")
    if kpis["owner_response_rate"] < 0.3:
        out.append("Owner responses on "
                   + str(int(round(kpis["owner_response_rate"] * 100)))
                   + "% of reviews; unanswered complaints stay the public record.")
    if report.get("comparison"):
        out.append(report["comparison"]["headline"])
    return out[:6]


# --- 2. temporal ----------------------------------------------------------

def section_themes(doc, primary):
    """The thematic framework — function 2's reasoning, with its evidence."""
    themes = primary.get("themes") or []
    if not themes:
        return
    doc.heading("2  Thematic framework", size=14, rule=True)
    engine = (primary.get("engine") or {}).get("reasoning")
    doc.paragraph(
        "Every coded statement was sorted into the theme it belongs to by meaning, "
        "not by shared words. Coverage is the share of reviewers whose reviews "
        "support the theme."
        + ("" if engine == "claude" else
           " This run used the local fallback engine, so treat the groupings as "
           "provisional."),
        colour=FAINT, size=8.6)

    for theme in themes:
        doc.ensure(120)
        doc.text(doc.margin, doc.y - 11, theme["theme"], size=11.5, font="F2")
        doc.text(doc.margin, doc.y - 11,
                 str(theme.get("evidence_count", 0)) + " statements · "
                 + str(len(theme.get("participants", []))) + " reviewers · "
                 + str(int(round(theme.get("coverage", 0) * 100))) + "% coverage",
                 size=7.8, colour=FAINT, align="right", width=doc.content_width)
        doc.y -= 18
        colour = SENTIMENT_COLOURS.get(theme.get("sentiment", "neutral"), AMBER)
        pdfkit.bar_row(doc, doc.margin, doc.y, doc.content_width,
                       theme.get("coverage", 0), 1.0, colour)
        doc.y -= 14
        if theme.get("description"):
            doc.paragraph(theme["description"], size=8.8, leading=12, gap=4)
        for quote in (theme.get("quotes") or [])[:2]:
            stars = (str(int(quote["rating"])) + "* " if quote.get("rating") else "")
            doc.quote(quote["text"], stars + quote.get("reviewer", ""))
        if theme.get("alternative_interpretation"):
            doc.paragraph("Alternative reading: " + theme["alternative_interpretation"],
                          size=8.4, leading=11.5, colour=FAINT, gap=8)


def section_temporal(doc, primary):
    doc.heading("3  Temporal and sentiment trend distribution", size=14, rule=True)
    series = primary["temporal"]["series"]
    if not series:
        doc.paragraph("No dated reviews were available, so no trend can be shown.",
                      colour=FAINT)
        return

    doc.paragraph(primary["temporal"]["reading"])
    doc.ensure(210)
    chart_top = doc.y - 190
    doc.rect(doc.margin, chart_top, doc.content_width, 190, fill="#FFFFFF",
             stroke="#E4E1D8", radius=4)
    groups = [entry["bucket"] for entry in series]
    pdfkit.grouped_bars(
        doc, doc.margin + 40, chart_top + 58, doc.content_width - 70, 106, groups,
        [("Positive", GREEN, [entry["positive"] for entry in series]),
         ("Neutral", AMBER, [entry["neutral"] for entry in series]),
         ("Negative", RED, [entry["negative"] for entry in series])])
    doc.y = chart_top - 16

    rows = [[
        entry["bucket"], str(entry["total"]), str(entry["positive"]),
        str(entry["neutral"]), str(entry["negative"]),
        ("%.2f" % entry["average_rating"]) if entry["average_rating"] else "—",
        str(int(round(entry["negative_ratio"] * 100))) + "%",
    ] for entry in series]
    doc.table(["Period", "Reviews", "Positive", "Neutral", "Negative", "Avg rating",
               "Negative share"], rows, [150, 70, 70, 70, 70, 80, 90],
              align=["left", "right", "right", "right", "right", "right", "right"])

    trend = primary.get("sentiment_trend") or {}
    if trend.get("points"):
        doc.heading("How sentiment has moved", size=11.5, gap_before=8)
        doc.paragraph(
            "Coded sentiment of what reviewers actually wrote, oldest period on the "
            "left. Star ratings move in whole numbers and lag; the language turns "
            "first.", colour=FAINT, size=8.6)
        doc.ensure(150)
        top = doc.y - 132
        doc.rect(doc.margin, top, doc.content_width, 132, fill="#FFFFFF",
                 stroke="#E4E1D8", radius=4)
        pdfkit.line_chart(
            doc, doc.margin + 40, top + 30, doc.content_width - 70, 78,
            [point["mean_sentiment"] for point in trend["points"]],
            [point["label"] for point in trend["points"]],
            low=-1.0, high=1.0, colour=LEDGER)
        doc.y = top - 12
        doc.paragraph(trend.get("note", ""), size=8.8)


# --- 3. bottlenecks and contradictions ------------------------------------

def section_bottlenecks(doc, primary):
    doc.heading("4  Operational bottleneck audit", size=14, rule=True)
    bottlenecks = primary["bottlenecks"]
    if not bottlenecks:
        doc.paragraph("No sustained negative pattern was found in this corpus.",
                      colour=FAINT)
    else:
        doc.paragraph("Friction points ranked by severity — a blend of how negative the "
                      "language is, how many separate reviewers raise it, and how often "
                      "explicit failure words appear.", colour=FAINT, size=8.6)
        rows = []
        for entry in bottlenecks[:8]:
            rows.append([
                entry["issue"],
                entry["category"],
                "▲" * entry["severity_band"],
                str(entry["reviewers"]),
                str(int(round(entry["coverage"] * 100))) + "%",
                ("%.2f" % entry["mean_rating"]) if entry["mean_rating"] else "—",
                str(int(round(entry["recent_share"] * 100))) + "%",
            ])
        doc.table(["Friction point", "Category", "Severity", "Reviewers", "Coverage",
                   "Avg rating", "Last 6 months"],
                  rows, [200, 100, 60, 60, 60, 60, 70],
                  align=["left", "left", "left", "right", "right", "right", "right"])

        doc.ensure(80)
        doc.eyebrow("Evidence")
        for entry in bottlenecks[:3]:
            doc.ensure(60)
            doc.text(doc.margin, doc.y - 9, entry["issue"], size=9.6, font="F2")
            doc.y -= 16
            for item in entry["evidence"][:2]:
                stars = (str(int(item["rating"])) + "★ " if item["rating"] else "")
                doc.quote(item["text"], stars + item["reviewer"] + " · " + item["bucket"])

    contradictions = primary["contradictions"]
    doc.heading("Contradictions matrix", size=11.5, gap_before=10)
    if not contradictions:
        doc.paragraph("No internal contradictions were detected.", colour=FAINT)
        return
    doc.paragraph("Where the same review, or the same theme across reviews, pulls in two "
                  "directions. These are the places an average score hides a problem.",
                  colour=FAINT, size=8.6)
    rows = [[
        item["theme"],
        "▲" * item["severity"],
        item["kind"],
        item["description"],
    ] for item in contradictions[:8]]
    doc.table(["Theme", "Severity", "Type", "Description"], rows, [110, 50, 80, 320],
              align=["left", "left", "left", "left"])


# --- 4. framework matrix --------------------------------------------------

def section_framework(doc, primary):
    doc.heading("5  Framework matrix: the customer journey", size=14, rule=True)
    framework = primary["framework"]
    doc.paragraph("The corpus indexed against the six stages of the customer journey. "
                  "Coverage is the share of reviewers who speak to that stage at all; "
                  "a stage nobody mentions is as informative as one everybody complains "
                  "about.", colour=FAINT, size=8.6)

    doc.ensure(40)
    for entry in framework["synthesis"]:
        doc.ensure(66)
        colour = SENTIMENT_COLOURS.get(entry.get("sentiment", "neutral"), AMBER)
        doc.text(doc.margin, doc.y - 10, entry["stage"], size=10.5, font="F2")
        doc.text(doc.margin, doc.y - 10,
                 str(int(round(entry["coverage"] * 100))) + "% of reviewers", size=8,
                 colour=FAINT, align="right", width=doc.content_width)
        doc.y -= 17
        pdfkit.bar_row(doc, doc.margin, doc.y, doc.content_width, entry["coverage"], 1.0,
                       colour)
        doc.y -= 14
        doc.paragraph(entry["reading"], size=8.6, leading=11.8, gap=3)
        if entry.get("quote"):
            doc.quote(entry["quote"], entry.get("quote_reviewer"))
        doc.y -= 4


# --- 5. competitor --------------------------------------------------------

def section_competitor(doc, primary, competitor, comparison):
    doc.new_page()
    doc.heading("6  Competitor cross-comparison", size=14, rule=True, gap_before=0)
    doc.paragraph(comparison["headline"])

    doc.ensure(300)
    chart_top = doc.y - 280
    doc.rect(doc.margin, chart_top, doc.content_width, 280, fill="#FFFFFF",
             stroke="#E4E1D8", radius=4)
    axes = [entry["dimension"] for entry in comparison["radar"]]
    pdfkit.radar(doc, doc.margin + doc.content_width / 2, chart_top + 152, 104, axes,
                 [(primary["label"], LEDGER, [entry["primary"] for entry in comparison["radar"]]),
                  (competitor["label"], AMBER,
                   [entry["competitor"] for entry in comparison["radar"]])])
    doc.y = chart_top - 16

    rows = [[
        entry["dimension"],
        "%.1f" % entry["primary"],
        "%.1f" % entry["competitor"],
        ("+" if entry["gap"] > 0 else "") + ("%.1f" % entry["gap"]),
        str(entry["primary_mentions"]) + " / " + str(entry["competitor_mentions"]),
    ] for entry in comparison["radar"]]
    doc.table(["Dimension", "You", "Them", "Gap", "Mentions (you/them)"],
              rows, [220, 60, 60, 60, 110],
              align=["left", "right", "right", "right", "right"])

    doc.heading("Adoption parameters", size=11.5, gap_before=8)
    if not comparison["adoption_parameters"]:
        doc.paragraph("No competitor strength stands out as something you lack.",
                      colour=FAINT)
    else:
        doc.paragraph("Practices their customers praise that yours do not. Ranked by the "
                      "size of the gap.", colour=FAINT, size=8.6)
        for entry in comparison["adoption_parameters"][:5]:
            doc.ensure(96)
            doc.text(doc.margin, doc.y - 10, entry["parameter"], size=10.5, font="F2")
            gap_text = ("gap " + ("%.1f" % entry["gap"])
                        + ("  ·  you " + str(entry["your_score"]) if entry["your_score"] is not None else "")
                        + ("  ·  them " + str(entry["their_score"]) if entry["their_score"] is not None else ""))
            doc.text(doc.margin, doc.y - 10, gap_text, size=8, colour=FAINT,
                     align="right", width=doc.content_width)
            doc.y -= 18
            doc.paragraph(entry["recommendation"], size=8.8, leading=12, gap=4)
            if entry.get("evidence"):
                doc.quote(entry["evidence"]["text"],
                          "Their customer · " + str(entry["evidence"].get("reviewer", "")))
            doc.y -= 2

    if comparison["defend"]:
        doc.heading("Hold your lead", size=11.5, gap_before=6)
        doc.bullets([entry["dimension"] + " — you lead by "
                     + ("%.1f" % entry["lead"]) + " points."
                     for entry in comparison["defend"]])


# --- method ---------------------------------------------------------------

def section_method(doc, report):
    doc.heading("Method and limitations", size=11.5, rule=True)
    meta = report["meta"]
    doc.paragraph(
        "Every review was split into sentences and coded individually: an emotion, a "
        "discourse intent, a valence score from -1 to +1, a confidence score and an "
        "alternative reading. Codes were grouped into themes by similarity in a concept "
        "space derived from the corpus itself. Sentiment at review level blends the text "
        "reading (65%) with the star rating (35%), which is why a five-star review full "
        "of complaint still registers as negative — and appears in the contradictions "
        "matrix.", size=8.6, leading=11.8)
    doc.paragraph(
        "Limitations: review text is self-selected and skews to extremes; relative "
        "timestamps (\"3 months ago\") are normalised to approximate dates, so period "
        "boundaries are indicative; and the coding engine is lexicon-driven, so it reads "
        "sarcasm and idiom poorly. Every claim in this report is traceable to a "
        "quotation in the accompanying workbook — check the quotations before acting on "
        "anything expensive.", size=8.6, leading=11.8)
    doc.paragraph("Source: " + meta["source_label"] + ". Generated "
                  + datetime.now(timezone.utc).strftime("%d %B %Y %H:%M UTC")
                  + " by QRIP.", size=8, colour=FAINT)
