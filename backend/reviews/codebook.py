"""The codebook workbook — the deliverable function 1 produces and function 2
reads. Five sheets: Themes, Codes, Quotations, Confidence Scores, Audit Log.
"""
from datetime import datetime, timezone

import exports


def build(codes, themes, contradictions=None, audit=None, meta=None):
    contradictions = contradictions or []
    meta = meta or {}
    sheets = [
        ("Themes", _themes_sheet(themes)),
        ("Codes", _codes_sheet(codes)),
        ("Quotations", _quotations_sheet(codes)),
        ("Confidence Scores", _confidence_sheet(themes, contradictions)),
        ("Audit Log", _audit_sheet(audit, meta)),
    ]
    return exports.write_xlsx(sheets)


def _themes_sheet(themes):
    rows = [["Theme", "Description", "Status", "Confidence", "Coverage",
             "Participants", "Evidence Count", "Alternative Interpretation"]]
    for theme in themes:
        rows.append([
            theme["theme"], theme.get("description", ""), theme.get("status", ""),
            theme.get("confidence", 0), theme.get("coverage", 0),
            len(theme.get("participants", [])), theme.get("evidence_count", 0),
            theme.get("alternative_interpretation", ""),
        ])
    return rows


def _codes_sheet(codes):
    rows = [["Code", "Participant", "Quote", "Literal Meaning", "Emotion", "Intent",
             "Confidence", "Negative Case", "Theme(s)"]]
    for code in codes:
        rows.append([
            code["code"], code["participant"], code["quote"],
            code.get("literal_meaning", ""), code.get("emotion", ""),
            code.get("intent", ""), code.get("confidence", 0),
            "Yes" if code.get("negative_case") else "No",
            "; ".join(code.get("themes", [])),
        ])
    return rows


def _quotations_sheet(codes):
    rows = [["Theme", "Participant", "Quote", "Code"]]
    for code in codes:
        for theme in code.get("themes") or [""]:
            if not theme:
                continue
            rows.append([theme, code["participant"], code["quote"], code["code"]])
    return rows


def _confidence_sheet(themes, contradictions):
    counts = {}
    for item in contradictions:
        name = item.get("theme")
        if name:
            counts[name] = counts.get(name, 0) + 1
    rows = [["Theme", "Confidence", "Coverage", "Contradiction Count"]]
    for theme in themes:
        rows.append([theme["theme"], theme.get("confidence", 0),
                     theme.get("coverage", 0), counts.get(theme["theme"], 0)])
    return rows


def _audit_sheet(audit, meta):
    rows = [["Timestamp", "Action", "Entity Type", "Entity ID", "Details"]]
    for entry in audit or []:
        rows.append([entry.get("timestamp", ""), entry.get("action", ""),
                     entry.get("entity_type", ""), entry.get("entity_id", ""),
                     str(entry.get("details", ""))])
    if not audit:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        rows.append([stamp, "analyze", "review_job", meta.get("job_id", ""),
                     str({"engine": meta.get("engine"), "reviews": meta.get("reviews")})])
    return rows
