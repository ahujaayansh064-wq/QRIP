"""The manual-analysis layer: quotations, the codebook, groups, memos, typed
links, networks, code queries and inter-coder agreement.

Automatic coding and hand coding write to the same three objects — a quotation
(a span of a document), a codebook entry, and an application joining them — so a
researcher can take over anything the machine produced, and the machine can be
measured against the researcher.
"""
import json
import math
from collections import Counter, defaultdict

import db

PALETTE = [
    "#2B4570", "#2F6F4E", "#8A6D3B", "#B5541B", "#5B4B8A", "#1F6F7A",
    "#7A2E4A", "#4A6B2A", "#A34A2A", "#3C5A9A", "#8A3A5F", "#4F5D66",
]

RELATIONS = [
    "is associated with",
    "is part of",
    "is a",
    "is cause of",
    "is consequence of",
    "contradicts",
    "supports",
    "explains",
    "precedes",
]


def colour_for(project_id: str, name: str) -> str:
    """Stable colour per code name, spread across the palette."""
    used = db.q1("SELECT COUNT(*) AS n FROM codebook WHERE project_id=?", (project_id,))["n"]
    seed = sum(ord(ch) for ch in name)
    return PALETTE[(used + seed) % len(PALETTE)]


# --- codebook -------------------------------------------------------------

def ensure_code(project_id, name, created_by="user", definition=None, color=None):
    """Fetch a codebook entry by name, creating it if this is its first use."""
    name = (name or "").strip()
    if not name:
        raise ValueError("A code name is required.")
    existing = db.q1("SELECT * FROM codebook WHERE project_id=? AND lower(name)=lower(?)",
                     (project_id, name))
    if existing:
        return existing
    order = db.q1("SELECT COALESCE(MAX(order_idx), 0) + 1 AS n FROM codebook WHERE project_id=?",
                  (project_id,))["n"]
    code_id = db.new_id()
    db.insert("codebook", {
        "id": code_id, "project_id": project_id, "name": name,
        "color": color or colour_for(project_id, name),
        "definition": definition, "created_by": created_by,
        "created_at": db.now(), "order_idx": order,
    })
    return db.q1("SELECT * FROM codebook WHERE id=?", (code_id,))


def codebook(project_id, with_stats=True):
    rows = db.q("SELECT * FROM codebook WHERE project_id=? ORDER BY order_idx, name",
                (project_id,))
    if not with_stats:
        return [dict(row) for row in rows]

    grounded = Counter()
    participants = defaultdict(set)
    for row in db.q("SELECT code_id, participant_label FROM codes WHERE project_id=?",
                    (project_id,)):
        if row["code_id"]:
            grounded[row["code_id"]] += 1
            participants[row["code_id"]].add(row["participant_label"])

    density = Counter()
    for row in db.q("SELECT source_type, source_id, target_type, target_id FROM links"
                    " WHERE project_id=?", (project_id,)):
        if row["source_type"] == "code":
            density[row["source_id"]] += 1
        if row["target_type"] == "code":
            density[row["target_id"]] += 1

    memo_counts = Counter()
    for row in db.q("SELECT target_id FROM memo_links WHERE target_type='code'"):
        memo_counts[row["target_id"]] += 1

    groups = defaultdict(list)
    for row in db.q("SELECT m.code_id, g.name FROM code_group_members m"
                    " JOIN code_groups g ON g.id = m.group_id WHERE g.project_id=?",
                    (project_id,)):
        groups[row["code_id"]].append(row["name"])

    out = []
    for row in rows:
        entry = dict(row)
        entry["groundedness"] = grounded.get(row["id"], 0)
        entry["density"] = density.get(row["id"], 0)
        entry["participants"] = len(participants.get(row["id"], ()))
        entry["memos"] = memo_counts.get(row["id"], 0)
        entry["groups"] = groups.get(row["id"], [])
        out.append(entry)
    return out


def rename_code(project_id, code_id, name):
    db.ex("UPDATE codebook SET name=? WHERE id=? AND project_id=?", (name, code_id, project_id))
    db.ex("UPDATE codes SET label=? WHERE code_id=? AND project_id=?",
          (name, code_id, project_id))


