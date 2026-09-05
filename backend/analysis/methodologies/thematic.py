"""Reflexive thematic analysis (Braun & Clarke, six phases)."""
from collections import Counter

from .. import clustering as cl
from .. import textproc as tp

NAME = "Thematic analysis"
FRAMEWORK = "Braun & Clarke (2006, 2019) reflexive thematic analysis"


def run(ctx):
    codes = ctx["codes"]
    themes = ctx["themes"]
    vectors = ctx["vectors"]
    idf = ctx["idf"]
    threshold = ctx["controls"]["similarity_threshold"]

    theme_payload = []
    for theme in themes:
        members = theme["member_idx"]
        member_codes = [codes[i] for i in members]
        member_codes_sorted = sorted(member_codes, key=lambda c: -c["confidence"])
        subs = cl.subthemes(member_codes, vectors, members, idf, threshold)
        exemplar = member_codes_sorted[0]
        counter_cases = [c for c in member_codes if c.get("is_negative_case")]
        theme_payload.append({
            "id": theme.get("id"),
            "name": theme["name"],
            "status": theme["status"],
            "confidence": theme["confidence"],
            "coverage": theme["coverage"],
            "participant_count": theme["participant_count"],
            "quote_count": len(member_codes),
            "subthemes": subs,
            "defining_quote": {
                "participant": exemplar["participant_label"],
                "text": tp.truncate(exemplar["quote_text"], 320),
                "confidence": exemplar["confidence"],
            },
            "boundary_note": _boundary_note(theme, subs, counter_cases),
            "counter_cases": [{
                "participant": c["participant_label"],
                "text": tp.truncate(c["quote_text"], 220),
            } for c in counter_cases[:3]],
        })

    nodes = [{"id": t.get("id") or t["name"], "label": t["name"], "size": t["quote_count"],
              "status": t["status"]} for t in theme_payload]
    edges = []
    for i in range(len(themes)):
        for j in range(i + 1, len(themes)):
            sim = tp.cosine(themes[i].get("centroid", {}), themes[j].get("centroid", {}))
            if sim >= threshold * 0.5:
                edges.append({
                    "source": themes[i].get("id") or themes[i]["name"],
                    "target": themes[j].get("id") or themes[j]["name"],
                    "weight": round(sim, 3),
                })

    phases = _phases(ctx, theme_payload)
    keyness = _keyness(codes, idf)

    return {
        "methodology": "thematic",
        "name": NAME,
        "framework": FRAMEWORK,
        "phases": phases,
        "themes": theme_payload,
        "thematic_map": {"nodes": nodes, "edges": edges},
        "keyness": keyness,
        "reflexive_prompts": [
            "Which of these themes did you expect to find before you read the data?",
            "Whose account is doing the most work in the theme with the fewest participants?",
            "Where have you smoothed over disagreement to make a theme hold together?",
        ],
    }


def _boundary_note(theme, subs, counter_cases):
    bits = []
    if len(subs) >= 2:
        bits.append("Splits cleanly into " + str(len(subs))
                    + " sub-patterns at a tighter cut; consider promoting one to a theme "
                      "in its own right.")
    if counter_cases:
        bits.append(str(len(counter_cases)) + " segment(s) run against the grain of the "
                    "theme and are retained as counter-cases rather than discarded.")
    if theme["participant_count"] <= 2:
        bits.append("Narrow participant base — currently closer to a case-level "
                    "observation than a shared theme.")
    if theme["cohesion"] < 0.25:
        bits.append("Low internal cohesion: the material is held together loosely and may "
                    "be a container for several ideas.")
    return " ".join(bits) or "Boundaries are stable: coherent internally and distinct " \
                             "from neighbouring themes."


def _phases(ctx, theme_payload):
    codes = ctx["codes"]
    n_units = ctx["unit_count"]
    n_transcripts = len(ctx["transcripts"])
    confirmed = [t for t in theme_payload if t["status"] == "confirmed"]
    return [
        {"phase": 1, "name": "Familiarisation",
         "output": (str(n_transcripts) + " transcripts segmented into " + str(n_units)
                    + " meaning units; speaker turns separated so interviewer prompts "
                      "are held as context rather than coded."),
         "stat": n_units},
        {"phase": 2, "name": "Generating initial codes",
         "output": (str(len(codes)) + " codes generated across the corpus, each tied to a "
                    "verbatim segment with an emotion and intent reading and a confidence "
                    "score."),
         "stat": len(codes)},
        {"phase": 3, "name": "Searching for themes",
         "output": ("Codes grouped by semantic similarity at a cut of "
                    + str(ctx["controls"]["similarity_threshold"]) + ", yielding "
                    + str(len(theme_payload)) + " candidate themes."),
         "stat": len(theme_payload)},
        {"phase": 4, "name": "Reviewing themes",
         "output": (str(len(confirmed)) + " themes meet the support thresholds ("
                    + str(ctx["controls"]["min_supporting_quotations"]) + "+ quotations, "
                    + str(ctx["controls"]["participant_frequency_threshold"])
                    + "+ participants); the rest are held as candidates for review."),
         "stat": len(confirmed)},
        {"phase": 5, "name": "Defining and naming",
         "output": ("Each theme carries a definition, a defining quotation, an explicit "
                    "alternative reading and a boundary note."),
         "stat": len(theme_payload)},
        {"phase": 6, "name": "Producing the report",
         "output": ("Exportable as .docx narrative report, .xlsx codebook and .pdf "
                    "summary, with the full audit trail attached."),
         "stat": 3},
    ]


def _keyness(codes, idf):
    counts = Counter()
    for code in codes:
        counts.update(set(code["stems"]))
    scored = [(term, n, round(n * idf.get(term, 1.0), 2)) for term, n in counts.items() if n > 1]
    scored.sort(key=lambda s: -s[2])
    return [{"term": t, "count": n, "keyness": k} for t, n, k in scored[:24]]
