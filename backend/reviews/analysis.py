"""Review analytics.

This is QRIP's qualitative engine pointed at customer reviews: the same
sentence-level coding (emotion, intent, valence, confidence, alternative
readings), the same concept-space clustering into themes, and the same
contradiction detection — plus the review-specific layers an operator needs:
temporal trend, content counts, a customer-journey framework matrix, an
operational bottleneck audit and competitive dimension scores.
"""
from collections import Counter, defaultdict

from analysis import clustering as cl
from analysis import coding
from analysis import contradictions as contra
from analysis import textproc as tp

from . import lexicon as lx
from .sources import BUCKETS, bucket_for

POSITIVE_CUT = 0.12
NEGATIVE_CUT = -0.12

CONTROLS = {
    "similarity_threshold": 0.3,
    "confidence_threshold": 0.5,
    "min_supporting_quotations": 2,
    "participant_frequency_threshold": 2,
    "coding_granularity": "sentence",
    "contradiction_sensitivity": 0.55,
}


def sentiment_label(value):
    if value >= POSITIVE_CUT:
        return "positive"
    if value <= NEGATIVE_CUT:
        return "negative"
    return "neutral"


def blended_sentiment(text_valence, rating):
    """Text carries the meaning; the star rating is corroboration, not truth.

    Reviewers routinely leave four stars beside a paragraph of complaint, which
    is exactly the contradiction this report is meant to surface — so the text
    keeps the larger weight.
    """
    if rating is None:
        return round(text_valence, 3)
    star_valence = (float(rating) - 3.0) / 2.0
    return round(0.65 * text_valence + 0.35 * star_valence, 3)


# --- coding ---------------------------------------------------------------

def code_reviews(reviews):
    """Sentence-granularity coding, one code per meaning unit."""
    units = []
    for review in reviews:
        pieces = [piece for piece in tp.split_sentences(review["text"])
                  if len(piece.split()) >= 4]
        if not pieces:
            pieces = [review["text"]]
        for index, piece in enumerate(pieces):
            units.append({
                "id": review["id"] + ":" + str(index),
                "transcript_id": review["id"],
                "participant_label": review["reviewer_id"],
                "idx": index,
                "turn_idx": 0,
                "text": piece.strip(),
                "question_context": None,
            })
    if not units:
        return [], {}, {}, {}

    unit_stems = [tp.stems(unit["text"]) for unit in units]
    idf = tp.idf_table(unit_stems)
    related = tp.cooccurrence(unit_stems)
    concepts, _ = tp.concept_space(unit_stems)
    codes = coding.code_units(units, idf, "sentence")

    by_review = {review["id"]: review for review in reviews}
    for code in codes:
        review = by_review[code["transcript_id"]]
        code["review_id"] = review["id"]
        code["reviewer"] = review["reviewer"]
        code["rating"] = review["rating"]
        code["months_ago"] = review["months_ago"]
        code["bucket"] = bucket_for(review["months_ago"])
        code["sentiment"] = sentiment_label(code["valence"])
    return codes, idf, related, concepts


def build_themes(codes, idf, related, concepts, participant_count):
    if len(codes) < 2:
        return [], []
    vectors = cl.build_vectors(codes, idf, concepts, related)
    clusters = cl.cluster(vectors, threshold=CONTROLS["similarity_threshold"])
    controls = dict(CONTROLS)
    controls["idf"] = idf
    themes = cl.summarise(codes, vectors, clusters, controls, participant_count)
    for theme in themes:
        members = [codes[i] for i in theme["member_idx"]]
        for code in members:
            code["theme_name"] = theme["name"]
        theme["reviewers"] = sorted({code["participant_label"] for code in members})
        theme["mean_rating"] = _mean([code["rating"] for code in members
                                      if code["rating"] is not None])
        theme["sentiment"] = sentiment_label(theme["mean_valence"])
        theme["quotes"] = [{
            "reviewer": code["reviewer"], "text": code["quote_text"],
            "valence": code["valence"], "rating": code["rating"],
        } for code in sorted(members, key=lambda c: c["valence"])[:3]]
    return themes, vectors


def _mean(values):
    values = [value for value in values if value is not None]
    return round(sum(values) / len(values), 2) if values else None


# --- contradictions -------------------------------------------------------

