"""Text processing primitives for the QRIP analysis engine.

Pure stdlib: transcript segmentation, tokenisation, light stemming, phrase
extraction and tf-idf vector maths. Everything downstream (coding, clustering,
the six methodologies) is built on these functions.
"""
import math
import re
from collections import Counter

# --- vocabulary ----------------------------------------------------------

STOPWORDS = set("""
a about above after again against all am an and any are aren't as at be because been
before being below between both but by can cannot could couldn't did didn't do does
doesn't doing don't down during each few for from further had hadn't has hasn't have
haven't having he he'd he'll he's her here here's hers herself him himself his how
how's i i'd i'll i'm i've if in into is isn't it it's its itself let's me more most
mustn't my myself no nor not of off on once only or other ought our ours ourselves out
over own same shan't she she'd she'll she's should shouldn't so some such than that
that's the their theirs them themselves then there there's these they they'd they'll
they're they've this those through to too under until up very was wasn't we we'd we'll
we're we've were weren't what what's when when's where where's which while who who's
whom why why's with won't would wouldn't you you'd you'll you're you've your yours
yourself yourselves yeah yes okay ok um uh er mm hmm like just really kind sort thing
things get got gets go goes going gone know knew think thought say said says one two
three lot lots bit really actually basically maybe well right sure mean means meant
much many quite even also still ever never always sometimes often usually
""".split())

# Words that must survive stopping because they carry analytic weight.
KEEP = {"not", "no", "never", "but", "because", "should", "cannot"}
STOPWORDS -= KEEP

INTERVIEWER_ALIASES = {
    "interviewer", "i", "r", "researcher", "moderator", "facilitator", "q",
    "question", "int", "res", "me", "host",
}

_SPEAKER_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 ._'-]{0,28}?)\s*[:\-–]\s+(.*)$")
_ABBREV = {"mr", "mrs", "ms", "dr", "prof", "st", "e.g", "i.e", "etc", "vs", "no"}
_SENT_RE = re.compile(r"(?<=[.!?…])[\"'”’)]*\s+")
_WORD_RE = re.compile(r"[a-z][a-z'’-]*")
_CLAUSE_RE = re.compile(
    r"\s*(?:,\s+(?:but|and|so|because|although|though|while|whereas|which|who)\s+"
    r"|;\s+|\s+--\s+|\s+—\s+)"
)