def merge_codes(project_id, keep_id, merge_ids):
    for other in merge_ids:
        if other == keep_id:
            continue
        db.ex("UPDATE codes SET code_id=? WHERE code_id=? AND project_id=?",
              (keep_id, other, project_id))
        db.ex("UPDATE links SET source_id=? WHERE source_type='code' AND source_id=?",
              (keep_id, other))
        db.ex("UPDATE links SET target_id=? WHERE target_type='code' AND target_id=?",
              (keep_id, other))
        db.ex("DELETE FROM codebook WHERE id=? AND project_id=?", (other, project_id))
    keep = db.q1("SELECT name FROM codebook WHERE id=?", (keep_id,))
    if keep:
        db.ex("UPDATE codes SET label=? WHERE code_id=?", (keep["name"], keep_id))


def delete_code(project_id, code_id):
    db.ex("DELETE FROM codes WHERE code_id=? AND project_id=?", (code_id, project_id))
    db.ex("DELETE FROM codebook WHERE id=? AND project_id=?", (code_id, project_id))
    db.ex("DELETE FROM code_group_members WHERE code_id=?", (code_id,))


# --- quotations -----------------------------------------------------------

def create_quotation(project_id, document_id, start, end, text=None, created_by="user",
                     comment=None, name=None):
    document = db.q1("SELECT * FROM transcripts WHERE id=? AND project_id=?",
                     (document_id, project_id))
    if document is None:
        raise ValueError("Document not found.")
    body = document["raw_text"]
    start = max(0, min(int(start), len(body)))
    end = max(start, min(int(end), len(body)))
    if end - start < 2:
        raise ValueError("Select some text before coding it.")
    snippet = text if text is not None else body[start:end]

    # Selecting the same span again means "code this passage", not "make a second
    # copy of it": reuse the existing quotation so the reader shows one highlight
    # and both coders stay attached to one object.
    existing = db.q1("SELECT * FROM quotations WHERE document_id=? AND start_offset=?"
                     " AND end_offset=?", (document_id, start, end))
    if existing is not None:
        if comment and not existing["comment"]:
            db.ex("UPDATE quotations SET comment=? WHERE id=?", (comment, existing["id"]))
        return db.q1("SELECT * FROM quotations WHERE id=?", (existing["id"],))

    quotation_id = db.new_id()
    db.insert("quotations", {
        "id": quotation_id, "project_id": project_id, "document_id": document_id,
        "start_offset": start, "end_offset": end, "text": snippet,
        "name": name, "comment": comment, "created_by": created_by,
        "created_at": db.now(),
    })
    return db.q1("SELECT * FROM quotations WHERE id=?", (quotation_id,))


def apply_code(project_id, quotation, code, created_by="user", confidence=1.0,
               emotion=None, intent=None, valence=0.0, literal=None):
    """Attach a codebook entry to a quotation (an 'application')."""
    existing = db.q1("SELECT id FROM codes WHERE quotation_id=? AND code_id=?",
                     (quotation["id"], code["id"]))
    if existing:
        return db.q1("SELECT * FROM codes WHERE id=?", (existing["id"],))
    document = db.q1("SELECT * FROM transcripts WHERE id=?", (quotation["document_id"],))
    application_id = db.new_id()
    db.insert("codes", {
        "id": application_id,
        "project_id": project_id,
        "transcript_id": quotation["document_id"],
        "meaning_unit_id": quotation["id"],
        "quotation_id": quotation["id"],
        "code_id": code["id"],
        "theme_id": None,
        "label": code["name"],
        "literal_meaning": literal or quotation["text"][:180],
        "emotion": emotion,
        "intent": intent,
        "valence": valence,
        "confidence": confidence,
        "alternative_interpretations": json.dumps([]),
        "is_negative_case": 0,
        "quote_text": quotation["text"],
        "participant_label": document["participant_label"] if document else "?",
        "terms": json.dumps({"phrase": code["name"]}),
        "created_by": created_by,
    })
    return db.q1("SELECT * FROM codes WHERE id=?", (application_id,))