def find_contradictions(codes, vectors, themes, reviews):
    """Two kinds: tension inside a theme, and stars that fight the words."""
    out = []
    if themes and vectors:
        for item in contra.detect(codes, vectors, themes,
                                  CONTROLS["contradiction_sensitivity"])[:20]:
            out.append({
                "theme": item.get("theme_name") or "Across themes",
                "severity": _severity(item["severity"]),
                "severity_score": item["severity"],
                "kind": item["kind"],
                "description": item["description"],
            })

    by_review = defaultdict(list)
    for code in codes:
        by_review[code["review_id"]].append(code)
    for review in reviews:
        members = by_review.get(review["id"], [])
        if not members or review["rating"] is None:
            continue
        text_valence = sum(code["valence"] for code in members) / len(members)
        rating = float(review["rating"])
        if rating >= 4 and text_valence <= -0.2:
            worst = min(members, key=lambda code: code["valence"])
            out.append({
                "theme": worst.get("theme_name") or "Rating vs text",
                "severity": _severity(min(1.0, (rating - 3) / 2 + abs(text_valence))),
                "severity_score": round(min(1.0, (rating - 3) / 2 + abs(text_valence)), 3),
                "kind": "rating-vs-text",
                "description": (review["reviewer"] + " left " + str(int(rating))
                                + " stars while describing a clear problem: \""
                                + tp.truncate(worst["quote_text"], 180)
                                + "\" The score flatters the experience — a star "
                                  "average will hide this."),
            })
        elif rating <= 2 and text_valence >= 0.2:
            best = max(members, key=lambda code: code["valence"])
            out.append({
                "theme": best.get("theme_name") or "Rating vs text",
                "severity": 1,
                "severity_score": 0.35,
                "kind": "rating-vs-text",
                "description": (review["reviewer"] + " left " + str(int(rating))
                                + " stars but the text is largely positive: \""
                                + tp.truncate(best["quote_text"], 160)
                                + "\" One specific failure is dragging the whole "
                                  "score down."),
            })
    names = {review["reviewer_id"]: review["reviewer"] for review in reviews}
    for item in out:
        for reviewer_id, name in names.items():
            item["description"] = item["description"].replace(reviewer_id, name)
    out.sort(key=lambda item: -item["severity_score"])
    return out[:30]


def _severity(score):
    if score >= 0.66:
        return 3
    if score >= 0.33:
        return 2
    return 1


# --- content counts -------------------------------------------------------

def content_counts(codes, reviews):
    categories = list(lx.CONTENT_CATEGORIES)
    per_review = defaultdict(Counter)
    valence = defaultdict(list)
    examples = defaultdict(list)
    for code in codes:
        for category, cues in lx.CONTENT_CATEGORIES.items():
            if coding.count_hits(code["quote_text"], cues):
                per_review[code["review_id"]][category] += 1
                valence[category].append(code["valence"])
                if len(examples[category]) < 3:
                    examples[category].append({
                        "reviewer": code["reviewer"],
                        "text": tp.truncate(code["quote_text"], 180),
                        "valence": code["valence"],
                    })
    rows = []
    for review in reviews:
        counts = [per_review[review["id"]].get(category, 0) for category in categories]
        rows.append({"reviewer": review["reviewer"], "reviewer_id": review["reviewer_id"],
                     "counts": counts, "total": sum(counts)})
    totals = [sum(row["counts"][i] for row in rows) for i in range(len(categories))]
    summary = []
    for index, category in enumerate(categories):
        values = valence[category]
        summary.append({
            "category": category,
            "mentions": totals[index],
            "reviews": sum(1 for row in rows if row["counts"][index]),
            "mean_valence": round(sum(values) / len(values), 3) if values else 0.0,
            "sentiment": sentiment_label(sum(values) / len(values)) if values else "neutral",
            "examples": examples[category],
        })
    summary.sort(key=lambda entry: -entry["mentions"])
    return {"categories": categories, "rows": rows, "totals": totals, "summary": summary}


# --- framework matrix -----------------------------------------------------

