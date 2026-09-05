"""Contradiction detection and second-pass (model comparison) checks."""
from . import textproc as tp
from . import clustering as cl


def detect(codes, vectors, themes, sensitivity=0.5):
    """Find places where similar content is spoken about in opposing terms."""
    gap_needed = 1.25 - 0.8 * sensitivity      # 0.85 at sensitivity 0.5
    sim_needed = 0.34 - 0.14 * sensitivity     # 0.27 at sensitivity 0.5
    found = []

    for theme in themes:
        members = theme["member_idx"]
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                ia, ib = members[a], members[b]
                ca, cb = codes[ia], codes[ib]
                gap = abs(ca["valence"] - cb["valence"])
                if gap < gap_needed:
                    continue
                sim = tp.cosine(vectors[ia], vectors[ib])
                if sim < sim_needed:
                    continue
                cross = ca["participant_label"] != cb["participant_label"]
                severity = min(1.0, (sim * 1.6) * (gap / 2.0) * (1.25 if cross else 0.85) * 2.2)
                pos, neg = (ca, cb) if ca["valence"] > cb["valence"] else (cb, ca)
                if cross:
                    desc = (
                        pos["participant_label"] + " frames this positively — \""
                        + tp.truncate(pos["quote_text"], 150) + "\" — while "
                        + neg["participant_label"] + " reports the opposite: \""
                        + tp.truncate(neg["quote_text"], 150) + "\""
                    )
                else:
                    desc = (
                        pos["participant_label"] + " holds both positions within the "
                        "same account: \"" + tp.truncate(pos["quote_text"], 130)
                        + "\" against \"" + tp.truncate(neg["quote_text"], 130)
                        + "\" — an internal tension rather than a disagreement between cases."
                    )
                found.append({
                    "theme_id": theme.get("id"),
                    "theme_name": theme["name"],
                    "description": desc,
                    "severity": round(severity, 3),
                    "code_a_id": ca.get("id"),
                    "code_b_id": cb.get("id"),
                    "kind": "cross-case" if cross else "within-case",
                })

    # theme-level opposition: near-identical topics, opposite overall valence
    for i in range(len(themes)):
        for j in range(i + 1, len(themes)):
            ta, tb = themes[i], themes[j]
            sim = tp.cosine(ta.get("centroid", {}), tb.get("centroid", {}))
            gap = abs(ta["mean_valence"] - tb["mean_valence"])
            if sim >= 0.2 and gap >= 0.55:
                found.append({
                    "theme_id": ta.get("id"),
                    "theme_name": ta["name"],
                    "description": (
                        "Theme-level opposition: '" + ta["name"] + "' (valence "
                        + str(ta["mean_valence"]) + ") and '" + tb["name"] + "' (valence "
                        + str(tb["mean_valence"]) + ") describe overlapping material in "
                        "opposing terms. Consider whether the difference is contextual "
                        "(who, where, when) rather than substantive."
                    ),
                    "severity": round(min(1.0, sim * gap * 1.9), 3),
                    "code_a_id": None,
                    "code_b_id": None,
                    "kind": "theme-level",
                })

    found.sort(key=lambda c: -c["severity"])
    dedup, seen = [], set()
    for c in found:
        key = (c["code_a_id"], c["code_b_id"], c["theme_id"])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(c)
    return dedup[:60]


def compare_second_pass(codes, vectors, themes, threshold, primary_model, secondary_model):
    """Re-cluster under a perturbed configuration and report where readings diverge.

    This is the deterministic stand-in for a second coder: if a theme survives a
    different cut of the same data, it is more likely to be a property of the
    corpus than of the parameters.
    """
    alt_clusters = cl.cluster(vectors, threshold=min(0.9, threshold + 0.09), passes=1)
    alt_sets = [set(c) for c in alt_clusters]
    out = []
    for theme in themes:
        primary_set = set(theme["member_idx"])
        best, best_j = None, 0.0
        for alt in alt_sets:
            inter = len(primary_set & alt)
            if not inter:
                continue
            j = inter / len(primary_set | alt)
            if j > best_j:
                best, best_j = alt, j
        agreement = best_j >= 0.6
        if best is None:
            notes = ("The second pass did not reproduce this grouping at all; every "
                     "supporting code was absorbed elsewhere.")
        elif agreement:
            notes = None if best_j > 0.92 else (
                "Reproduced with " + str(int(round(best_j * 100))) + "% overlap; "
                + str(len(primary_set - best)) + " code(s) moved."
            )
        else:
            missing = len(primary_set - best)
            gained = len(best - primary_set)
            notes = (
                "Only " + str(int(round(best_j * 100))) + "% overlap at the tighter cut: "
                + str(missing) + " code(s) split away and " + str(gained)
                + " unrelated code(s) joined. The boundary of this theme is unstable — "
                "check it by hand before reporting."
            )
        out.append({
            "theme_id": theme.get("id"),
            "theme_name": theme["name"],
            "primary_model": primary_model,
            "secondary_model": secondary_model,
            "agreement": bool(agreement),
            "disagreement_notes": notes,
            "overlap": round(best_j, 3),
        })
    return out
