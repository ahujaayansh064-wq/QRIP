"""Open coding: meaning units in, interpreted codes out.

Each code carries a label, a literal restatement, an emotion and intent
reading, a confidence score and — importantly for reflexive practice —
alternative interpretations the researcher should weigh.
"""
import math
import re
from collections import Counter

from . import lexicons as lx
from . import textproc as tp

EMOTION_FRAMES = {
    "frustration": "Frustration with {p}",
    "anxiety": "Anxiety about {p}",
    "sadness": "Loss and sadness around {p}",
    "anger": "Anger at {p}",
    "relief": "Relief at {p}",
    "hope": "Hope for {p}",
    "gratitude": "Gratitude for {p}",
    "pride": "Pride in {p}",
    "confusion": "Confusion about {p}",
    "trust": "Trust in {p}",
    "distrust": "Distrust of {p}",
    "resignation": "Resignation about {p}",
}

INTENT_FRAMES = {
    "recounting": "Account of {p}",
    "evaluating": "Judgement of {p}",
    "comparing": "Comparison of {p}",
    "justifying": "Explanation of {p}",
    "recommending": "Call for {p}",
    "contrasting": "Tension around {p}",
    "hypothesising": "Imagining {p}",
    "describing": "Description of {p}",
}


def emotion_scores(text: str):
    toks = tp.tokenize(text)
    stemmed = [tp.stem(t) for t in toks]
    joined = " ".join(toks)
    scores = {}
    for name, cues in lx.EMOTION_STEMS.items():
        hit = 0.0
        for cue in cues:
            if "-" in cue:
                if cue.replace("-", " ") in joined:
                    hit += 1.2
            elif any(s.startswith(cue) or cue.startswith(s) and len(s) > 3 for s in stemmed):
                hit += 1.0
        if hit:
            scores[name] = hit
    return scores


def valence(text: str) -> float:
    toks = tp.tokenize(text)
    score = 0.0
    window_negated = False
    for i, tok in enumerate(toks):
        if tok in lx.NEGATORS:
            window_negated = True
            continue
        weight = 1.0
        if i > 0 and toks[i - 1] in lx.INTENSIFIERS:
            weight = 1.5
        val = 0.0
        if tok in lx.POSITIVE:
            val = 1.0
        elif tok in lx.NEGATIVE:
            val = -1.0
        if val:
            if window_negated:
                val = -val * 0.85
                window_negated = False
            score += val * weight
    em = emotion_scores(text)
    for name, hits in em.items():
        score += lx.EMOTION_VALENCE.get(name, 0.0) * min(hits, 2.0) * 0.6
    n = max(len(toks) / 12.0, 1.0)
    return max(-1.0, min(1.0, score / n))


_CUE_CACHE = {}


def _cue_pattern(cue: str):
    """Cues must match whole words: 'if' should not fire inside 'difference'."""
    pattern = _CUE_CACHE.get(cue)
    if pattern is None:
        pattern = re.compile(r"(?<![a-z])" + re.escape(cue.lower()) + r"(?![a-z])")
        _CUE_CACHE[cue] = pattern
    return pattern


def detect_intent(text: str):
    low = text.lower()
    best, best_hits = None, 0
    for name, cues in lx.INTENTS.items():
        hits = sum(1 for cue in cues if _cue_pattern(cue).search(low))
        if hits > best_hits:
            best, best_hits = name, hits
    return best or "describing", best_hits


def count_hits(text: str, cues) -> int:
    low = text.lower()
    return sum(1 for cue in cues if _cue_pattern(cue).search(low))


def phrase_frequencies(units):
    """How often each surface phrase recurs across the corpus."""
    df = Counter()
    for unit in units:
        df.update(set(tp.phrases(unit["text"], max_len=3)))
    return df