def framework_matrix(codes, reviews):
    stages = [name for name, _ in lx.FRAMEWORK_STAGES]
    cells = defaultdict(lambda: defaultdict(list))
    for code in codes:
        for stage, cues in lx.FRAMEWORK_STAGES:
            if coding.count_hits(code["quote_text"], cues):
                cells[code["participant_label"]][stage].append(code)

    rows = []
    for review in reviews:
        row = {"reviewer": review["reviewer"], "reviewer_id": review["reviewer_id"],
               "rating": review["rating"], "cells": []}
        for stage in stages:
            found = cells[review["reviewer_id"]].get(stage, [])
            if not found:
                row["cells"].append({"summary": "", "count": 0, "valence": None})
                continue
            best = sorted(found, key=lambda code: -abs(code["valence"]))[:2]
            mean = sum(code["valence"] for code in found) / len(found)
            row["cells"].append({
                "summary": " ".join(tp.truncate(code["quote_text"], 150) for code in best),
                "count": len(found),
                "valence": round(mean, 2),
            })
        rows.append(row)

    synthesis = []
    for index, stage in enumerate(stages):
        entries = [code for reviewer in cells.values() for code in reviewer.get(stage, [])]
        if not entries:
            synthesis.append({"stage": stage, "coverage": 0, "mean_valence": 0.0,
                              "reading": "Nothing in the corpus speaks to this stage — "
                                         "either it does not arise, or reviewers are "
                                         "not being asked about it."})
            continue
        mean = sum(code["valence"] for code in entries) / len(entries)
        reviewers = len({code["participant_label"] for code in entries})
        top = sorted(entries, key=lambda code: code["valence"])[0]
        synthesis.append({
            "stage": stage,
            "coverage": round(reviewers / max(len(reviews), 1), 3),
            "mentions": len(entries),
            "mean_valence": round(mean, 3),
            "sentiment": sentiment_label(mean),
            "quote": tp.truncate(top["quote_text"], 200),
            "quote_reviewer": top["reviewer"],
            "reading": _stage_reading(stage, mean, reviewers, len(reviews)),
        })
    return {"stages": stages, "rows": rows, "synthesis": synthesis}


def _stage_reading(stage, mean, reviewers, total):
    share = int(round(100 * reviewers / max(total, 1)))
    tone = ("consistently negative" if mean < -0.25 else "negative on balance"
            if mean < -0.05 else "consistently positive" if mean > 0.25
            else "positive on balance" if mean > 0.05 else "mixed")
    templates = {
        "Expectations": "What customers arrive expecting, and who set that expectation.",
        "Experience": "What actually happened on the day.",
        "Barriers": "What got in the way.",
        "Enablers": "What made it work when it worked.",
        "Impact": "What the experience cost or gained the customer afterwards.",
        "Suggestions for Change": "What customers are explicitly asking you to fix.",
    }
    return (templates[stage] + " Raised by " + str(share) + "% of reviewers and "
            + tone + " (mean valence " + str(round(mean, 2)) + ").")


# --- bottlenecks ----------------------------------------------------------

def bottlenecks(codes, themes, reviews):
    """Operational friction ranked by how much it costs and how widely it spreads."""
    negative = [code for code in codes if _reads_as_complaint(code)]
    if not negative:
        return []
    # Grouped by operational category rather than by auto-generated theme name:
    # an operator needs "Systems — double bookings", not a cluster label.
    grouped = defaultdict(list)
    for code in negative:
        grouped[_category_of(code) or "General service"].append(code)

    total_reviews = max(len(reviews), 1)
    out = []
    for category, members in grouped.items():
        name = category + " — " + _issue_phrase(members)
        reviewers = {code["participant_label"] for code in members}
        coverage = len(reviewers) / total_reviews
        mean_valence = sum(code["valence"] for code in members) / len(members)
        friction = sum(coding.count_hits(code["quote_text"], lx.FRICTION) for code in members)
        ratings = [code["rating"] for code in members if code["rating"] is not None]
        severity = min(1.0, (abs(mean_valence) * 0.55) + (coverage * 0.9)
                       + min(friction / max(len(members), 1), 2) * 0.12)
        recent = sum(1 for code in members if (code["months_ago"] or 99) <= 6)
        out.append({
            "issue": name,
            "severity": round(severity, 3),
            "severity_band": _severity(severity),
            "coverage": round(coverage, 3),
            "mentions": len(members),
            "reviewers": len(reviewers),
            "mean_valence": round(mean_valence, 3),
            "mean_rating": _mean(ratings),
            "recent_share": round(recent / len(members), 2),
            "category": category,
            "evidence": [{
                "reviewer": code["reviewer"],
                "rating": code["rating"],
                "text": tp.truncate(code["quote_text"], 220),
                "bucket": code["bucket"],
            } for code in sorted(members, key=lambda code: code["valence"])[:3]],
        })
    # A single uncategorised complaint is noise, not a bottleneck: it has no
    # operational home and its label comes from one sentence.
    out = [entry for entry in out
           if entry["category"] != "General service" or entry["mentions"] >= 2]
    out.sort(key=lambda entry: (-entry["severity"], -entry["mentions"]))
    return out[:12]


