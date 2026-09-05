"""Grounded theory: open -> axial -> selective coding, saturation, memos.

Follows the Strauss & Corbin paradigm model for axial coding and reports a
theoretical saturation curve computed over the order transcripts were added.
"""
from collections import Counter, defaultdict

from .. import clustering as cl
from .. import coding
from .. import lexicons as lx
from .. import textproc as tp

NAME = "Grounded theory"
FRAMEWORK = "Strauss & Corbin paradigm model with constant comparison"

PARADIGM_ORDER = [
    ("causal_conditions", "Causal conditions"),
    ("phenomenon", "Phenomenon"),
    ("context", "Context"),
    ("intervening_conditions", "Intervening conditions"),
    ("strategies", "Action / interaction strategies"),
    ("consequences", "Consequences"),
]


def run(ctx):
    codes = ctx["codes"]
    themes = ctx["themes"]
    idf = ctx["idf"]

    open_coding = _open_coding(codes)
    categories = _axial(ctx, themes, codes, idf)
    selective = _selective(categories, themes, codes)
    saturation = _saturation(ctx)
    memos = _memos(ctx, categories, selective, saturation)
    comparisons = _constant_comparison(themes, codes)

    return {
        "methodology": "grounded_theory",
        "name": NAME,
        "framework": FRAMEWORK,
        "open_coding": open_coding,
        "axial_categories": categories,
        "selective_coding": selective,
        "saturation": saturation,
        "memos": memos,
        "constant_comparison": comparisons,
    }


def _open_coding(codes):
    labels = Counter(c["label"] for c in codes)
    in_vivo = []
    for code in codes:
        text = code["quote_text"]
        if 4 <= len(text.split()) <= 12 and code["confidence"] > 0.6:
            in_vivo.append({"participant": code["participant_label"],
                            "phrase": tp.truncate(text, 90)})
    return {
        "code_count": len(codes),
        "distinct_labels": len(labels),
        "most_frequent": [{"label": lab, "count": n} for lab, n in labels.most_common(12)],
        "in_vivo_codes": in_vivo[:10],
        "note": ("Open coding fractures the data line by line. Labels repeat where "
                 "participants converge on the same object of concern."),
    }


def _axial(ctx, themes, codes, idf):
    """Group themes into higher-order categories and fill the paradigm model."""
    if not themes:
        return []
    centroids = [t.get("centroid", {}) for t in themes]
    groups = cl.cluster(centroids, threshold=max(0.14, ctx["controls"]["similarity_threshold"] * 0.5),
                        passes=1)
    taken = set()
    categories = []
    for gi, group in enumerate(groups):
        member_themes = [themes[i] for i in group]
        member_codes = [codes[i] for t in member_themes for i in t["member_idx"]]
        if not member_codes:
            continue
        name = cl.name_theme(member_codes, idf, taken)
        paradigm = {}
        for key, label in PARADIGM_ORDER:
            cues = lx.GT_PARADIGM[key]
            hits = []
            for c in member_codes:
                score = coding.count_hits(c["quote_text"], cues)
                if score:
                    hits.append((score * c["confidence"], c))
            hits.sort(key=lambda h: -h[0])
            paradigm[key] = {
                "label": label,
                "evidence": [{
                    "participant": c["participant_label"],
                    "quote": tp.truncate(c["quote_text"], 200),
                } for _, c in hits[:3]],
                "count": len(hits),
            }
        participants = sorted({c["participant_label"] for c in member_codes})
        density = sum(1 for k, _ in PARADIGM_ORDER if paradigm[k]["count"] > 0)
        categories.append({
            "name": name,
            "themes": [t["name"] for t in member_themes],
            "theme_ids": [t.get("id") for t in member_themes],
            "code_count": len(member_codes),
            "participants": participants,
            "paradigm": paradigm,
            "density": density,
            "centrality": round(sum(t["coverage"] for t in member_themes), 4),
            "properties": _properties(member_codes),
            "dimensions": _dimensions(member_codes),
            "order_idx": gi,
        })
    categories.sort(key=lambda c: -c["centrality"])
    return categories


def _properties(member_codes):
    """Properties of a category = the recurring attributes participants name."""
    phrases = Counter(c["phrase"] for c in member_codes)
    return [{"property": tp.titlecase(p), "count": n} for p, n in phrases.most_common(6)]


def _dimensions(member_codes):
    """Dimensional range: where along each property the accounts sit."""
    vals = [c["valence"] for c in member_codes]
    emotions = Counter(c["emotion"] for c in member_codes if c["emotion"] != "neutral")
    lo, hi = (min(vals), max(vals)) if vals else (0, 0)
    return {
        "valence_range": [round(lo, 2), round(hi, 2)],
        "affective_span": [e for e, _ in emotions.most_common(4)],
        "note": ("Accounts range from " + ("strongly negative" if lo < -0.4 else "mildly negative"
                 if lo < 0 else "neutral") + " to " + ("strongly positive" if hi > 0.4 else
                 "mildly positive" if hi > 0 else "neutral") + " on this category."),
    }


