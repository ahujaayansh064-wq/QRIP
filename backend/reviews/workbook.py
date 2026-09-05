"""The multi-sheet .xlsx: the report's evidence, in full."""
import exports


def build(report):
    primary = report["primary"]
    competitor = report.get("competitor")
    comparison = report.get("comparison")
    sheets = [
        ("Codebook", codebook_sheet(primary)),
        ("Themes", themes_sheet(primary)),
        ("Contradictions", contradictions_sheet(primary)),
        ("Content Counts", content_sheet(primary)),
        ("Framework Matrix", framework_sheet(primary)),
        ("Bottlenecks", bottleneck_sheet(primary)),
        ("Temporal", temporal_sheet(primary)),
        ("Reviews", reviews_sheet(primary)),
        ("Dashboard", dashboard_sheet(report)),
    ]
    if competitor:
        sheets.append(("Competitor Codebook", codebook_sheet(competitor)))
        sheets.append(("Competitor Reviews", reviews_sheet(competitor)))
    if comparison:
        sheets.append(("Comparison", comparison_sheet(comparison)))
    return exports.write_xlsx(sheets)


def codebook_sheet(side):
    rows = [["Code", "Theme", "Reviewer ID", "Reviewer", "Rating", "Emotion", "Intent",
             "Valence", "Sentiment", "Confidence", "Quote", "Literal meaning",
             "Alternative interpretation", "Period"]]
    for code in side["codebook"]:
        rows.append([
            code["code"], code["theme"], code["reviewer_id"], code["reviewer"],
            code["rating"], code["emotion"], code["intent"], code["valence"],
            code["sentiment"], code["confidence"], code["quote"],
            code["literal_meaning"], code["alternative_interpretation"], code["bucket"],
        ])
    return rows


def themes_sheet(side):
    rows = [["Theme", "Status", "Confidence", "Coverage %", "Quote count", "Reviewers",
             "Sentiment", "Mean valence", "Mean rating", "Description",
             "Alternative interpretation"]]
    for theme in side["themes"]:
        rows.append([
            theme["theme"], theme["status"], theme["confidence"],
            round(theme["coverage"] * 100, 1), theme["quote_count"],
            len(theme["reviewers"]), theme["sentiment"], theme["mean_valence"],
            theme["mean_rating"], theme["description"],
            theme["alternative_interpretation"],
        ])
    return rows


def contradictions_sheet(side):
    rows = [["Theme", "Severity (1-3)", "Type", "Description"]]
    for item in side["contradictions"]:
        rows.append([item["theme"], item["severity"], item["kind"], item["description"]])
    return rows


def content_sheet(side):
    content = side["content"]
    rows = [["Reviewer"] + content["categories"] + ["Total"]]
    for row in content["rows"]:
        rows.append([row["reviewer"]] + row["counts"] + [row["total"]])
    rows.append(["All"] + content["totals"] + [sum(content["totals"])])
    rows.append([])
    rows.append(["Category", "Mentions", "Reviews", "Mean valence", "Sentiment",
                 "Example quote"])
    for entry in content["summary"]:
        example = entry["examples"][0]["text"] if entry["examples"] else ""
        rows.append([entry["category"], entry["mentions"], entry["reviews"],
                     entry["mean_valence"], entry["sentiment"], example])
    return rows


def framework_sheet(side):
    framework = side["framework"]
    rows = [["Reviewer", "Rating"] + framework["stages"]]
    for row in framework["rows"]:
        rows.append([row["reviewer"], row["rating"]]
                    + [cell["summary"] for cell in row["cells"]])
    rows.append([])
    rows.append(["Stage", "Coverage %", "Mentions", "Mean valence", "Sentiment",
                 "Reading", "Illustrative quote"])
    for entry in framework["synthesis"]:
        rows.append([entry["stage"], round(entry.get("coverage", 0) * 100, 1),
                     entry.get("mentions", 0), entry.get("mean_valence", 0),
                     entry.get("sentiment", ""), entry["reading"],
                     entry.get("quote", "")])
    return rows