def salient_phrase(unit_text: str, idf, used: Counter, phrase_df=None):
    """Pick the phrase that best names what this unit is about."""
    cands = tp.phrases(unit_text, max_len=3)
    if not cands:
        toks = tp.content_tokens(unit_text)
        return toks[0] if toks else "this account"
    scored = []
    for phrase in set(cands):
        words = phrase.split()
        # a label that opens on a verb reads like a fragment: trim it
        while words and words[0] in lx.VERBS:
            words = words[1:]
        if not words or all(w in lx.LOW_CONTENT for w in words):
            continue
        phrase = " ".join(words)
        weight = sum(idf.get(tp.stem(w), 1.0) for w in words) / len(words)
        # prefer 2-word phrases: they name a topic without being a whole clause
        length_bonus = {1: 0.88, 2: 1.16, 3: 1.02}[min(len(words), 3)]
        if any(w in lx.LOW_CONTENT for w in words):
            weight *= 0.6
        if all(w.endswith("ly") for w in words):
            weight *= 0.3
        # a phrase other participants also use names a shared object of concern;
        # a one-off phrase names this sentence only
        if phrase_df is not None:
            weight *= 1.0 + 0.75 * math.log(1 + phrase_df.get(phrase, 0))
        # avoid reusing the same label everywhere
        repeat_penalty = 1.0 / (1.0 + 0.35 * used[phrase])
        scored.append((weight * length_bonus * repeat_penalty, phrase))
    if not scored:
        # nothing survived the filters — fall back to the most distinctive word
        toks = tp.content_tokens(unit_text)
        if toks:
            return max(toks, key=lambda t: idf.get(tp.stem(t), 1.0))
        return "this account"
    scored.sort(key=lambda s: (-s[0], s[1]))
    return scored[0][1]


def literal_meaning(text: str) -> str:
    words = text.split()
    trimmed = [w for w in words if w.lower().strip(",.") not in {"um", "uh", "erm", "like"}]
    return tp.truncate(" ".join(trimmed), 180)


def alternatives(text, emotions, negated, hedged, phrase):
    out = []
    ranked = sorted(emotions.items(), key=lambda kv: -kv[1])
    if len(ranked) > 1 and ranked[1][1] >= ranked[0][1] * 0.6:
        out.append(
            "Could equally be coded as " + ranked[1][0] + " rather than "
            + ranked[0][0] + " — both registers are present in the same breath."
        )
    if negated:
        out.append(
            "Contains negation; the speaker may be rejecting the framing of '"
            + phrase + "' rather than affirming it."
        )
    if hedged:
        out.append(
            "Hedged phrasing suggests a tentative account, not a settled claim; "
            "treat as provisional."
        )
    if not out:
        out.append(
            "Read here as manifest content about '" + phrase
            + "'; a latent reading would foreground what is left unsaid."
        )
    return out[:3]


def code_units(units, idf, granularity="sentence"):
    """units: list of dicts with text/participant_label/ids. Returns code dicts."""
    phrase_df = phrase_frequencies(units)
    used = Counter()
    codes = []
    for unit in units:
        text = unit["text"]
        toks = tp.tokenize(text)
        if len(toks) < 4:
            continue
        ems = emotion_scores(text)
        emotion = max(ems, key=ems.get) if ems else "neutral"
        intent, intent_hits = detect_intent(text)
        phrase = salient_phrase(text, idf, used, phrase_df)
        used[phrase] += 1
        if emotion != "neutral":
            label = EMOTION_FRAMES[emotion].format(p=phrase)
        else:
            label = INTENT_FRAMES[intent].format(p=phrase)
        label = label[0].upper() + label[1:]

        negated = any(t in lx.NEGATORS for t in toks)
        hedged = any(t in lx.HEDGES for t in toks)
        n_words = len(toks)

        conf = 0.55
        if 8 <= n_words <= 45:
            conf += 0.12
        elif n_words < 6:
            conf -= 0.12
        if ems:
            conf += min(max(ems.values()), 3.0) * 0.04
        if intent_hits:
            conf += min(intent_hits, 3) * 0.025
        if len(phrase.split()) >= 2:
            conf += 0.05
        if hedged:
            conf -= 0.11
        if negated:
            conf -= 0.05
        conf = round(max(0.2, min(0.97, conf)), 3)

        codes.append({
            "meaning_unit_id": unit["id"],
            "transcript_id": unit["transcript_id"],
            "participant_label": unit["participant_label"],
            "label": label,
            "literal_meaning": literal_meaning(text),
            "emotion": emotion,
            "intent": intent,
            "valence": round(valence(text), 3),
            "confidence": conf,
            "alternative_interpretations": alternatives(text, ems, negated, hedged, phrase),
            "quote_text": text,
            "phrase": phrase,
            "stems": tp.stems(text) + [tp.stem(w) for w in phrase.split()],
            "turn_idx": unit.get("turn_idx", 0),
            "idx": unit.get("idx", 0),
            "question_context": unit.get("question_context"),
        })
    return codes
