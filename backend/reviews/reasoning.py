"""Function 2 — theme reasoning.

Takes the codebook from function 1 and decides what the themes actually are,
then places every code in the theme it belongs to. This is the pass that needs
judgement rather than string similarity: 'nobody called me back', 'three
unanswered emails' and 'the phone rings out' are lexically unrelated and
analytically the same finding.

Claude Opus 5 at medium effort does the reasoning in two passes — the theme set
is decided once over the whole codebook so it stays consistent, then codes are
assigned in batches against that fixed set. Arithmetic (coverage, counts,
participants) is computed here, not asked of the model.
"""
from collections import defaultdict

import claude

from .scoring import sentiment_label

ASSIGN_BATCH = 45

SYSTEM = (
    "You are a senior qualitative researcher building a thematic framework from "
    "coded customer reviews. You group codes by what they mean for the business, "
    "not by shared vocabulary: 'nobody returned my call', 'three unanswered "
    "emails' and 'the phone just rings' belong to one theme about communication "
    "failure even though they share no words. A theme is a finding an operator "
    "could act on, not a topic label."
)

THEME_SCHEMA = {
    "type": "object",
    "properties": {
        "themes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string"},
                    "description": {"type": "string"},
                    "alternative_interpretation": {"type": "string"},
                    "status": {"type": "string",
                               "enum": ["confirmed", "review", "candidate"]},
                },
                "required": ["theme", "description", "alternative_interpretation",
                             "status"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["themes"],
    "additionalProperties": False,
}

ASSIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "assignments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code_index": {"type": "integer"},
                    "theme": {"type": "string"},
                    "confidence": {"type": "number"},
                    "rationale": {"type": "string"},
                },
                "required": ["code_index", "theme", "confidence", "rationale"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["assignments"],
    "additionalProperties": False,
}

UNASSIGNED = "Unassigned"


def run(codes, candidate_themes, business_name="", review_count=0,
        on_usage=None, on_progress=None):
    """Decide the themes, then sort every code into one. Returns themes + codes."""
    if not codes:
        return {"themes": [], "codes": codes, "engine": "none",
                "note": "No codes to reason over."}

    if not claude.configured():
        themes = _fallback(codes, candidate_themes, review_count)
        return {"themes": themes, "codes": codes, "engine": "local",
                "note": ("Claude is not configured, so codes were grouped by lexical "
                         "similarity instead of reasoning. Set ANTHROPIC_API_KEY for "
                         "the theme quality this step is designed for.")}

    themes = _derive_themes(codes, candidate_themes, business_name, review_count,
                            on_usage)
    if not themes:
        fallback = _fallback(codes, candidate_themes, review_count)
        return {"themes": fallback, "codes": codes, "engine": "local",
                "note": "The reasoning pass failed; fell back to lexical grouping."}

    _assign(codes, themes, business_name, on_usage, on_progress)
    enriched = _finalise(codes, themes, review_count)
    return {"themes": enriched, "codes": codes, "engine": "claude", "note": None}


# --- pass 1: what are the themes ------------------------------------------

def _derive_themes(codes, candidate_themes, business_name, review_count, on_usage):
    import json
    digest = []
    for index, code in enumerate(codes):
        digest.append({
            "i": index,
            "code": code["code"],
            "emotion": code["emotion"],
            "valence": code["valence"],
            "quote": code["quote"][:220],
        })
    proposed = [theme["theme"] for theme in candidate_themes]

    prompt = (
        "Business: " + (business_name or "(not named)") + "\n"
        "Reviews analysed: " + str(review_count) + "\n\n"
        "Below is the full codebook produced by open coding. Decide the thematic "
        "framework for this business.\n\n"
        "Rules:\n"
        "- Produce between 4 and 8 themes. Each must be a finding, not a topic: "
        "'Pricing quoted and pricing charged do not match' rather than 'Pricing'.\n"
        "- Every theme must be supported by codes from more than one reviewer, "
        "unless the issue is severe enough to matter on its own.\n"
        "- Themes must be distinguishable: if two would take the same codes, "
        "merge them.\n"
        "- description: 2-3 sentences on what the pattern is and what it means "
        "operationally.\n"
        "- alternative_interpretation: a different reading of the same evidence "
        "that a sceptical reader could defend.\n"
        "- status: 'confirmed' when several reviewers independently support it, "
        "'review' when the evidence is thinner, 'candidate' when it is one "
        "reviewer or ambiguous.\n\n"
        "A lexical clustering pass proposed these groupings, which you may accept, "
        "reshape or discard: " + json.dumps(proposed, ensure_ascii=False) + "\n\n"
        "Codebook:\n" + json.dumps(digest, ensure_ascii=False)
    )

    result = claude.structured(SYSTEM, prompt, THEME_SCHEMA, effort="medium",
                               max_tokens=8000, on_usage=on_usage)
    if not result:
        return []
    themes = []
    seen = set()
    for entry in result.get("themes") or []:
        name = str(entry.get("theme") or "").strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        themes.append({
            "theme": name[:140],
            "description": str(entry.get("description") or "").strip(),
            "alternative_interpretation":
                str(entry.get("alternative_interpretation") or "").strip(),
            "status": entry.get("status") if entry.get("status") in
                      ("confirmed", "review", "candidate") else "candidate",
        })
    return themes


