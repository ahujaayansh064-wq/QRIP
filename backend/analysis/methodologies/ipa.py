"""Interpretative Phenomenological Analysis (Smith, Flowers & Larkin).

Idiographic first: each case is worked through on its own terms into Personal
Experiential Themes, and only then are Group Experiential Themes assembled
across cases with convergence and divergence made explicit.
"""
from collections import Counter, defaultdict

from .. import clustering as cl
from .. import lexicons as lx
from .. import textproc as tp

NAME = "Interpretative phenomenological analysis"
FRAMEWORK = "Smith, Flowers & Larkin — idiographic, hermeneutic, double hermeneutic"


def run(ctx):
    codes = ctx["codes"]
    vectors = ctx["vectors"]
    idf = ctx["idf"]
    by_participant = defaultdict(list)
    index_of = {id(c): i for i, c in enumerate(codes)}
    for code in codes:
        by_participant[code["participant_label"]].append(code)

    cases = []
    for participant in sorted(by_participant):
        pcodes = by_participant[participant]
        pidx = [index_of[id(c)] for c in pcodes]
        pvectors = [vectors[i] for i in pidx]
        groups = cl.cluster(pvectors, threshold=max(0.3, ctx["controls"]["similarity_threshold"]),
                            passes=1)
        taken = set()
        pets = []
        for group in groups:
            members = [pcodes[i] for i in group]
            if len(members) < 2:
                continue
            pets.append({
                "name": cl.name_theme(members, idf, taken),
                "statements": [_statement(c) for c in sorted(
                    members, key=lambda c: -c["confidence"])[:4]],
                "statement_count": len(members),
            })
        pets = pets[:6]
        cases.append({
            "participant": participant,
            "experiential_statements": [_statement(c) for c in sorted(
                pcodes, key=lambda c: -c["confidence"])[:8]],
            "personal_experiential_themes": pets,
            "dimensions": _dimension_profile(pcodes),
            "idiographic_summary": _case_summary(participant, pcodes, pets),
            "code_count": len(pcodes),
        })

    gets = _group_themes(ctx, by_participant)
    return {
        "methodology": "ipa",
        "name": NAME,
        "framework": FRAMEWORK,
        "cases": cases,
        "group_experiential_themes": gets,
        "dimension_totals": _totals(codes),
        "hermeneutic_notes": [
            ("Double hermeneutic: every statement below is the analyst making sense of a "
             "participant making sense of their own experience. The interpretive layer is "
             "shown separately from the quotation so it can be challenged."),
            ("Idiography is preserved: group themes are assembled from personal themes, "
             "never the other way round. A group theme that erases a case is a failure of "
             "the method, not a stronger finding."),
            ("Bracketing prompt: note what you already believed about this phenomenon "
             "before reading the transcripts, and where that belief shows in the naming."),
        ],
    }


def _statement(code):
    dims = _dimensions_for(code["quote_text"])
    return {
        "quote": tp.truncate(code["quote_text"], 300),
        "participant": code["participant_label"],
        "descriptive": code["literal_meaning"],
        "linguistic": _linguistic_note(code),
        "conceptual": _conceptual_note(code),
        "dimension": dims[0] if dims else "experiential",
        "confidence": code["confidence"],
    }


def _linguistic_note(code):
    text = code["quote_text"].lower()
    notes = []
    if any(h in text.split() for h in lx.HEDGES):
        notes.append("hedged delivery")
    if any(n in text.split() for n in lx.NEGATORS):
        notes.append("built around negation — what did not happen")
    if any(i in text.split() for i in lx.INTENSIFIERS):
        notes.append("intensifiers heighten the account")
    if text.count(",") >= 3:
        notes.append("accumulating clauses, as if the list itself is the point")
    if " i " in " " + text and " they " in text:
        notes.append("an I/they contrast structures the sentence")
    return ", ".join(notes) if notes else "plain declarative delivery"


