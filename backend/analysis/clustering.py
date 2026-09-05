"""Code -> theme clustering, theme naming and theme-level statistics."""
from collections import Counter, defaultdict

from . import textproc as tp
from . import lexicons as lx

STATUS_CONFIRMED = "confirmed"
STATUS_CANDIDATE = "candidate"
STATUS_REVIEW = "review"


def build_vectors(codes, idf, concepts=None, related=None):
    vecs = []
    for code in codes:
        toks = list(code["stems"])
        # the salient phrase names the code, so give it extra pull
        toks += [tp.stem(w) for w in code["phrase"].split()] * 2
        # affect and stance are part of what makes two segments "the same thing"
        if code.get("emotion") and code["emotion"] != "neutral":
            toks += ["emo:" + code["emotion"]] * 2
        if code.get("intent"):
            toks.append("int:" + code["intent"])
        vec = tp.concept_vector(toks, concepts or {}, idf)
        vecs.append(tp.expand(vec, related) if related else vec)
    return vecs


def cluster(vectors, threshold=0.35, passes=2):
    """Leader clustering with centroid refinement.

    Deterministic, O(n^2), and it produces clusters a researcher can reason
    about: each starts from the most central code and absorbs its neighbours.
    """
    n = len(vectors)
    if n == 0:
        return []
    sims = [[0.0] * n for _ in range(n)]
    centrality = [0.0] * n
    for i in range(n):
        for j in range(i + 1, n):
            s = tp.cosine(vectors[i], vectors[j])
            sims[i][j] = sims[j][i] = s
            centrality[i] += s
            centrality[j] += s

    order = sorted(range(n), key=lambda i: (-centrality[i], i))
    assigned = [-1] * n
    seeds = []
    for i in order:
        if assigned[i] != -1:
            continue
        cid = len(seeds)
        seeds.append(i)
        assigned[i] = cid
        for j in order:
            if assigned[j] == -1 and sims[i][j] >= threshold:
                assigned[j] = cid

    for _ in range(passes):
        groups = defaultdict(list)
        for i, cid in enumerate(assigned):
            groups[cid].append(i)
        centroids = {cid: tp.centroid([vectors[i] for i in members])
                     for cid, members in groups.items()}
        changed = False
        for i in range(n):
            best_cid, best_sim = assigned[i], -1.0
            for cid, cvec in centroids.items():
                s = tp.cosine(vectors[i], cvec)
                if s > best_sim:
                    best_cid, best_sim = cid, s
            if best_sim >= threshold * 0.75 and best_cid != assigned[i]:
                assigned[i] = best_cid
                changed = True
        if not changed:
            break

    groups = defaultdict(list)
    for i, cid in enumerate(assigned):
        groups[cid].append(i)
    clusters = [sorted(members) for members in groups.values()]

    # A cluster holding a fifth of the corpus is a container, not a theme: cut it
    # again at a tighter threshold and keep the split if it separates cleanly.
    limit = max(12, int(0.18 * n))
    refined = []
    for members in clusters:
        if len(members) > limit and threshold < 0.8:
            sub = cluster([vectors[i] for i in members],
                          threshold=min(0.8, threshold * 1.6), passes=1)
            keepers = [s for s in sub if len(s) >= 3]
            if len(keepers) >= 2:
                for group in sub:
                    refined.append(sorted(members[i] for i in group))
                continue
        refined.append(members)
    refined.sort(key=lambda m: (-len(m), m[0]))
    return refined


def cohesion(vectors, members):
    if len(members) < 2:
        return 0.5
    total, pairs = 0.0, 0
    for a in range(len(members)):
        for b in range(a + 1, len(members)):
            total += tp.cosine(vectors[members[a]], vectors[members[b]])
            pairs += 1
    return total / pairs if pairs else 0.5