def quotations_for(project_id, document_id=None):
    if document_id:
        rows = db.q("SELECT * FROM quotations WHERE project_id=? AND document_id=?"
                    " ORDER BY start_offset", (project_id, document_id))
    else:
        rows = db.q("SELECT * FROM quotations WHERE project_id=? ORDER BY created_at DESC",
                    (project_id,))
    by_quotation = defaultdict(list)
    for row in db.q("SELECT c.*, b.color FROM codes c LEFT JOIN codebook b ON b.id = c.code_id"
                    " WHERE c.project_id=?", (project_id,)):
        if row["quotation_id"]:
            by_quotation[row["quotation_id"]].append({
                "application_id": row["id"], "code_id": row["code_id"],
                "label": row["label"], "color": row["color"] or "#2B4570",
                "created_by": row["created_by"], "confidence": row["confidence"],
                "emotion": row["emotion"], "theme_id": row["theme_id"],
            })
    memo_counts = Counter()
    for row in db.q("SELECT target_id FROM memo_links WHERE target_type='quotation'"):
        memo_counts[row["target_id"]] += 1

    out = []
    for row in rows:
        entry = dict(row)
        entry["codes"] = by_quotation.get(row["id"], [])
        entry["memos"] = memo_counts.get(row["id"], 0)
        out.append(entry)
    return out


# --- memos, links, networks ----------------------------------------------

def memos(project_id):
    rows = db.q("SELECT * FROM memos WHERE project_id=? ORDER BY updated_at DESC",
                (project_id,))
    links = defaultdict(list)
    for row in db.q("SELECT * FROM memo_links"):
        links[row["memo_id"]].append({"type": row["target_type"], "id": row["target_id"]})
    out = []
    for row in rows:
        entry = dict(row)
        entry["links"] = links.get(row["id"], [])
        out.append(entry)
    return out


def link_targets(project_id):
    """Everything a network node or memo can point at."""
    codes = [{"type": "code", "id": r["id"], "label": r["name"], "color": r["color"]}
             for r in db.q("SELECT id, name, color FROM codebook WHERE project_id=?",
                           (project_id,))]
    themes = [{"type": "theme", "id": r["id"], "label": r["name"], "color": "#2B4570"}
              for r in db.q("SELECT id, name FROM themes WHERE project_id=?", (project_id,))]
    documents = [{"type": "document", "id": r["id"], "label": r["participant_label"],
                  "color": "#4F5D66"}
                 for r in db.q("SELECT id, participant_label FROM transcripts"
                               " WHERE project_id=?", (project_id,))]
    quotations = [{"type": "quotation", "id": r["id"], "label": r["text"][:60],
                   "color": "#8A6D3B"}
                  for r in db.q("SELECT id, text FROM quotations WHERE project_id=?"
                                " ORDER BY created_at DESC LIMIT 120", (project_id,))]
    memo_rows = [{"type": "memo", "id": r["id"], "label": r["title"], "color": "#5B4B8A"}
                 for r in db.q("SELECT id, title FROM memos WHERE project_id=?", (project_id,))]
    return codes + themes + documents + quotations + memo_rows


# --- queries --------------------------------------------------------------