def bottleneck_sheet(side):
    rows = [["Friction point", "Category", "Severity", "Severity band", "Reviewers",
             "Coverage %", "Mentions", "Mean valence", "Mean rating",
             "Share in last 6 months", "Evidence"]]
    for entry in side["bottlenecks"]:
        evidence = " | ".join(item["reviewer"] + ": " + item["text"]
                              for item in entry["evidence"])
        rows.append([entry["issue"], entry["category"], entry["severity"],
                     entry["severity_band"], entry["reviewers"],
                     round(entry["coverage"] * 100, 1), entry["mentions"],
                     entry["mean_valence"], entry["mean_rating"],
                     round(entry["recent_share"] * 100, 1), evidence])
    return rows


def temporal_sheet(side):
    rows = [["Period", "Reviews", "Positive", "Neutral", "Negative", "Average rating",
             "Negative share %"]]
    for entry in side["temporal"]["series"]:
        rows.append([entry["bucket"], entry["total"], entry["positive"], entry["neutral"],
                     entry["negative"], entry["average_rating"],
                     round(entry["negative_ratio"] * 100, 1)])
    rows.append([])
    rows.append(["Reading", side["temporal"]["reading"]])
    return rows


def reviews_sheet(side):
    rows = [["Reviewer ID", "Reviewer", "Rating", "Relative time", "Approx date",
             "Months ago", "Period", "Sentiment", "Sentiment score", "Photos",
             "Owner response", "Review"]]
    for review in side["reviews"]:
        rows.append([review["reviewer_id"], review["reviewer"], review["rating"],
                     review["relative_time"], review["published_at"],
                     review["months_ago"], review["bucket"], review["sentiment"],
                     review["sentiment_score"], review["photo_count"],
                     review["owner_response"] or "", review["text"]])
    return rows


def dashboard_sheet(report):
    primary = report["primary"]
    kpis = primary["kpis"]
    rows = [
        ["QRIP review intelligence report"],
        ["Business", primary["label"]],
        ["Competitor", report.get("competitor", {}).get("label", "—")],
        ["Source", report["meta"]["source_label"]],
        ["Generated", report["meta"]["generated_at"]],
        [],
        ["Metric", "Value"],
        ["Net sentiment score", kpis["net_sentiment_score"]],
        ["Total reviews analysed", kpis["total_reviews"]],
        ["Coded statements", kpis["coded_units"]],
        ["Average rating", kpis["average_rating"]],
        ["Positive reviews", kpis["positive"]],
        ["Neutral reviews", kpis["neutral"]],
        ["Negative reviews", kpis["negative"]],
        ["Negative ratio", kpis["negative_ratio"]],
        ["Mean sentiment", kpis["mean_sentiment"]],
        ["Owner response rate", kpis["owner_response_rate"]],
        [],
        ["Dimension", "Score (1-10)", "Mentions", "Mean valence"],
    ]
    for entry in primary["dimensions"]:
        rows.append([entry["dimension"], entry["score"], entry.get("mentions", 0),
                     entry.get("mean_valence", 0)])
    return rows


def comparison_sheet(comparison):
    rows = [["Dimension", comparison["primary_label"], comparison["competitor_label"],
             "Gap", "Your mentions", "Their mentions"]]
    for entry in comparison["radar"]:
        rows.append([entry["dimension"], entry["primary"], entry["competitor"],
                     entry["gap"], entry["primary_mentions"], entry["competitor_mentions"]])
    rows.append([])
    rows.append(["Headline", comparison["headline"]])
    rows.append([])
    rows.append(["Adoption parameter", "Kind", "Your score", "Their score", "Gap",
                 "Recommendation", "Their customers say"])
    for entry in comparison["adoption_parameters"]:
        evidence = entry["evidence"]["text"] if entry.get("evidence") else ""
        rows.append([entry["parameter"], entry["kind"], entry["your_score"],
                     entry["their_score"], entry["gap"], entry["recommendation"],
                     evidence])
    return rows