def name_theme(member_codes, idf, taken):
    """Name a cluster after the words that actually recur across its members.

    Salience alone picks the rarest phrase in the cluster, which reads as noise.
    What names a theme is the word several participants keep returning to, so
    recurrence is weighted first and distinctiveness second.
    """
    doc_freq = Counter()
    for code in member_codes:
        seen = set()
        for word in tp.content_tokens(code["phrase"]) + tp.content_tokens(code["quote_text"]):
            if word in lx.LOW_CONTENT or word in lx.VERBS or word in tp.KEEP:
                continue
            stemmed = tp.stem(word)
            if stemmed in seen:
                continue
            seen.add(stemmed)
            doc_freq[word] += 1

    # keyness: how much more this cluster leans on a word than the corpus does
    inside = sum(doc_freq.values()) or 1

    def salience(word, count):
        share = count / inside
        corpus = 1.0 / max(idf.get(tp.stem(word), 1.0), 0.2)
        return (share / (corpus + 0.02)) * (1.0 + 0.5 * (count - 1))

    ranked = sorted([kv for kv in doc_freq.items() if kv[1] >= 2] or list(doc_freq.items()),
                    key=lambda kv: (-salience(*kv), kv[0]))
    if not ranked:
        primary_word = "unnamed pattern"
    else:
        primary_word = ranked[0][0]

    # prefer a natural two-word phrase from the data that contains that word
    phrase_counts = Counter(c["phrase"] for c in member_codes)
    primary = primary_word
    best = 0
    for phrase, count in phrase_counts.items():
        words = phrase.split()
        if primary_word in words and len(words) >= 2 and count >= best:
            primary, best = phrase, count

    secondary = None
    primary_stems = {tp.stem(w) for w in primary.split()}
    for word, count in ranked[1:6]:
        if tp.stem(word) not in primary_stems and count >= 2:
            secondary = word
            break

    name = tp.titlecase(primary)
    if secondary and len(name) + len(secondary) < 40:
        name = name + " and " + secondary
    base, i = name, 2
    while name.lower() in taken:
        name = base + " (" + str(i) + ")"
        i += 1
    taken.add(name.lower())
    return name


def describe_theme(member_codes, participants, total_participants, mean_valence, cohesion_score):
    emotions = Counter(c["emotion"] for c in member_codes if c["emotion"] != "neutral")
    intents = Counter(c["intent"] for c in member_codes)
    phrases = [p for p, _ in Counter(c["phrase"] for c in member_codes).most_common(4)]
    tone = "broadly negative" if mean_valence < -0.15 else (
        "broadly positive" if mean_valence > 0.15 else "mixed or neutral")
    bits = []
    bits.append(
        "Present in " + str(len(participants)) + " of " + str(total_participants)
        + " participants across " + str(len(member_codes)) + " coded segments."
    )
    if emotions:
        top_em, top_n = emotions.most_common(1)[0]
        share = int(round(100.0 * top_n / len(member_codes)))
        if share >= 25:
            bits.append("Dominant affect is " + top_em + " (" + str(share)
                        + "% of segments); overall valence reads " + tone + ".")
        else:
            bits.append("Affect is mostly unmarked; where it surfaces it is " + top_em
                        + " (" + str(share) + "% of segments). Overall valence reads "
                        + tone + ".")
    else:
        bits.append("Affect is largely unmarked; the register is descriptive and " + tone + ".")
    if intents:
        bits.append("Participants are mostly " + intents.most_common(1)[0][0] + " here.")
    if phrases:
        bits.append("Recurring language: " + ", ".join("'" + p + "'" for p in phrases) + ".")
    bits.append("Internal cohesion " + str(round(cohesion_score, 2))
                + " (mean pairwise similarity of member codes).")
    return " ".join(bits)


def alternative_reading(member_codes):
    emotions = Counter(c["emotion"] for c in member_codes if c["emotion"] != "neutral")
    ranked = emotions.most_common(3)
    if len(ranked) >= 2:
        return (
            "Read through a " + ranked[1][0] + " lens rather than " + ranked[0][0]
            + ", this cluster becomes less an account of what the service did wrong "
              "and more an account of what participants had to carry. The same quotes "
              "support both readings; the choice is interpretive, not empirical."
        )
    parts = sorted({c["participant_label"] for c in member_codes})
    if len(parts) <= 2:
        return (
            "Concentrated in " + ", ".join(parts) + ". It may be an idiographic "
            "pattern rather than a shared theme — treat as a case-level finding "
            "until corroborated."
        )
    return (
        "An alternative reading treats this as context rather than a theme in its "
        "own right: the material may be better placed as a condition shaping the "
        "other themes."
    )