def _reads_as_complaint(code):
    """Is this statement a complaint?

    Lexical valence alone misses plain operational reporting — "waited 25
    minutes for a sandwich that arrived cold" contains no lexicon-negative word.
    A low star rating on the parent review, or explicit friction vocabulary,
    corroborates what the sentence is doing.
    """
    if code["valence"] <= NEGATIVE_CUT:
        return True
    rating = code.get("rating")
    if rating is not None and float(rating) <= 2 and code["valence"] <= 0.08:
        return True
    if coding.count_hits(code["quote_text"], lx.FRICTION) and code["valence"] <= 0.02:
        return True
    return False


def _issue_phrase(members):
    """Name the friction in the reviewers' own words."""
    phrases = Counter()
    for code in members:
        weight = 1 + coding.count_hits(code["quote_text"], lx.FRICTION)
        phrases[code["phrase"]] += weight
    if not phrases:
        return "recurring complaints"
    best = max(phrases.items(), key=lambda item: (item[1], len(item[0].split())))[0]
    return best


def _category_of(code):
    best, best_hits = None, 0
    for category, cues in lx.CONTENT_CATEGORIES.items():
        hits = coding.count_hits(code["quote_text"], cues)
        if hits > best_hits:
            best, best_hits = category, hits
    return best


# --- KPIs, temporal, dimensions -------------------------------------------

def kpis(reviews, codes):
    by_review = defaultdict(list)
    for code in codes:
        by_review[code["review_id"]].append(code)
    split = Counter()
    sentiments = []
    for review in reviews:
        members = by_review.get(review["id"], [])
        text_valence = (sum(code["valence"] for code in members) / len(members)
                        if members else 0.0)
        review["text_valence"] = round(text_valence, 3)
        review["sentiment_score"] = blended_sentiment(text_valence, review["rating"])
        review["sentiment"] = sentiment_label(review["sentiment_score"])
        split[review["sentiment"]] += 1
        sentiments.append(review["sentiment_score"])
    total = max(len(reviews), 1)
    ratings = [review["rating"] for review in reviews if review["rating"] is not None]
    responded = sum(1 for review in reviews if review.get("owner_response"))
    return {
        "total_reviews": len(reviews),
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "positive": split["positive"], "neutral": split["neutral"],
        "negative": split["negative"],
        "net_sentiment_score": round((split["positive"] - split["negative"]) / total * 100),
        "negative_ratio": round(split["negative"] / total, 3),
        "mean_sentiment": round(sum(sentiments) / total, 3),
        "coded_units": len(codes),
        "owner_response_rate": round(responded / total, 3),
        "with_photos": sum(1 for review in reviews if review.get("photo_count")),
    }


def temporal(reviews):
    counts = {bucket: {"positive": 0, "neutral": 0, "negative": 0, "total": 0,
                       "ratings": []} for bucket in BUCKETS}
    for review in reviews:
        bucket = bucket_for(review["months_ago"])
        entry = counts[bucket]
        entry[review.get("sentiment", "neutral")] += 1
        entry["total"] += 1
        if review["rating"] is not None:
            entry["ratings"].append(review["rating"])
    series = []
    for bucket in BUCKETS:
        entry = counts[bucket]
        if not entry["total"]:
            continue
        series.append({
            "bucket": bucket,
            "positive": entry["positive"], "neutral": entry["neutral"],
            "negative": entry["negative"], "total": entry["total"],
            "average_rating": _mean(entry["ratings"]),
            "negative_ratio": round(entry["negative"] / entry["total"], 3),
        })
    return {"series": series, "reading": _trend_reading(series)}


def _trend_reading(series):
    ordered = [entry for entry in series if entry["bucket"] != "unknown"]
    if len(ordered) < 2:
        return "Not enough dated reviews to read a trend."
    recent = ordered[0]
    older = ordered[-1]
    delta = recent["negative_ratio"] - older["negative_ratio"]
    if delta > 0.12:
        return ("Negative sentiment is rising: " + str(int(recent["negative_ratio"] * 100))
                + "% of reviews in the last three months are negative against "
                + str(int(older["negative_ratio"] * 100)) + "% in the oldest period. "
                "Something has changed operationally and it is getting worse, not settling.")
    if delta < -0.12:
        return ("Negative sentiment is falling: " + str(int(older["negative_ratio"] * 100))
                + "% in the oldest period down to " + str(int(recent["negative_ratio"] * 100))
                + "% now. Whatever changed in between is working — protect it.")
    return ("Sentiment is broadly stable across the period (negative share moved "
            + str(round(delta * 100, 1)) + " points). The problems in this report are "
            "structural rather than a recent slip.")


