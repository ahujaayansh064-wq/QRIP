"""Competitive cross-comparison.

Scores both businesses on the same operational dimensions, then finds the
adoption parameters: things the competitor is praised for that this business is
not — with the competitor's own customers' words as the evidence.
"""

ADOPTION_PLAYBOOK = {
    "Staff & Hospitality": (
        "Their customers name individual staff and describe being remembered. "
        "Introduce named ownership of each customer visit and brief the front desk "
        "to use names on arrival and at handover."),
    "Pricing & Value": (
        "Their reviews repeatedly mention knowing the price before committing. "
        "Publish the price list where customers see it before they are in the chair, "
        "and confirm the total verbally before any work starts."),
    "Facility Quality & Maintenance": (
        "Their premises are described as clean, modern and accessible. Run a weekly "
        "documented walk-round of the customer-facing estate and fix or visibly flag "
        "anything broken within 48 hours."),
    "Process & Wait Times": (
        "Their customers mention being seen on time and getting reminders. Add "
        "confirmation and day-before reminder messages, and publish a running-late "
        "rule: if you are more than 10 minutes behind, the customer is told and offered "
        "a choice."),
    "Overall Satisfaction": (
        "Their reviews close with an intention to return or recommend. Ask satisfied "
        "customers for a review at the moment of relief, not by email three days later."),
}

CATEGORY_PLAYBOOK = {
    "Access": "Make getting to and into the premises a published, solved problem: "
              "parking, step-free access and opening hours stated up front.",
    "Communication": "Guarantee a response window for calls and emails and staff it. "
                     "Most of the anger in your reviews is about silence, not outcomes.",
    "Quality": "Their reviews describe thoroughness and being unhurried. Protect "
               "appointment length rather than compressing it.",
    "Cost": "Remove pricing surprises entirely: written estimate before work, and no "
            "variation without explicit approval.",
    "Staff": "Their front-of-house is the single most praised thing they have. Treat "
             "reception as a customer-experience role, not an administrative one.",
    "Systems": "Their booking and reminders work. Fix double bookings and confirmations "
               "before spending anything on marketing.",
    "Outcomes": "They close the loop on results. Follow up after significant work to "
                "confirm the outcome held.",
    "Support": "They check in after the event unprompted. A single follow-up call is "
               "the cheapest reputation work available to you.",
}


def compare(primary, competitor):
    if not competitor:
        return None

    radar = _radar(primary, competitor)
    adoption = _adoption(primary, competitor, radar)
    defend = [entry for entry in radar if entry["gap"] >= 0.8]
    return {
        "primary_label": primary["label"],
        "competitor_label": competitor["label"],
        "radar": radar,
        "headline": _headline(primary, competitor, radar),
        "kpi_delta": {
            "net_sentiment_score": (primary["kpis"]["net_sentiment_score"]
                                    - competitor["kpis"]["net_sentiment_score"]),
            "average_rating": _delta(primary["kpis"]["average_rating"],
                                     competitor["kpis"]["average_rating"]),
            "negative_ratio": round(primary["kpis"]["negative_ratio"]
                                    - competitor["kpis"]["negative_ratio"], 3),
        },
        "adoption_parameters": adoption,
        "defend": [{"dimension": entry["dimension"], "lead": entry["gap"]} for entry in defend],
    }


def _delta(a, b):
    if a is None or b is None:
        return None
    return round(a - b, 2)


def _radar(primary, competitor):
    competitor_scores = {entry["dimension"]: entry for entry in competitor["dimensions"]}
    out = []
    for entry in primary["dimensions"]:
        rival = competitor_scores.get(entry["dimension"], {})
        theirs = rival.get("score", 5.5)
        out.append({
            "dimension": entry["dimension"],
            "primary": entry["score"],
            "competitor": theirs,
            "gap": round(entry["score"] - theirs, 2),
            "primary_mentions": entry.get("mentions", 0),
            "competitor_mentions": rival.get("mentions", 0),
            "competitor_quote": rival.get("best"),
            "primary_quote": entry.get("worst"),
        })
    return out


def _adoption(primary, competitor, radar):
    """Competitor strengths this business lacks, ranked by the size of the gap."""
    primary_categories = {entry["category"]: entry for entry in primary["content"]["summary"]}
    out = []

    for entry in sorted(radar, key=lambda item: item["gap"]):
        if entry["gap"] > -0.6:
            continue
        out.append({
            "parameter": entry["dimension"],
            "kind": "dimension",
            "your_score": entry["primary"],
            "their_score": entry["competitor"],
            "gap": abs(entry["gap"]),
            "evidence": entry["competitor_quote"],
            "your_evidence": entry["primary_quote"],
            "recommendation": ADOPTION_PLAYBOOK.get(entry["dimension"],
                                                    "Adopt their practice in this area."),
        })

    for entry in competitor["content"]["summary"]:
        if entry["mentions"] < 2 or entry["mean_valence"] < 0.15:
            continue
        mine = primary_categories.get(entry["category"])
        if mine and mine["mean_valence"] > entry["mean_valence"] - 0.2:
            continue
        if any(item["parameter"] == entry["category"] for item in out):
            continue
        out.append({
            "parameter": entry["category"],
            "kind": "category",
            "your_score": round(mine["mean_valence"], 2) if mine else None,
            "their_score": round(entry["mean_valence"], 2),
            "gap": round(entry["mean_valence"] - (mine["mean_valence"] if mine else 0), 2),
            "evidence": entry["examples"][0] if entry["examples"] else None,
            "your_evidence": (mine["examples"][0] if mine and mine["examples"] else None),
            "recommendation": CATEGORY_PLAYBOOK.get(entry["category"],
                                                    "Match their handling of this."),
        })

    out.sort(key=lambda item: -abs(item["gap"]))
    return out[:8]


def _headline(primary, competitor, radar):
    behind = [entry for entry in radar if entry["gap"] <= -0.6]
    ahead = [entry for entry in radar if entry["gap"] >= 0.6]
    nss_gap = (primary["kpis"]["net_sentiment_score"]
               - competitor["kpis"]["net_sentiment_score"])
    parts = []
    if nss_gap < -5:
        parts.append(competitor["label"] + " leads on net sentiment by "
                     + str(abs(nss_gap)) + " points.")
    elif nss_gap > 5:
        parts.append(primary["label"] + " leads on net sentiment by " + str(nss_gap)
                     + " points.")
    else:
        parts.append("Net sentiment is close between the two (" + str(nss_gap)
                     + " points apart).")
    if behind:
        parts.append("The gap is concentrated in "
                     + ", ".join(entry["dimension"] for entry in behind[:3]) + ".")
    if ahead:
        parts.append("You are ahead on "
                     + ", ".join(entry["dimension"] for entry in ahead[:2])
                     + " — that is the position to defend while you close the rest.")
    return " ".join(parts)