# --- pass 2: which theme does each code belong to -------------------------

def _assign(codes, themes, business_name, on_usage, on_progress):
    import json
    names = [theme["theme"] for theme in themes]
    lookup = {name.lower(): name for name in names}
    batches = list(claude.batched(list(enumerate(codes)), ASSIGN_BATCH))

    for number, batch in enumerate(batches):
        if on_progress:
            on_progress(number / max(len(batches), 1))
        payload = [{
            "i": index,
            "code": code["code"],
            "quote": code["quote"][:300],
            "literal_meaning": code["literal_meaning"][:200],
            "emotion": code["emotion"],
            "valence": code["valence"],
        } for index, code in batch]

        prompt = (
            "Business: " + (business_name or "(not named)") + "\n\n"
            "Themes (use these names exactly, or \"" + UNASSIGNED + "\"):\n"
            + json.dumps([{"theme": theme["theme"],
                           "description": theme["description"]}
                          for theme in themes], ensure_ascii=False) + "\n\n"
            "Assign each code below to the one theme it best belongs to. Judge by "
            "what the reviewer meant, not by shared words. Use \"" + UNASSIGNED
            + "\" only when the code genuinely does not belong to any theme — "
            "forcing a poor fit is worse than leaving it out.\n"
            "confidence is 0.0-1.0 for the fit. rationale is one short clause.\n\n"
            "Codes:\n" + json.dumps(payload, ensure_ascii=False)
        )

        result = claude.structured(SYSTEM, prompt, ASSIGN_SCHEMA, effort="medium",
                                   max_tokens=12000, on_usage=on_usage)
        if not result:
            continue
        for item in result.get("assignments") or []:
            try:
                code = codes[int(item["code_index"])]
            except (KeyError, ValueError, IndexError, TypeError):
                continue
            name = lookup.get(str(item.get("theme") or "").strip().lower())
            if not name:
                continue
            code["themes"] = [name]
            code["theme_confidence"] = round(
                max(0.0, min(1.0, float(item.get("confidence") or 0.7))), 3)
            code["theme_rationale"] = str(item.get("rationale") or "").strip()[:300]
    if on_progress:
        on_progress(1.0)


# --- statistics, computed rather than asked -------------------------------

def _finalise(codes, themes, review_count):
    grouped = defaultdict(list)
    for code in codes:
        for name in code["themes"]:
            grouped[name].append(code)

    out = []
    for theme in themes:
        members = grouped.get(theme["theme"], [])
        participants = sorted({code["participant"] for code in members})
        valences = [code["valence"] for code in members]
        mean = sum(valences) / len(valences) if valences else 0.0
        confidences = [code.get("theme_confidence", code["confidence"])
                       for code in members]
        out.append({
            **theme,
            "participants": participants,
            "evidence_count": len(members),
            # names the report, workbook and UI already use
            "quote_count": len(members),
            "reviewers": participants,
            "coverage": round(len(participants) / max(review_count, 1), 3),
            "confidence": round(sum(confidences) / len(confidences), 3)
                          if confidences else 0.0,
            "mean_valence": round(mean, 3),
            "sentiment": sentiment_label(mean),
            "mean_rating": _mean([code["rating"] for code in members]),
            "quotes": [{
                "reviewer": code["participant"],
                "text": code["quote"],
                "code": code["code"],
                "valence": code["valence"],
                "rating": code["rating"],
            } for code in sorted(members, key=lambda c: c["valence"])[:4]],
        })
    out = [theme for theme in out if theme["evidence_count"] > 0]
    out.sort(key=lambda theme: -theme["evidence_count"])
    return out


def _mean(values):
    numbers = [value for value in values if value is not None]
    return round(sum(numbers) / len(numbers), 2) if numbers else None


# --- fallback when Claude is unavailable ----------------------------------

def _fallback(codes, candidate_themes, review_count):
    """Use the lexical clusters from function 1 as the themes."""
    for theme in candidate_themes:
        for index in theme.get("code_indexes", []):
            if 0 <= index < len(codes):
                codes[index]["themes"] = [theme["theme"]]
    themes = [{
        "theme": theme["theme"],
        "description": theme.get("description")
            or ("Grouped by lexical similarity across "
                + str(theme["evidence_count"]) + " codes from "
                + str(len(theme["participants"])) + " reviewers."),
        "alternative_interpretation": theme.get("alternative_interpretation")
            or "Grouped without reasoning about context; treat the boundary as provisional.",
        "status": theme.get("status", "candidate"),
    } for theme in candidate_themes]
    return _finalise(codes, themes, review_count)
