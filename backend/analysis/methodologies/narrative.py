"""Narrative analysis — structural (Labov), plot shape and positioning.

Each case is read as a story: orientation, complicating action, evaluation,
resolution, coda; plus turning points, the shape of the valence line, and how
much agency the teller claims.
"""
from collections import Counter, defaultdict

from .. import coding
from .. import lexicons as lx
from .. import textproc as tp

NAME = "Narrative analysis"
FRAMEWORK = "Labov & Waletzky structural model with plot-shape and positioning reading"

ELEMENTS = ["orientation", "complication", "evaluation", "resolution", "coda"]


def run(ctx):
    by_participant = defaultdict(list)
    for code in ctx["codes"]:
        by_participant[code["participant_label"]].append(code)

    narratives = []
    for participant in sorted(by_participant):
        pcodes = sorted(by_participant[participant], key=lambda c: (c["turn_idx"], c["idx"]))
        narratives.append(_narrative(participant, pcodes))

    return {
        "methodology": "narrative",
        "name": NAME,
        "framework": FRAMEWORK,
        "narratives": narratives,
        "cross_narrative": _cross(narratives),
    }


def _narrative(participant, pcodes):
    n = len(pcodes)
    arc = {e: [] for e in ELEMENTS}
    for i, code in enumerate(pcodes):
        position = i / max(n - 1, 1)
        scores = {}
        for element in ELEMENTS:
            hits = coding.count_hits(code["quote_text"], lx.NARRATIVE_CUES[element])
            scores[element] = hits * 1.0
        # positional prior: stories move through the elements in order
        priors = {
            "orientation": max(0.0, 1.0 - abs(position - 0.05) * 2.2),
            "complication": max(0.0, 1.0 - abs(position - 0.35) * 2.0),
            "evaluation": max(0.0, 1.0 - abs(position - 0.55) * 2.0),
            "resolution": max(0.0, 1.0 - abs(position - 0.82) * 2.2),
            "coda": max(0.0, 1.0 - abs(position - 0.97) * 2.6),
        }
        if abs(code["valence"]) > 0.35:
            scores["evaluation"] += 0.6
        if code["valence"] < -0.4:
            scores["complication"] += 0.5
        if code["valence"] > 0.35:
            scores["resolution"] += 0.35
        total = {e: scores[e] + priors[e] for e in ELEMENTS}
        element = max(total, key=total.get)
        arc[element].append({
            "quote": tp.truncate(code["quote_text"], 260),
            "position": round(position, 3),
            "valence": code["valence"],
            "emotion": code["emotion"],
        })

    series = [{"i": i, "valence": c["valence"], "emotion": c["emotion"],
               "quote": tp.truncate(c["quote_text"], 120)} for i, c in enumerate(pcodes)]
    turning_points = _turning_points(pcodes)
    agency = _agency(pcodes)
    plot = _plot_type(pcodes)
    temporal = _temporal(pcodes)

    return {
        "participant": participant,
        "arc": [{"element": e, "segments": arc[e][:4], "count": len(arc[e])} for e in ELEMENTS],
        "valence_series": series,
        "turning_points": turning_points,
        "agency": agency,
        "plot_type": plot,
        "temporal_markers": temporal,
        "summary": _summary(participant, plot, agency, turning_points, arc),
    }


def _turning_points(pcodes):
    points = []
    for i in range(1, len(pcodes)):
        delta = pcodes[i]["valence"] - pcodes[i - 1]["valence"]
        if abs(delta) >= 0.7:
            points.append({
                "index": i,
                "delta": round(delta, 3),
                "direction": "upturn" if delta > 0 else "downturn",
                "before": tp.truncate(pcodes[i - 1]["quote_text"], 150),
                "after": tp.truncate(pcodes[i]["quote_text"], 150),
            })
    points.sort(key=lambda p: -abs(p["delta"]))
    return points[:4]


