"""Function 1 — thematic analysis.

Reads every review and produces a codebook: one row per coded idea, with the
verbatim quote it came from, what it literally says, the emotion behind it, what
the reviewer was doing by saying it, and a confidence score. Then it proposes
candidate themes by grouping codes that talk about the same thing.

Claude does the coding when a key is configured, because the point of this pass
is to read *context* — "the price list had changed" is a pricing failure whether
or not the word "expensive" appears. The lexicon engine is the fallback, and it
is honest about being a weaker reading.
"""
from collections import Counter, defaultdict

import claude
from analysis import clustering as cl
from analysis import coding
from analysis import textproc as tp

from .scoring import sentiment_label
from .sources import bucket_for

BATCH_SIZE = 6
MAX_CODES_PER_REVIEW = 6

SYSTEM = (
    "You are a qualitative researcher performing open coding on customer reviews "
    "for a business-improvement study. You code for meaning in context, not for "
    "keywords: a reviewer who says 'the price list had changed' is reporting a "
    "pricing-transparency failure even though no negative word appears, and a "
    "reviewer who says 'I was in and out in ten minutes' is praising process "
    "speed. Never invent content. Every quote must appear verbatim in the review "
    "you took it from."
)

CODE_SCHEMA = {
    "type": "object",
    "properties": {
        "reviews": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "review_index": {"type": "integer"},
                    "codes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string"},
                                "quote": {"type": "string"},
                                "literal_meaning": {"type": "string"},
                                "emotion": {"type": "string"},
                                "intent": {"type": "string"},
                                "valence": {"type": "number"},
                                "confidence": {"type": "number"},
                                "negative_case": {"type": "boolean"},
                            },
                            "required": ["code", "quote", "literal_meaning", "emotion",
                                         "intent", "valence", "confidence",
                                         "negative_case"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["review_index", "codes"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["reviews"],
    "additionalProperties": False,
}


def run(reviews, business_name="", on_usage=None, on_progress=None):
    """Code every review and propose candidate themes."""
    engine = "claude" if claude.configured() else "local"
    codes = []
    if engine == "claude":
        codes = _code_with_claude(reviews, business_name, on_usage, on_progress)
        if not codes:
            engine = "local"
    if not codes:
        codes = _code_locally(reviews)

    themes = _candidate_themes(codes, len(reviews))
    return {"codes": codes, "themes": themes, "engine": engine}


# --- Claude coding --------------------------------------------------------

def _code_with_claude(reviews, business_name, on_usage, on_progress):
    out = []
    batches = list(claude.batched(list(enumerate(reviews)), BATCH_SIZE))
    for number, batch in enumerate(batches):
        if on_progress:
            on_progress(number / max(len(batches), 1))
        payload = []
        for index, review in batch:
            payload.append({
                "review_index": index,
                "reviewer": review["reviewer"],
                "rating": review["rating"],
                "posted": review.get("relative_time") or review.get("published_at"),
                "review": review["text"][:4000],
            })
        prompt = _coding_prompt(business_name, payload)
        result = claude.structured(SYSTEM, prompt, CODE_SCHEMA, effort="medium",
                                   max_tokens=16000, on_usage=on_usage)
        if result is None:
            return []
        out.extend(_absorb(result, reviews))
    if on_progress:
        on_progress(1.0)
    return out


def _coding_prompt(business_name, payload):
    import json
    return (
        "Business under review: " + (business_name or "(not named)") + "\n\n"
        "Code each review below. For every distinct idea a reviewer expresses, "
        "produce one code:\n"
        "- code: a short analytic label, 2-5 words, naming the idea rather than "
        "quoting it (e.g. 'unexplained price increase', 'staff remembered me').\n"
        "- quote: the exact sentence or clause from the review that carries it, "
        "copied verbatim.\n"
        "- literal_meaning: what the reviewer is literally reporting, in one "
        "plain sentence.\n"
        "- emotion: the feeling behind it in one word (frustration, relief, "
        "gratitude, anger, anxiety, pride, disappointment, trust, resignation, "
        "or neutral).\n"
        "- intent: what the reviewer is doing by saying it, as a short phrase "
        "beginning with 'To' (e.g. 'To warn other customers about hidden costs').\n"
        "- valence: -1.0 (strongly negative) to 1.0 (strongly positive) for this "
        "specific idea, judged from meaning in context and not from the star "
        "rating.\n"
        "- confidence: 0.0-1.0, how firmly the quote supports the code.\n"
        "- negative_case: true when this idea runs against the overall tone of "
        "the same review (praise inside a complaint, or vice versa).\n\n"
        "Give between 1 and " + str(MAX_CODES_PER_REVIEW) + " codes per review. "
        "A short review may only warrant one. Do not code the same idea twice.\n\n"
        "Reviews:\n" + json.dumps(payload, ensure_ascii=False)
    )


def _absorb(result, reviews):
    out = []
    for entry in result.get("reviews") or []:
        try:
            review = reviews[int(entry["review_index"])]
        except (KeyError, ValueError, IndexError, TypeError):
            continue
        for item in (entry.get("codes") or [])[:MAX_CODES_PER_REVIEW]:
            quote = str(item.get("quote") or "").strip()
            label = str(item.get("code") or "").strip()
            if not quote or not label:
                continue
            valence = _number(item.get("valence"), -1.0, 1.0, 0.0)
            out.append({
                "code": label[:120],
                "participant": review["reviewer"],
                "reviewer_id": review["reviewer_id"],
                "review_id": review["id"],
                "rating": review["rating"],
                "months_ago": review["months_ago"],
                "bucket": bucket_for(review["months_ago"]),
                "quote": quote[:1200],
                "literal_meaning": str(item.get("literal_meaning") or "").strip()[:600],
                "emotion": str(item.get("emotion") or "neutral").strip().lower()[:40],
                "intent": str(item.get("intent") or "").strip()[:300],
                "valence": round(valence, 3),
                "sentiment": sentiment_label(valence),
                "confidence": round(_number(item.get("confidence"), 0.0, 1.0, 0.7), 3),
                "negative_case": bool(item.get("negative_case")),
                "themes": [],
                "source": "claude",
            })
    return out


def _number(value, low, high, default):
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return default


# --- local fallback -------------------------------------------------------

def _code_locally(reviews):
    """Lexicon coding. Weaker: it reads words, not context."""
    units = []
    for review in reviews:
        pieces = [piece for piece in tp.split_sentences(review["text"])
                  if len(piece.split()) >= 4] or [review["text"]]
        for index, piece in enumerate(pieces):
            units.append({
                "id": review["id"] + ":" + str(index),
                "transcript_id": review["id"],
                "participant_label": review["reviewer"],
                "idx": index, "turn_idx": 0,
                "text": piece.strip(), "question_context": None,
            })
    if not units:
        return []
    idf = tp.idf_table([tp.stems(unit["text"]) for unit in units])
    raw = coding.code_units(units, idf, "sentence")
    by_review = {review["id"]: review for review in reviews}

    out = []
    for code in raw:
        review = by_review[code["transcript_id"]]
        out.append({
            "code": code["label"],
            "participant": review["reviewer"],
            "reviewer_id": review["reviewer_id"],
            "review_id": review["id"],
            "rating": review["rating"],
            "months_ago": review["months_ago"],
            "bucket": bucket_for(review["months_ago"]),
            "quote": code["quote_text"],
            "literal_meaning": code["literal_meaning"],
            "emotion": code["emotion"],
            "intent": "To " + code["intent"].rstrip("e") + "e the experience"
                      if code["intent"] else "",
            "valence": code["valence"],
            "sentiment": sentiment_label(code["valence"]),
            "confidence": code["confidence"],
            "negative_case": False,
            "themes": [],
            "source": "local",
        })
    return out


# --- candidate themes -----------------------------------------------------

def _candidate_themes(codes, review_count):
    """Group codes that talk about the same thing, as a starting proposal.

    Function 2 is what decides the final themes; this pass only has to give it
    something sensible to argue with.
    """
    if len(codes) < 3:
        return []
    documents = [tp.stems(code["code"] + " " + code["quote"]) for code in codes]
    idf = tp.idf_table(documents)
    concepts, _ = tp.concept_space(documents)
    vectors = [tp.concept_vector(tokens, concepts, idf) for tokens in documents]
    clusters = cl.cluster(vectors, threshold=0.3)

    taken = set()
    themes = []
    for order, members in enumerate(clusters):
        if len(members) < 2:
            continue
        group = [codes[i] for i in members]
        participants = sorted({code["participant"] for code in group})
        valences = [code["valence"] for code in group]
        mean = sum(valences) / len(valences)
        themes.append({
            "theme": cl.name_theme([{
                "phrase": code["code"],
                "quote_text": code["quote"],
                "participant_label": code["participant"],
            } for code in group], idf, taken),
            "description": "",
            "status": "candidate",
            "confidence": round(sum(code["confidence"] for code in group) / len(group), 3),
            "coverage": round(len(participants) / max(review_count, 1), 3),
            "participants": participants,
            "evidence_count": len(group),
            "mean_valence": round(mean, 3),
            "sentiment": sentiment_label(mean),
            "alternative_interpretation": "",
            "code_indexes": list(members),
            "order": order,
        })
    themes.sort(key=lambda theme: -theme["evidence_count"])
    return themes[:12]


def summarise(codes):
    """Counts the UI shows after function 1."""
    return {
        "codes": len(codes),
        "reviewers": len({code["participant"] for code in codes}),
        "emotions": dict(Counter(code["emotion"] for code in codes).most_common(8)),
        "mean_confidence": round(
            sum(code["confidence"] for code in codes) / max(len(codes), 1), 3),
    }