def dimension_scores(codes, reviews):
    """1-10 scores per operational dimension, from sentiment not stars."""
    out = []
    ratings = [review["rating"] for review in reviews if review["rating"] is not None]
    baseline = ((sum(ratings) / len(ratings) - 1) / 4 * 9 + 1) if ratings else 5.5
    for dimension, cues in lx.DIMENSIONS.items():
        matched = [code for code in codes if coding.count_hits(code["quote_text"], cues)]
        if not matched:
            out.append({"dimension": dimension, "score": round(baseline, 1), "mentions": 0,
                        "mean_valence": 0.0, "basis": "no direct mentions — overall rating used"})
            continue
        mean = sum(code["valence"] for code in matched) / len(matched)
        raw = max(1.0, min(10.0, 5.5 + mean * 4.5))
        # Shrink towards the overall rating when the evidence is thin: one glowing
        # sentence should not produce a perfect score on a whole dimension.
        prior = 2.0
        score = (raw * len(matched) + baseline * prior) / (len(matched) + prior)
        out.append({
            "dimension": dimension,
            "score": round(max(1.0, min(10.0, score)), 1),
            "mentions": len(matched),
            "reviewers": len({code["participant_label"] for code in matched}),
            "mean_valence": round(mean, 3),
            "basis": str(len(matched)) + " coded mentions",
            "best": _quote(max(matched, key=lambda code: code["valence"])),
            "worst": _quote(min(matched, key=lambda code: code["valence"])),
        })
    return out


def _quote(code):
    return {"reviewer": code["reviewer"], "text": tp.truncate(code["quote_text"], 200),
            "valence": code["valence"]}


# --- top-level ------------------------------------------------------------

def analyse(reviews, label):
    """Run the whole pipeline for one business."""
    codes, idf, related, concepts = code_reviews(reviews)
    participants = len({review["reviewer_id"] for review in reviews})
    themes, vectors = build_themes(codes, idf, related, concepts, participants)
    summary = kpis(reviews, codes)          # also fills review sentiment fields
    return {
        "label": label,
        "kpis": summary,
        "temporal": temporal(reviews),
        "themes": [_theme_out(theme) for theme in themes],
        "codebook": [_code_out(code) for code in codes],
        "contradictions": find_contradictions(codes, vectors, themes, reviews),
        "content": content_counts(codes, reviews),
        "framework": framework_matrix(codes, reviews),
        "bottlenecks": bottlenecks(codes, themes, reviews),
        "dimensions": dimension_scores(codes, reviews),
        "reviews": [_review_out(review) for review in reviews],
    }


def _theme_out(theme):
    return {
        "theme": theme["name"],
        "status": theme["status"],
        "confidence": theme["confidence"],
        "coverage": theme["coverage"],
        "quote_count": len(theme["member_idx"]),
        "reviewers": theme["reviewers"],
        "sentiment": theme["sentiment"],
        "mean_valence": theme["mean_valence"],
        "mean_rating": theme["mean_rating"],
        "description": theme["description"],
        "alternative_interpretation": theme["alternative_interpretation"],
        "quotes": theme["quotes"],
    }


def _code_out(code):
    return {
        "code": code["label"],
        "theme": code.get("theme_name") or "",
        "reviewer": code["reviewer"],
        "reviewer_id": code["participant_label"],
        "rating": code["rating"],
        "emotion": code["emotion"],
        "intent": code["intent"],
        "valence": code["valence"],
        "sentiment": code["sentiment"],
        "confidence": code["confidence"],
        "quote": code["quote_text"],
        "literal_meaning": code["literal_meaning"],
        "alternative_interpretation": "; ".join(code["alternative_interpretations"]),
        "bucket": code["bucket"],
    }


def _review_out(review):
    return {
        "id": review["id"], "reviewer": review["reviewer"],
        "reviewer_id": review["reviewer_id"], "rating": review["rating"],
        "text": review["text"], "relative_time": review["relative_time"],
        "published_at": review["published_at"], "months_ago": review["months_ago"],
        "bucket": bucket_for(review["months_ago"]),
        "sentiment": review.get("sentiment"), "sentiment_score": review.get("sentiment_score"),
        "owner_response": review.get("owner_response"),
        "photo_count": review.get("photo_count", 0),
    }