def co_occurrence(project_id, min_count=1):
    """Codes that share a quotation, and codes that share a document."""
    by_quotation = defaultdict(set)
    by_document = defaultdict(set)
    names = {}
    colors = {}
    for row in db.q("SELECT c.code_id, c.quotation_id, c.transcript_id, c.label, b.color"
                    " FROM codes c LEFT JOIN codebook b ON b.id = c.code_id"
                    " WHERE c.project_id=? AND c.code_id IS NOT NULL", (project_id,)):
        names[row["code_id"]] = row["label"]
        colors[row["code_id"]] = row["color"] or "#2B4570"
        if row["quotation_id"]:
            by_quotation[row["quotation_id"]].add(row["code_id"])
        by_document[row["transcript_id"]].add(row["code_id"])

    pairs = Counter()
    for codes in by_quotation.values():
        ordered = sorted(codes)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                pairs[(ordered[i], ordered[j])] += 1
    doc_pairs = Counter()
    for codes in by_document.values():
        ordered = sorted(codes)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                doc_pairs[(ordered[i], ordered[j])] += 1

    totals = Counter()
    for row in db.q("SELECT code_id, COUNT(*) AS n FROM codes WHERE project_id=?"
                    " AND code_id IS NOT NULL GROUP BY code_id", (project_id,)):
        totals[row["code_id"]] = row["n"]

    edges = []
    for (a, b), count in (pairs + doc_pairs).items():
        direct = pairs.get((a, b), 0)
        shared_docs = doc_pairs.get((a, b), 0)
        if direct < min_count and shared_docs < 2:
            continue
        union = totals[a] + totals[b] - direct
        edges.append({
            "source": a, "target": b,
            "source_name": names.get(a, "?"), "target_name": names.get(b, "?"),
            "quotation_overlap": direct,
            "document_overlap": shared_docs,
            "c_coefficient": round(direct / union, 3) if union else 0.0,
        })
    edges.sort(key=lambda e: (-e["quotation_overlap"], -e["document_overlap"]))
    nodes = [{"id": cid, "label": names.get(cid, "?"), "color": colors.get(cid, "#2B4570"),
              "count": totals.get(cid, 0)} for cid in names]
    nodes.sort(key=lambda n: -n["count"])
    return {"nodes": nodes, "edges": edges[:200]}


def code_document_table(project_id):
    documents = db.q("SELECT id, participant_label FROM transcripts WHERE project_id=?"
                     " ORDER BY created_at", (project_id,))
    codes = db.q("SELECT id, name, color FROM codebook WHERE project_id=? ORDER BY order_idx",
                 (project_id,))
    counts = Counter()
    for row in db.q("SELECT code_id, transcript_id FROM codes WHERE project_id=?"
                    " AND code_id IS NOT NULL", (project_id,)):
        counts[(row["code_id"], row["transcript_id"])] += 1
    rows = []
    for code in codes:
        cells = [counts.get((code["id"], doc["id"]), 0) for doc in documents]
        rows.append({"code_id": code["id"], "code": code["name"], "color": code["color"],
                     "cells": cells, "total": sum(cells),
                     "documents": sum(1 for cell in cells if cell)})
    rows.sort(key=lambda r: -r["total"])
    return {
        "columns": [doc["participant_label"] for doc in documents],
        "document_ids": [doc["id"] for doc in documents],
        "rows": rows,
    }


def query(project_id, operator, code_ids, scope="quotation"):
    """Boolean retrieval over coded quotations.

    operator: all (AND), any (OR), none (NOT), only (exclusively these codes).
    """
    wanted = set(code_ids or [])
    if not wanted:
        return []
    by_quotation = defaultdict(set)
    for row in db.q("SELECT quotation_id, code_id FROM codes WHERE project_id=?"
                    " AND quotation_id IS NOT NULL AND code_id IS NOT NULL", (project_id,)):
        by_quotation[row["quotation_id"]].add(row["code_id"])

    if scope == "document":
        by_document = defaultdict(set)
        doc_of = {}
        for row in db.q("SELECT id, document_id FROM quotations WHERE project_id=?",
                        (project_id,)):
            doc_of[row["id"]] = row["document_id"]
        for quotation_id, codes in by_quotation.items():
            by_document[doc_of.get(quotation_id)] |= codes
        keep = [qid for qid, codes in by_quotation.items()
                if _matches(by_document[doc_of.get(qid)], wanted, operator)]
    else:
        keep = [qid for qid, codes in by_quotation.items()
                if _matches(codes, wanted, operator)]

    if not keep:
        return []
    quotations = {q["id"]: q for q in quotations_for(project_id)}
    results = [quotations[qid] for qid in keep if qid in quotations]
    results.sort(key=lambda q: (q["document_id"], q["start_offset"]))
    return results


def _matches(codes, wanted, operator):
    if operator == "all":
        return wanted <= codes
    if operator == "any":
        return bool(wanted & codes)
    if operator == "none":
        return not (wanted & codes)
    if operator == "only":
        return codes == wanted
    return bool(wanted & codes)