def summarise(codes, vectors, clusters, controls, total_participants):
    """Turn raw clusters into theme records plus per-code assignment."""
    themes = []
    taken = set()
    total_codes = len(codes) or 1
    min_quotes = controls.get("min_supporting_quotations", 3)
    min_participants = controls.get("participant_frequency_threshold", 2)
    conf_threshold = controls.get("confidence_threshold", 0.55)

    min_members = max(2, min(min_quotes, 3)) if len(codes) > 30 else 1
    for order, members in enumerate(clusters):
        if len(members) < min_members:
            # too thin to call a theme; these codes stay unassigned and are shown
            # to the researcher as unclustered material rather than padded out
            continue
        member_codes = [codes[i] for i in members]
        participants = sorted({c["participant_label"] for c in member_codes})
        coh = cohesion(vectors, members)
        mean_conf = sum(c["confidence"] for c in member_codes) / len(member_codes)
        mean_val = sum(c["valence"] for c in member_codes) / len(member_codes)
        confidence = round(max(0.05, min(0.99, mean_conf * (0.7 + 0.3 * min(coh * 2, 1.0)))), 3)
        coverage = round(len(member_codes) / total_codes, 4)

        if (len(member_codes) >= min_quotes and len(participants) >= min_participants
                and confidence >= conf_threshold):
            status = STATUS_CONFIRMED
        elif len(member_codes) >= max(2, min_quotes - 1) or len(participants) >= min_participants:
            status = STATUS_REVIEW
        else:
            status = STATUS_CANDIDATE

        theme = {
            "name": name_theme(member_codes, controls.get("idf", {}), taken),
            "description": describe_theme(member_codes, participants, total_participants,
                                          mean_val, coh),
            "status": status,
            "confidence": confidence,
            "coverage": coverage,
            "participant_count": len(participants),
            "alternative_interpretation": alternative_reading(member_codes),
            "order_idx": order,
            "member_idx": members,
            "mean_valence": round(mean_val, 3),
            "cohesion": round(coh, 3),
            "participants": participants,
            "centroid": tp.centroid([vectors[i] for i in members]),
        }
        # negative cases: members pulling against the theme's dominant valence
        for i in members:
            code = codes[i]
            opposed = (mean_val < -0.1 and code["valence"] > 0.25) or \
                      (mean_val > 0.1 and code["valence"] < -0.25)
            code["is_negative_case"] = 1 if opposed else 0
        themes.append(theme)
    return themes


def merge_suggestions(themes, threshold):
    """Theme pairs that sit just below the clustering cut — candidates to merge."""
    out = []
    for i in range(len(themes)):
        for j in range(i + 1, len(themes)):
            a, b = themes[i], themes[j]
            sim = tp.cosine(a.get("centroid", {}), b.get("centroid", {}))
            shared = set(tp.top_terms(a.get("centroid", {}), 8)) & \
                set(tp.top_terms(b.get("centroid", {}), 8))
            if sim >= threshold * 0.62 or len(shared) >= 3:
                reasons = []
                if sim:
                    reasons.append("centroid similarity " + str(round(sim, 3))
                                   + " (cut is " + str(round(threshold, 3)) + ")")
                if shared:
                    reasons.append("shared vocabulary: " + ", ".join(sorted(shared)[:4]))
                overlap = set(a.get("participants", [])) & set(b.get("participants", []))
                if overlap:
                    reasons.append(str(len(overlap)) + " participants contribute to both")
                out.append({
                    "theme_a_id": a.get("id"),
                    "theme_b_id": b.get("id"),
                    "theme_a_name": a["name"],
                    "theme_b_name": b["name"],
                    "similarity": round(sim, 3),
                    "rationale": "; ".join(reasons) + ".",
                })
    out.sort(key=lambda s: -s["similarity"])
    return out[:12]


def subthemes(member_codes, vectors, members, idf, threshold):
    """Split one theme into sub-patterns at a tighter cut (used by thematic analysis)."""
    if len(members) < 4:
        return []
    sub_vectors = [vectors[i] for i in members]
    subs = cluster(sub_vectors, threshold=min(0.85, threshold + 0.22), passes=1)
    if len(subs) < 2:
        return []
    taken = set()
    out = []
    for group in subs:
        if len(group) < 2:
            continue
        codes_in = [member_codes[i] for i in group]
        out.append({
            "name": name_theme(codes_in, idf, taken),
            "quote_count": len(codes_in),
            "participants": sorted({c["participant_label"] for c in codes_in}),
            "example": tp.truncate(codes_in[0]["quote_text"], 200),
        })
    return out[:5]
