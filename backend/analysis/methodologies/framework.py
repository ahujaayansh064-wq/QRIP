"""Framework analysis (Ritchie & Spencer / Gale et al.).

Five stages, ending in the framework matrix: one row per case, one column per
category, each cell a summary of that participant's data indexed to quotations.
"""
from collections import defaultdict

from .. import coding
from .. import lexicons as lx
from .. import textproc as tp

NAME = "Framework analysis"
FRAMEWORK = "Ritchie & Spencer five-stage framework method"


def run(ctx):
    codes = ctx["codes"]
    categories = _build_framework(ctx)
    indexed = _index(codes, categories)
    matrix = _chart(ctx, categories, indexed)
    mapping = _map_and_interpret(ctx, categories, indexed, matrix)
    return {
        "methodology": "framework",
        "name": NAME,
        "framework": FRAMEWORK,
        "stages": _stages(ctx, categories, indexed, matrix),
        "categories": categories,
        "matrix": matrix,
        "mapping": mapping,
        "gaps": _gaps(matrix, categories),
    }


def _build_framework(ctx):
    """A-priori dimensions plus emergent categories from the themes."""
    categories = []
    for name, cues in lx.FRAMEWORK_DIMENSIONS:
        categories.append({"name": name, "source": "a priori", "cues": cues,
                           "definition": "Indexed where participants " + cues[0] + "-type "
                                         "language appears."})
    for theme in ctx["themes"][:6]:
        if theme["status"] == "candidate":
            continue
        terms = tp.top_terms(theme.get("centroid", {}), 6)
        categories.append({
            "name": theme["name"],
            "source": "emergent",
            "cues": terms,
            "theme_id": theme.get("id"),
            "definition": "Emergent from the coded data: " + tp.truncate(
                theme.get("description", ""), 160),
        })
    return categories


def _index(codes, categories):
    """Stage 3 — index every coded segment against the framework."""
    indexed = defaultdict(lambda: defaultdict(list))  # participant -> category -> codes
    for code in codes:
        text = code["quote_text"].lower()
        stems = set(code["stems"])
        for cat in categories:
            if cat["source"] == "a priori":
                score = coding.count_hits(text, cat["cues"])
            else:
                score = len(stems & set(cat["cues"]))
            if score:
                indexed[code["participant_label"]][cat["name"]].append((score, code))
    return indexed


def _chart(ctx, categories, indexed):
    """Stage 4 — chart the matrix."""
    participants = sorted({c["participant_label"] for c in ctx["codes"]})
    columns = [c["name"] for c in categories]
    rows = []
    for participant in participants:
        cells = []
        for cat in categories:
            entries = sorted(indexed.get(participant, {}).get(cat["name"], []),
                             key=lambda e: -e[0] * e[1]["confidence"])
            if not entries:
                cells.append({"summary": "", "quotes": [], "count": 0, "valence": None})
                continue
            picked = [e[1] for e in entries[:3]]
            valence = sum(c["valence"] for c in picked) / len(picked)
            cells.append({
                "summary": _cell_summary(picked, valence),
                "quotes": [{"text": tp.truncate(c["quote_text"], 220),
                            "code": c["label"],
                            "confidence": c["confidence"]} for c in picked],
                "count": len(entries),
                "valence": round(valence, 2),
            })
        rows.append({
            "participant": participant,
            "cells": cells,
            "filled": sum(1 for c in cells if c["count"]),
        })
    return {"columns": columns, "rows": rows,
            "sources": [c["source"] for c in categories]}


def _cell_summary(picked, valence):
    tone = "positive" if valence > 0.15 else ("negative" if valence < -0.15 else "mixed")
    lead = picked[0]
    extra = (" Also raises " + picked[1]["phrase"] + "." if len(picked) > 1 else "")
    return (tone.capitalize() + " account centred on " + lead["phrase"] + ": "
            + tp.truncate(lead["literal_meaning"], 140) + extra)


def _stages(ctx, categories, indexed, matrix):
    filled = sum(r["filled"] for r in matrix["rows"])
    total_cells = len(matrix["rows"]) * len(matrix["columns"]) or 1
    return [
        {"stage": 1, "name": "Familiarisation",
         "output": (str(len(ctx["transcripts"])) + " transcripts read and segmented into "
                    + str(ctx["unit_count"]) + " meaning units.")},
        {"stage": 2, "name": "Identifying a thematic framework",
         "output": (str(sum(1 for c in categories if c["source"] == "a priori"))
                    + " a-priori dimensions retained and "
                    + str(sum(1 for c in categories if c["source"] == "emergent"))
                    + " emergent categories added from the data.")},
        {"stage": 3, "name": "Indexing",
         "output": (str(sum(len(v) for cats in indexed.values() for v in cats.values()))
                    + " segment-to-category assignments made; segments may index to more "
                      "than one category.")},
        {"stage": 4, "name": "Charting",
         "output": (str(len(matrix["rows"])) + " x " + str(len(matrix["columns"]))
                    + " matrix built; " + str(int(round(100.0 * filled / total_cells)))
                    + "% of cells carry data.")},
        {"stage": 5, "name": "Mapping and interpretation",
         "output": "Patterns read down columns (across cases) and along rows (within case)."},
    ]


def _map_and_interpret(ctx, categories, indexed, matrix):
    out = []
    for ci, cat in enumerate(categories):
        column = [(row["participant"], row["cells"][ci]) for row in matrix["rows"]]
        present = [p for p, cell in column if cell["count"]]
        valences = [cell["valence"] for _, cell in column if cell["valence"] is not None]
        if not present:
            out.append({"category": cat["name"], "coverage": 0,
                        "pattern": "No data indexed here — either the topic did not arise "
                                   "or the topic guide did not reach for it."})
            continue
        mean_v = sum(valences) / len(valences)
        spread = (max(valences) - min(valences)) if len(valences) > 1 else 0
        if spread > 0.8:
            pattern = ("Strongly divided: accounts run from " + str(round(min(valences), 2))
                       + " to " + str(round(max(valences), 2)) + " valence. Look for what "
                       "distinguishes the cases at each end.")
        elif mean_v < -0.2:
            pattern = ("Consistently negative across " + str(len(present))
                       + " cases — the most stable pattern in this column.")
        elif mean_v > 0.2:
            pattern = ("Consistently positive across " + str(len(present)) + " cases.")
        else:
            pattern = ("Mixed and moderate; no single reading dominates the column.")
        out.append({
            "category": cat["name"],
            "source": cat["source"],
            "coverage": round(len(present) / max(len(matrix["rows"]), 1), 3),
            "present_in": present,
            "mean_valence": round(mean_v, 2),
            "pattern": pattern,
        })
    out.sort(key=lambda o: -o["coverage"])
    return out


def _gaps(matrix, categories):
    gaps = []
    for ci, cat in enumerate(categories):
        empty = [row["participant"] for row in matrix["rows"] if not row["cells"][ci]["count"]]
        if empty and len(empty) < len(matrix["rows"]):
            gaps.append({
                "category": cat["name"],
                "missing_for": empty,
                "note": ("Not evidenced for " + ", ".join(empty)
                         + ". Follow up in the next round of interviews before treating "
                           "the column as complete."),
            })
    return gaps[:10]