def _conceptual_note(code):
    emotion = code["emotion"]
    if emotion == "neutral":
        return ("Held at a descriptive distance — the experience is reported rather than "
                "felt aloud, which may itself be a way of managing it.")
    templates = {
        "frustration": "The obstruction is experienced as personal, not procedural.",
        "anxiety": "Anticipation does the harm here: the waiting is the event.",
        "sadness": "A loss is being named without being called a loss.",
        "anger": "Moral language — this is framed as a wrong, not a mistake.",
        "relief": "Relief is defined against an expected worse outcome.",
        "hope": "The future is used to make the present bearable.",
        "gratitude": "Gratitude is directed at individuals, rarely at the system.",
        "pride": "Agency reclaimed — the participant positions themselves as the actor.",
        "confusion": "Meaning-making stalls; the participant is left to author the gaps.",
        "trust": "Trust is described relationally, resting on being believed.",
        "distrust": "Being disbelieved is experienced as a threat to standing, not just care.",
        "resignation": "Acceptance here reads as exhaustion rather than peace.",
    }
    return templates.get(emotion, "An affective register shapes how the event is remembered.")


def _dimensions_for(text):
    low = " " + text.lower() + " "
    scored = []
    for dim, cues in lx.IPA_DIMENSIONS.items():
        hits = sum(1 for cue in cues if cue in low)
        if hits:
            scored.append((hits, dim))
    scored.sort(reverse=True)
    return [d for _, d in scored]


def _dimension_profile(pcodes):
    counter = Counter()
    for code in pcodes:
        for dim in _dimensions_for(code["quote_text"]):
            counter[dim] += 1
    return dict(counter)


def _totals(codes):
    counter = Counter()
    for code in codes:
        for dim in _dimensions_for(code["quote_text"]):
            counter[dim] += 1
    return dict(counter)


def _case_summary(participant, pcodes, pets):
    emotions = Counter(c["emotion"] for c in pcodes if c["emotion"] != "neutral")
    valence = sum(c["valence"] for c in pcodes) / len(pcodes) if pcodes else 0
    dims = Counter()
    for c in pcodes:
        for d in _dimensions_for(c["quote_text"]):
            dims[d] += 1
    top_dim = dims.most_common(1)[0][0] if dims else "experiential"
    top_em = emotions.most_common(1)[0][0] if emotions else "an unmarked register"
    names = ", ".join("'" + p["name"] + "'" for p in pets[:3]) or "no stable personal theme yet"
    return (
        participant + "'s account is organised around " + names + ". The prevailing register "
        "is " + top_em + " (mean valence " + str(round(valence, 2)) + "), and experience is "
        "most often rendered in " + top_dim + " terms. Read this case on its own before "
        "reading it against the others."
    )


def _group_themes(ctx, by_participant):
    """Assemble GETs from the corpus-level themes, keeping case detail visible."""
    gets = []
    codes = ctx["codes"]
    n_participants = len(by_participant) or 1
    for theme in ctx["themes"]:
        member_codes = [codes[i] for i in theme["member_idx"]]
        by_p = defaultdict(list)
        for c in member_codes:
            by_p[c["participant_label"]].append(c)
        present = sorted(by_p)
        convergence = round(len(present) / n_participants, 3)
        absent = sorted(set(by_participant) - set(present))
        exemplars = []
        for participant in present[:5]:
            best = max(by_p[participant], key=lambda c: c["confidence"])
            exemplars.append({
                "participant": participant,
                "quote": tp.truncate(best["quote_text"], 240),
                "reading": _conceptual_note(best),
            })
        divergence = []
        valences = {p: sum(c["valence"] for c in cs) / len(cs) for p, cs in by_p.items()}
        if valences:
            lo = min(valences, key=valences.get)
            hi = max(valences, key=valences.get)
            if valences[hi] - valences[lo] > 0.5:
                divergence.append(
                    hi + " and " + lo + " occupy opposite ends of this theme (valence "
                    + str(round(valences[hi], 2)) + " vs " + str(round(valences[lo], 2))
                    + "); the theme holds the tension rather than resolving it."
                )
        if absent:
            divergence.append("Absent from " + ", ".join(absent)
                              + " — absence is data here, not missingness.")
        gets.append({
            "id": theme.get("id"),
            "name": theme["name"],
            "present_in": present,
            "convergence": convergence,
            "exemplars": exemplars,
            "divergence": divergence,
            "status": theme["status"],
        })
    gets.sort(key=lambda g: -g["convergence"])
    return gets
