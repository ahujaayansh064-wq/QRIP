"""Sentiment thresholds, shared by every stage of the review pipeline."""

POSITIVE_CUT = 0.12
NEGATIVE_CUT = -0.12


def sentiment_label(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "neutral"
    if value >= POSITIVE_CUT:
        return "positive"
    if value <= NEGATIVE_CUT:
        return "negative"
    return "neutral"


def blended_sentiment(text_valence, rating):
    """Text carries the meaning; the star rating corroborates it.

    Reviewers routinely leave four stars beside a paragraph of complaint, which
    is exactly the contradiction this report exists to surface — so the text
    keeps the larger weight.
    """
    if rating is None:
        return round(float(text_valence), 3)
    star_valence = (float(rating) - 3.0) / 2.0
    return round(0.65 * float(text_valence) + 0.35 * star_valence, 3)