def _agency(pcodes):
    active = passive = 0
    for code in pcodes:
        active += coding.count_hits(code["quote_text"], lx.AGENCY_ACTIVE)
        passive += coding.count_hits(code["quote_text"], lx.AGENCY_PASSIVE)
    total = active + passive
    ratio = (active / total) if total else 0.5
    if total == 0:
        note = "Agency is not grammatically marked either way in this account."
    elif ratio > 0.65:
        note = ("The teller positions themselves as the actor: things are done, chosen, "
                "pushed for.")
    elif ratio < 0.35:
        note = ("The teller is positioned as the one things happen to; the grammar itself "
                "carries the powerlessness.")
    else:
        note = "Agency alternates — claimed in some episodes, surrendered in others."
    return {"active": active, "passive": passive, "ratio": round(ratio, 3), "note": note}


def _plot_type(pcodes):
    if len(pcodes) < 3:
        return {"type": "fragment", "slope": 0.0,
                "note": "Too little narrative material to read a shape."}
    n = len(pcodes)
    xs = list(range(n))
    ys = [c["valence"] for c in pcodes]
    mx = sum(xs) / n
    my = sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs) or 1.0
    slope = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / denom
    first = sum(ys[: n // 3]) / max(n // 3, 1)
    middle = sum(ys[n // 3: 2 * n // 3]) / max(len(ys[n // 3: 2 * n // 3]), 1)
    last = sum(ys[2 * n // 3:]) / max(len(ys[2 * n // 3:]), 1)
    if middle < first - 0.25 and last > middle + 0.25:
        kind, note = "redemptive", ("Falls and recovers: the trouble is narrated as "
                                    "something survived.")
    elif middle > first + 0.25 and last < middle - 0.25:
        kind, note = "contaminative", ("Rises then falls: an early good is spoiled by what "
                                       "comes after.")
    elif slope > 0.02:
        kind, note = "progressive", "Moves steadily toward a better state."
    elif slope < -0.02:
        kind, note = "regressive", "Moves steadily toward a worse state."
    else:
        kind, note = "stable", "Holds a level tone throughout; endurance rather than change."
    return {"type": kind, "slope": round(slope, 4), "note": note,
            "thirds": [round(first, 2), round(middle, 2), round(last, 2)]}


def _temporal(pcodes):
    counter = Counter()
    for code in pcodes:
        low = " " + code["quote_text"].lower() + " "
        for marker in lx.TEMPORAL_MARKERS:
            if " " + marker + " " in low:
                counter[marker] += 1
    return [{"marker": m, "count": n} for m, n in counter.most_common(8)]


def _summary(participant, plot, agency, turning_points, arc):
    missing = [e for e in ELEMENTS if not arc[e]]
    bits = [participant + " tells a " + plot["type"] + " story. " + plot["note"]]
    if turning_points:
        tpn = turning_points[0]
        bits.append("The sharpest " + tpn["direction"] + " comes at \""
                    + tp.truncate(tpn["after"], 110) + "\"")
    bits.append(agency["note"])
    if missing:
        bits.append("No " + ", ".join(missing) + " segment surfaced — the story is told "
                    "without it, which is itself worth noting.")
    return " ".join(bits)


def _cross(narratives):
    plots = Counter(n["plot_type"]["type"] for n in narratives)
    agency_mean = (sum(n["agency"]["ratio"] for n in narratives) / len(narratives)
                   if narratives else 0)
    shared = Counter()
    for n in narratives:
        for point in n["turning_points"]:
            shared[point["direction"]] += 1
    return {
        "plot_types": dict(plots),
        "mean_agency_ratio": round(agency_mean, 3),
        "turning_point_directions": dict(shared),
        "note": _cross_note(plots, agency_mean, narratives),
    }


def _cross_note(plots, agency_mean, narratives):
    if not narratives:
        return "No narratives to compare."
    dominant = plots.most_common(1)[0]
    bits = [str(dominant[1]) + " of " + str(len(narratives)) + " accounts take a "
            + dominant[0] + " shape."]
    if agency_mean < 0.4:
        bits.append("Across the corpus, tellers are more often acted upon than acting — "
                    "a structural finding, not a personal one.")
    elif agency_mean > 0.6:
        bits.append("Tellers consistently claim agency, even where outcomes were poor.")
    else:
        bits.append("Agency is claimed and surrendered in roughly equal measure.")
    if len(plots) > 2:
        bits.append("The variation in plot shape is itself the finding: the same service "
                    "produces different stories for different people.")
    return " ".join(bits)