# --- agreement ------------------------------------------------------------

def agreement(project_id):
    """Compare the machine's coding with the researcher's on the same quotations.

    Reported as percent agreement, Cohen's kappa and Krippendorff's alpha over
    the quotations both have touched. Where a researcher has not coded anything
    yet there is nothing to compare, and that is said plainly rather than
    reported as perfect agreement.
    """
    auto = defaultdict(set)
    human = defaultdict(set)
    for row in db.q("SELECT quotation_id, code_id, created_by FROM codes"
                    " WHERE project_id=? AND quotation_id IS NOT NULL"
                    " AND code_id IS NOT NULL", (project_id,)):
        target = human if row["created_by"] == "user" else auto
        target[row["quotation_id"]].add(row["code_id"])

    shared = sorted(set(auto) & set(human))
    if not shared:
        return {
            "comparable_quotations": 0,
            "auto_quotations": len(auto),
            "human_quotations": len(human),
            "note": ("No quotation has been coded both automatically and by hand yet. "
                     "Code a few of the machine's quotations yourself and this becomes "
                     "a real reliability check."),
        }

    exact = 0
    partial = 0
    pairs = []
    for quotation_id in shared:
        a, b = auto[quotation_id], human[quotation_id]
        if a == b:
            exact += 1
        if a & b:
            partial += 1
        pairs.append((sorted(a)[0], sorted(b)[0]))

    labels = sorted({value for pair in pairs for value in pair})
    kappa = _cohen_kappa(pairs, labels)
    alpha = _krippendorff_alpha(pairs)
    names = {row["id"]: row["name"] for row in
             db.q("SELECT id, name FROM codebook WHERE project_id=?", (project_id,))}
    disagreements = [{
        "quotation_id": qid,
        "auto": sorted(names.get(c, c) for c in auto[qid]),
        "human": sorted(names.get(c, c) for c in human[qid]),
    } for qid in shared if auto[qid] != human[qid]][:25]

    return {
        "comparable_quotations": len(shared),
        "auto_quotations": len(auto),
        "human_quotations": len(human),
        "exact_agreement": round(exact / len(shared), 3),
        "partial_agreement": round(partial / len(shared), 3),
        "cohens_kappa": kappa,
        "krippendorff_alpha": alpha,
        "disagreements": disagreements,
        "note": _agreement_note(alpha, len(shared)),
    }


def _agreement_note(alpha, n):
    if alpha is None:
        return "Too little overlap to compute a coefficient."
    if n < 20:
        caveat = (" Based on only " + str(n) + " shared quotations, so read the coefficient "
                  "as indicative rather than conclusive.")
    else:
        caveat = ""
    if alpha >= 0.8:
        return "Alpha at or above 0.80 — the machine's coding is reproducing yours." + caveat
    if alpha >= 0.667:
        return ("Alpha between 0.67 and 0.80 — usable for drawing tentative conclusions, "
                "not for final claims." + caveat)
    return ("Alpha below 0.67 — the machine and you are coding differently. Look at the "
            "disagreements before trusting any automatic theme." + caveat)


def _cohen_kappa(pairs, labels):
    if not pairs or len(labels) < 2:
        return None
    n = len(pairs)
    observed = sum(1 for a, b in pairs if a == b) / n
    first = Counter(a for a, _ in pairs)
    second = Counter(b for _, b in pairs)
    expected = sum((first[label] / n) * (second[label] / n) for label in labels)
    if expected >= 1.0:
        return None
    return round((observed - expected) / (1 - expected), 3)


def _krippendorff_alpha(pairs):
    """Nominal alpha for two coders over paired observations."""
    if len(pairs) < 2:
        return None
    coincidence = Counter()
    for a, b in pairs:
        coincidence[(a, b)] += 1
        coincidence[(b, a)] += 1
    values = Counter()
    for (a, _), count in coincidence.items():
        values[a] += count
    total = sum(values.values())
    if total < 2:
        return None
    observed_disagreement = sum(count for (a, b), count in coincidence.items() if a != b)
    expected_disagreement = 0.0
    for a, na in values.items():
        for b, nb in values.items():
            if a != b:
                expected_disagreement += na * nb
    expected_disagreement /= (total - 1)
    if expected_disagreement == 0:
        return 1.0
    return round(1 - (observed_disagreement / expected_disagreement), 3)