def normalise(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_turns(text: str):
    """Split a transcript into speaker turns.

    Returns a list of dicts: {speaker, text, is_participant}. Transcripts with
    no speaker markers fall back to paragraphs attributed to the participant.
    """
    lines = normalise(text).split("\n")
    turns = []
    current = None
    saw_marker = False
    for line in lines:
        raw = line.strip()
        if not raw:
            if current:
                current["text"] += "\n"
            continue
        m = _SPEAKER_RE.match(raw)
        # A marker only counts if the label looks like a name/code, not prose.
        if m and len(m.group(1).split()) <= 3 and not m.group(1).endswith(","):
            saw_marker = True
            speaker = m.group(1).strip()
            body = m.group(2).strip()
            key = speaker.lower().strip(". ")
            is_participant = key not in INTERVIEWER_ALIASES
            current = {"speaker": speaker, "text": body, "is_participant": is_participant}
            turns.append(current)
        elif current is not None:
            current["text"] += " " + raw
        else:
            current = {"speaker": None, "text": raw, "is_participant": True}
            turns.append(current)
    if not saw_marker:
        # No speaker labels: treat paragraphs as participant narrative.
        paras = [p.strip() for p in normalise(text).split("\n\n") if p.strip()]
        if paras:
            turns = [{"speaker": None, "text": p, "is_participant": True} for p in paras]
    for t in turns:
        t["text"] = re.sub(r"\s+", " ", t["text"]).strip()
    return [t for t in turns if t["text"]]


def split_sentences(text: str):
    parts = _SENT_RE.split(text)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if out:
            last = out[-1]
            tail = last.rstrip(".").split()[-1].lower() if last.rstrip(".").split() else ""
            if tail in _ABBREV or len(last) < 12:
                out[-1] = last + " " + p
                continue
        out.append(p)
    return out


def split_clauses(sentence: str):
    parts = [p.strip(" ,;") for p in _CLAUSE_RE.split(sentence)]
    parts = [p for p in parts if len(p.split()) >= 4]
    return parts or [sentence]


def locate(document: str, fragment: str, cursor: int = 0):
    """Find a fragment's character span in the document, tolerant of whitespace.

    Segmentation collapses whitespace, so a unit's text is not always a literal
    substring. Every meaning unit still needs real document offsets — that is
    what makes a quotation highlightable and hand-editable later.
    """
    words = fragment.split()
    if not words:
        return None
    pattern = re.compile(r"\s+".join(re.escape(word) for word in words))
    match = pattern.search(document, cursor)
    if match is None:
        match = pattern.search(document)
    return (match.start(), match.end()) if match else None


def segment(text: str, granularity: str = "sentence"):
    """Segment a transcript into meaning units.

    granularity: 'clause' (fine), 'sentence' (default), 'utterance' (coarse,
    one unit per speaker turn). Each unit carries its character span in the
    normalised document so it can become a quotation.
    """
    units = []
    document = normalise(text)
    cursor = 0
    turns = split_turns(text)
    last_question = None
    for turn_idx, turn in enumerate(turns):
        if not turn["is_participant"]:
            if "?" in turn["text"]:
                last_question = turn["text"].strip()
            else:
                last_question = turn["text"].strip()
            continue
        if granularity == "utterance":
            pieces = [turn["text"]]
        else:
            pieces = split_sentences(turn["text"])
            if granularity == "clause":
                pieces = [c for s in pieces for c in split_clauses(s)]
        for piece in pieces:
            piece = piece.strip()
            if len(piece.split()) < 4:
                continue
            span = locate(document, piece, cursor)
            if span:
                cursor = span[1]
            units.append({
                "turn_idx": turn_idx,
                "speaker": turn["speaker"],
                "text": piece,
                "question_context": last_question,
                "char_start": span[0] if span else 0,
                "char_end": span[1] if span else 0,
            })
    return units


# --- tokens and stems ----------------------------------------------------

_SUFFIX_RULES = [
    ("ational", "ate"), ("tional", "tion"), ("iveness", "ive"), ("fulness", "ful"),
    ("ousness", "ous"), ("ization", "ize"), ("ations", "ate"), ("ization", "ize"),
    ("iness", "y"), ("ement", ""), ("ments", ""), ("ement", ""), ("ance", ""),
    ("ence", ""), ("ness", ""), ("ally", "al"), ("ical", "ic"), ("ing", ""),
    ("ies", "y"), ("ied", "y"), ("ent", ""), ("ers", "er"), ("est", ""),
    ("ful", ""), ("ive", ""), ("ion", ""), ("ise", ""), ("ize", ""),
    ("ed", ""), ("ly", ""), ("es", ""), ("s", ""),
]


def stem(word: str) -> str:
    w = word.lower().strip("'-")
    if len(w) <= 3:
        return w
    for suf, rep in _SUFFIX_RULES:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            base = w[: -len(suf)] + rep
            if len(base) >= 3:
                # undo accidental doubling: "stopp" -> "stop"
                if len(base) > 3 and base[-1] == base[-2] and base[-1] not in "sl":
                    base = base[:-1]
                return base
    return w


def tokenize(text: str):
    return _WORD_RE.findall(text.lower())


def content_tokens(text: str):
    return [t for t in tokenize(text) if t not in STOPWORDS and len(t) > 2]


def stems(text: str):
    return [stem(t) for t in content_tokens(text)]


# --- phrases -------------------------------------------------------------

def phrases(text: str, max_len: int = 3):
    """Maximal runs of content words, up to max_len, as surface phrases."""
    toks = tokenize(text)
    out = []
    run = []
    for t in toks:
        # KEEP words (not, because, never...) carry analytic weight but make poor
        # label material, so they break a phrase run rather than joining it.
        if t in STOPWORDS or t in KEEP or len(t) <= 2:
            if run:
                out.extend(_runs(run, max_len))
                run = []
        else:
            run.append(t)
    if run:
        out.extend(_runs(run, max_len))
    return out


def _runs(run, max_len):
    res = []
    n = len(run)
    for size in range(1, min(max_len, n) + 1):
        for i in range(n - size + 1):
            res.append(" ".join(run[i:i + size]))
    return res


# --- vector maths --------------------------------------------------------

def idf_table(documents):
    """documents: list of token lists. Returns {term: idf}."""
    n = len(documents) or 1
    df = Counter()
    for doc in documents:
        df.update(set(doc))
    return {term: math.log((n + 1) / (count + 0.5)) + 1.0 for term, count in df.items()}


def tfidf(tokens, idf):
    if not tokens:
        return {}
    tf = Counter(tokens)
    total = sum(tf.values())
    vec = {}
    for term, count in tf.items():
        vec[term] = (count / total) * idf.get(term, 1.0)
    return normalise_vec(vec)


def cooccurrence(documents, top_k=4, min_count=2):
    """Term -> related terms, from within-document co-occurrence.

    Interview sentences are short and share few exact words, so raw tf-idf
    cosine sees almost nothing in common between two segments about the same
    experience. Expanding each vector along its strongest co-occurrence links
    lets 'referral' and 'letter' pull together the way a reader would.
    """
    df = Counter()
    pair = Counter()
    for doc in documents:
        terms = sorted(set(doc))
        df.update(terms)
        for i in range(len(terms)):
            for j in range(i + 1, len(terms)):
                pair[(terms[i], terms[j])] += 1
    related = {}
    for (a, b), count in pair.items():
        if count < min_count:
            continue
        score = count / math.sqrt(df[a] * df[b])
        related.setdefault(a, []).append((b, score))
        related.setdefault(b, []).append((a, score))
    for term, items in related.items():
        items.sort(key=lambda kv: -kv[1])
        del items[top_k:]
    return related


def concept_space(documents, threshold=0.18, min_df=1):
    """Group vocabulary into concepts from co-occurrence, then index terms to them.

    Two participants rarely describe the same experience with the same words, so
    comparing segments term-by-term finds almost nothing. Clustering the
    vocabulary first ('referral', 'letter', 'form', 'paperwork') gives every
    segment a position in a dense concept space where those segments do meet.

    Returns (term -> concept id, concept id -> label terms).
    """
    df = Counter()
    pair = Counter()
    for doc in documents:
        terms = sorted(set(doc))
        df.update(terms)
        for i in range(len(terms)):
            for j in range(i + 1, len(terms)):
                pair[(terms[i], terms[j])] += 1
    vocab = sorted([t for t, n in df.items() if n >= min_df])
    if len(vocab) < 4:
        return {}, {}
    profiles = {t: {t: 1.0} for t in vocab}
    for (a, b), count in pair.items():
        if a not in profiles or b not in profiles:
            continue
        score = count / math.sqrt(df[a] * df[b])
        profiles[a][b] = score
        profiles[b][a] = score
    profiles = {t: normalise_vec(v) for t, v in profiles.items()}

    # leader clustering over the vocabulary, most connected terms first
    strength = {t: sum(profiles[t].values()) for t in vocab}
    order = sorted(vocab, key=lambda t: (-strength[t], t))
    assign = {}
    concepts = {}
    for term in order:
        if term in assign:
            continue
        cid = "c" + str(len(concepts))
        concepts[cid] = [term]
        assign[term] = cid
        for other in order:
            if other in assign:
                continue
            if cosine(profiles[term], profiles[other]) >= threshold:
                assign[other] = cid
                concepts[cid].append(other)
    # Terms seen only once have no profile of their own; place them with the
    # concept that dominates the segment they appeared in, so rare wording still
    # lands somewhere rather than falling out of the space entirely.
    for doc in documents:
        local = Counter(assign[t] for t in doc if t in assign)
        if not local:
            continue
        cid = local.most_common(1)[0][0]
        for term in doc:
            if term not in assign:
                assign[term] = cid
                concepts[cid].append(term)
    labels = {cid: terms[:6] for cid, terms in concepts.items()}
    return assign, labels


def concept_vector(tokens, assign, idf, blend=0.55):
    """Blend a concept-space vector with the literal term vector."""
    term_vec = tfidf(tokens, idf)
    if not assign:
        return term_vec
    mapped = [assign.get(t, t) for t in tokens]
    concept_vec = tfidf(mapped, idf)
    out = {}
    for k, v in concept_vec.items():
        out["k:" + k] = v * blend
    for k, v in term_vec.items():
        out[k] = out.get(k, 0.0) + v * (1.0 - blend)
    return normalise_vec(out)


def expand(vec, related, alpha=0.45):
    """Blend in co-occurring terms so near-synonymous segments align."""
    if not related:
        return vec
    out = dict(vec)
    for term, weight in vec.items():
        for other, score in related.get(term, ()):
            out[other] = out.get(other, 0.0) + weight * score * alpha
    return normalise_vec(out)


def normalise_vec(vec):
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {k: v / norm for k, v in vec.items()}


def cosine(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


def centroid(vectors):
    acc = {}
    for vec in vectors:
        for k, v in vec.items():
            acc[k] = acc.get(k, 0.0) + v
    if not acc:
        return {}
    n = len(vectors)
    return normalise_vec({k: v / n for k, v in acc.items()})


def top_terms(vec, n=6):
    return [k for k, _ in sorted(vec.items(), key=lambda kv: -kv[1])[:n]]


def titlecase(phrase: str) -> str:
    words = phrase.split()
    if not words:
        return phrase
    small = {"and", "or", "of", "the", "a", "an", "in", "on", "to", "for", "with", "as"}
    out = [words[0].capitalize()]
    for w in words[1:]:
        out.append(w if w in small else w.capitalize())
    return " ".join(out)


def truncate(text: str, limit: int = 220) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"
