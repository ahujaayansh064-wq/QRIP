"""Content analysis — manifest counts plus a latent interpretive layer.

Produces a coding scheme, a category-by-case frequency matrix, KWIC
concordances for the highest-keyness terms, and coding-reliability diagnostics.
"""
from collections import Counter, defaultdict

from .. import lexicons as lx
from .. import textproc as tp

NAME = "Content analysis"
FRAMEWORK = "Manifest frequency counts with a latent (interpretive) layer"


def run(ctx):
    codes = ctx["codes"]
    units = ctx["units"]
    scheme = _scheme(ctx)
    manifest = _manifest(ctx)
    matrix = _matrix(ctx, scheme)
    return {
        "methodology": "content",
        "name": NAME,
        "framework": FRAMEWORK,
        "scheme": scheme,
        "manifest": manifest,
        "matrix": matrix,
        "latent": _latent(ctx, scheme, matrix),
        "kwic": _kwic(ctx, manifest),
        "reliability": _reliability(codes, units),
    }


def _scheme(ctx):
    scheme = []
    for name, terms in lx.CONTENT_CATEGORIES.items():
        scheme.append({
            "category": tp.titlecase(name),
            "key": name,
            "type": "a priori",
            "terms": terms,
        })
    for theme in ctx["themes"][:5]:
        if theme["status"] == "candidate":
            continue
        terms = tp.top_terms(theme.get("centroid", {}), 8)
        scheme.append({
            "category": theme["name"],
            "key": "emergent_" + str(theme.get("order_idx", 0)),
            "type": "emergent",
            "terms": terms,
            "theme_id": theme.get("id"),
        })
    return scheme


def _manifest(ctx):
    all_tokens = []
    doc_stems = []
    for unit in ctx["units"]:
        toks = tp.content_tokens(unit["text"])
        all_tokens.extend(toks)
        doc_stems.append(set(tp.stems(unit["text"])))
    counts = Counter(all_tokens)
    idf = ctx["idf"]
    df = Counter()
    for doc in doc_stems:
        df.update(doc)
    rows = []
    for word, count in counts.most_common(200):
        s = tp.stem(word)
        rows.append({
            "term": word,
            "stem": s,
            "count": count,
            "documents": df.get(s, 0),
            "keyness": round(count * idf.get(s, 1.0), 2),
        })
    rows.sort(key=lambda r: -r["keyness"])
    total_words = sum(len(tp.tokenize(u["text"])) for u in ctx["units"])
    return {
        "total_words": total_words,
        "content_words": len(all_tokens),
        "unique_terms": len(counts),
        "type_token_ratio": round(len(counts) / max(len(all_tokens), 1), 4),
        "top_terms": rows[:30],
    }


def _matrix(ctx, scheme):
    participants = sorted({c["participant_label"] for c in ctx["codes"]})
    per = defaultdict(lambda: Counter())
    examples = defaultdict(dict)
    for code in ctx["codes"]:
        stems = set(code["stems"])
        low = " " + code["quote_text"].lower() + " "
        for cat in scheme:
            if cat["type"] == "a priori":
                hits = sum(1 for term in cat["terms"]
                           if " " + term + " " in low or tp.stem(term) in stems)
            else:
                hits = len(stems & set(cat["terms"]))
            if hits:
                per[code["participant_label"]][cat["key"]] += hits
                examples[cat["key"]].setdefault(
                    code["participant_label"], tp.truncate(code["quote_text"], 180))
    columns = [c["category"] for c in scheme]
    rows = []
    for participant in participants:
        counts = [per[participant].get(c["key"], 0) for c in scheme]
        rows.append({"participant": participant, "counts": counts, "total": sum(counts)})
    totals = [sum(r["counts"][i] for r in rows) for i in range(len(columns))]
    return {
        "columns": columns,
        "types": [c["type"] for c in scheme],
        "rows": rows,
        "totals": totals,
        "examples": {c["category"]: examples.get(c["key"], {}) for c in scheme},
    }


def _latent(ctx, scheme, matrix):
    out = []
    grand = sum(matrix["totals"]) or 1
    for i, cat in enumerate(scheme):
        total = matrix["totals"][i]
        if not total:
            continue
        share = total / grand
        spread = sum(1 for row in matrix["rows"] if row["counts"][i] > 0)
        relevant = [c for c in ctx["codes"]
                    if any(t in set(c["stems"]) for t in map(tp.stem, cat["terms"]))]
        valence = (sum(c["valence"] for c in relevant) / len(relevant)) if relevant else 0.0
        emotions = Counter(c["emotion"] for c in relevant if c["emotion"] != "neutral")
        top_em = emotions.most_common(1)[0][0] if emotions else "no marked affect"
        out.append({
            "category": cat["category"],
            "type": cat["type"],
            "count": total,
            "share": round(share, 4),
            "participants": spread,
            "mean_valence": round(valence, 3),
            "interpretation": (
                "Manifest frequency puts " + cat["category"].lower() + " at "
                + str(int(round(share * 100))) + "% of category hits across "
                + str(spread) + " participants. Latently, it carries " + top_em
                + " and a mean valence of " + str(round(valence, 2)) + " — "
                + ("the counts and the feeling point the same way."
                   if (valence < -0.2 and share > 0.1) or (valence > 0.2 and share > 0.1)
                   else "frequency alone would overstate how settled this is.")
            ),
        })
    out.sort(key=lambda o: -o["count"])
    return out


def _kwic(ctx, manifest):
    keys = [r["term"] for r in manifest["top_terms"][:8]]
    out = []
    for term in keys:
        lines = []
        for unit in ctx["units"]:
            toks = unit["text"].split()
            lows = [t.lower().strip(".,;:!?\"'()") for t in toks]
            for i, tok in enumerate(lows):
                if tok == term:
                    left = " ".join(toks[max(0, i - 7):i])
                    right = " ".join(toks[i + 1:i + 8])
                    lines.append({
                        "participant": unit["participant_label"],
                        "left": left, "keyword": toks[i], "right": right,
                    })
                    break
            if len(lines) >= 6:
                break
        if lines:
            out.append({"term": term, "lines": lines})
    return out


def _reliability(codes, units):
    if not codes:
        return {"coded_units": 0, "note": "No codes generated."}
    confs = [c["confidence"] for c in codes]
    mean_conf = sum(confs) / len(confs)
    ambiguous = [c for c in codes if len(c["alternative_interpretations"]) > 1]
    low_conf = [c for c in codes if c["confidence"] < 0.5]
    coverage = len(codes) / max(len(units), 1)
    return {
        "coded_units": len(codes),
        "total_units": len(units),
        "coverage": round(coverage, 3),
        "mean_confidence": round(mean_conf, 3),
        "ambiguous_units": len(ambiguous),
        "low_confidence_units": len(low_conf),
        "note": (
            "Every unit is coded by one deterministic pass, so this is not inter-coder "
            "reliability. Treat it as a map of where a second human coder should look: "
            "the " + str(len(low_conf)) + " low-confidence and " + str(len(ambiguous))
            + " multiply-interpretable units first."
        ),
    }