def _selective(categories, themes, codes):
    if not categories:
        return {"core_category": None, "storyline": "Not enough data to integrate a core category.",
                "candidates": []}
    ranked = sorted(categories, key=lambda c: -(c["centrality"] * (1 + 0.12 * c["density"])
                                                * (1 + 0.08 * len(c["participants"]))))
    core = ranked[0]
    others = ranked[1:4]
    consequences = core["paradigm"]["consequences"]["evidence"]
    strategies = core["paradigm"]["strategies"]["evidence"]
    storyline = (
        "The core category is '" + core["name"] + "', present for "
        + str(len(core["participants"])) + " participants across " + str(core["code_count"])
        + " coded segments. It integrates " + str(len(core["themes"])) + " theme(s) and "
        "connects to " + ", ".join("'" + o["name"] + "'" for o in others) + ". "
        + ("Participants respond to it primarily through the strategies they improvise — "
           + tp.truncate(strategies[0]["quote"], 120) + " — " if strategies else "")
        + ("and the consequence they report is " + tp.truncate(consequences[0]["quote"], 120) + "."
           if consequences else "with consequences that are not yet well evidenced in this corpus.")
    )
    return {
        "core_category": core["name"],
        "storyline": storyline,
        "candidates": [{"name": c["name"], "centrality": c["centrality"], "density": c["density"],
                        "participants": len(c["participants"])} for c in ranked[:5]],
        "integration_note": ("A core category should account for variation, not just "
                            "frequency. Check the negative cases before settling on it."),
    }


def _saturation(ctx):
    """New-code rate per transcript, in upload order."""
    by_transcript = defaultdict(list)
    for code in ctx["codes"]:
        by_transcript[code["transcript_id"]].append(code)
    seen = set()
    points = []
    saturated_at = None
    for order, transcript in enumerate(ctx["transcripts"], start=1):
        tcodes = by_transcript.get(transcript["id"], [])
        concepts = {c["phrase"] for c in tcodes}
        new = concepts - seen
        seen |= concepts
        rate = (len(new) / len(concepts)) if concepts else 0.0
        points.append({
            "order": order,
            "transcript": transcript["participant_label"],
            "concepts": len(concepts),
            "new_concepts": len(new),
            "cumulative": len(seen),
            "new_rate": round(rate, 3),
        })
        if saturated_at is None and order >= 3 and rate <= 0.12:
            saturated_at = order
    if saturated_at:
        verdict = ("New concepts fall below 12% of each interview from transcript "
                   + str(saturated_at) + " onward — provisional saturation.")
    elif len(points) < 4:
        verdict = "Too few interviews to speak about saturation; the curve is still climbing."
    else:
        verdict = ("Each new interview is still contributing fresh concepts. Sampling is "
                   "not saturated; continue theoretical sampling.")
    return {"points": points, "saturated_at": saturated_at, "verdict": verdict}


def _memos(ctx, categories, selective, saturation):
    memos = []
    if categories:
        top = categories[0]
        memos.append({
            "title": "Memo — emerging core: " + top["name"],
            "text": ("Written after coding " + str(len(ctx["transcripts"])) + " transcripts. "
                     + top["name"] + " keeps re-appearing across cases with the properties "
                     + ", ".join(p["property"] for p in top["properties"][:3])
                     + ". What varies is not whether participants encounter it but how much "
                       "work they must do to get around it. That variation is the dimension "
                       "worth sampling on next."),
        })
    memos.append({
        "title": "Memo — sampling",
        "text": saturation["verdict"] + " Theoretical sampling should now target the "
                "conditions under which the core category does not hold.",
    })
    negatives = [c for c in ctx["codes"] if c.get("is_negative_case")]
    if negatives:
        memos.append({
            "title": "Memo — negative cases",
            "text": (str(len(negatives)) + " segments run against their theme. "
                     + negatives[0]["participant_label"] + " in particular reports the "
                     "opposite pattern: \"" + tp.truncate(negatives[0]["quote_text"], 180)
                     + "\" Any theory built here has to accommodate that, not explain it away."),
        })
    return memos


def _constant_comparison(themes, codes):
    out = []
    for i in range(min(len(themes), 6)):
        for j in range(i + 1, min(len(themes), 6)):
            a, b = themes[i], themes[j]
            sim = tp.cosine(a.get("centroid", {}), b.get("centroid", {}))
            if sim < 0.08:
                continue
            shared = sorted(set(tp.top_terms(a.get("centroid", {}), 10))
                            & set(tp.top_terms(b.get("centroid", {}), 10)))
            out.append({
                "pair": [a["name"], b["name"]],
                "similarity": round(sim, 3),
                "note": ("Shared vocabulary " + (", ".join(shared[:4]) if shared else "is thin")
                         + "; valence differs by "
                         + str(round(abs(a["mean_valence"] - b["mean_valence"]), 2))
                         + ". Compare incident by incident before deciding whether these are "
                           "one category or two."),
            })
    out.sort(key=lambda o: -o["similarity"])
    return out[:8]