# --- word frequency and search coding -------------------------------------

def word_frequency(project_id, limit=120):
    from analysis import textproc as tp
    documents = db.q("SELECT id, participant_label, raw_text FROM transcripts"
                     " WHERE project_id=?", (project_id,))
    per_doc = []
    counts = Counter()
    doc_freq = Counter()
    for doc in documents:
        tokens = tp.content_tokens(doc["raw_text"])
        counts.update(tokens)
        doc_freq.update(set(tp.stems(doc["raw_text"])))
        per_doc.append({"document": doc["participant_label"], "words": len(tokens)})
    idf = tp.idf_table([tp.stems(doc["raw_text"]) for doc in documents])
    words = [{
        "term": term,
        "count": count,
        "documents": doc_freq.get(tp.stem(term), 0),
        "weight": round(count * idf.get(tp.stem(term), 1.0), 2),
    } for term, count in counts.most_common(limit)]
    return {"words": words, "documents": per_doc, "total_words": sum(counts.values())}


def code_by_search(project_id, term, code_name, whole_word=True, created_by="search"):
    """Auto-code every occurrence of a term — the classic CAQDAS text search."""
    import re
    term = (term or "").strip()
    if len(term) < 2:
        raise ValueError("Search for at least two characters.")
    code = ensure_code(project_id, code_name or term, created_by="user")
    pattern = re.compile((r"\b" if whole_word else "") + re.escape(term)
                         + (r"\b" if whole_word else ""), re.IGNORECASE)
    made = 0
    for document in db.q("SELECT * FROM transcripts WHERE project_id=?", (project_id,)):
        body = document["raw_text"]
        for match in pattern.finditer(body):
            start, end = _expand_to_sentence(body, match.start(), match.end())
            existing = db.q1("SELECT id FROM quotations WHERE document_id=? AND start_offset=?"
                             " AND end_offset=?", (document["id"], start, end))
            if existing:
                quotation = db.q1("SELECT * FROM quotations WHERE id=?", (existing["id"],))
            else:
                quotation = create_quotation(project_id, document["id"], start, end,
                                             created_by=created_by)
            apply_code(project_id, quotation, code, created_by=created_by, confidence=1.0)
            made += 1
    return {"code": dict(code), "applications": made}


def _expand_to_sentence(text, start, end):
    left = max(text.rfind(".", 0, start), text.rfind("\n", 0, start),
               text.rfind("?", 0, start), text.rfind("!", 0, start))
    right_candidates = [pos for pos in (text.find(".", end), text.find("\n", end),
                                        text.find("?", end), text.find("!", end))
                        if pos != -1]
    left = 0 if left == -1 else left + 1
    right = min(right_candidates) + 1 if right_candidates else len(text)
    return left + (len(text[left:]) - len(text[left:].lstrip())), right


def project_overview(project_id):
    """Counts used by the workbench header and the project card."""
    def count(sql, args=(project_id,)):
        return db.q1(sql, args)["n"]
    return {
        "documents": count("SELECT COUNT(*) AS n FROM transcripts WHERE project_id=?"),
        "quotations": count("SELECT COUNT(*) AS n FROM quotations WHERE project_id=?"),
        "codes": count("SELECT COUNT(*) AS n FROM codebook WHERE project_id=?"),
        "applications": count("SELECT COUNT(*) AS n FROM codes WHERE project_id=?"),
        "hand_coded": count("SELECT COUNT(*) AS n FROM codes WHERE project_id=?"
                            " AND created_by='user'"),
        "themes": count("SELECT COUNT(*) AS n FROM themes WHERE project_id=?"),
        "memos": count("SELECT COUNT(*) AS n FROM memos WHERE project_id=?"),
        "links": count("SELECT COUNT(*) AS n FROM links WHERE project_id=?"),
    }
