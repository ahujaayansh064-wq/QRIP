"""Analysis orchestrator.

Segments transcripts, codes every meaning unit, clusters codes into themes,
looks for contradictions, runs a second pass for stability, then executes all
six methodology readings over the same coded corpus.
"""
import json
import threading
import traceback
from collections import Counter, defaultdict

import caqdas
import db
from . import clustering as cl
from . import coding
from . import contradictions as contra
from . import lexicons as lx
from . import llm
from . import textproc as tp
from .methodologies import content, framework, grounded_theory, ipa, narrative, thematic

METHODOLOGIES = {
    "thematic": thematic,
    "grounded_theory": grounded_theory,
    "ipa": ipa,
    "framework": framework,
    "narrative": narrative,
    "content": content,
}

METHODOLOGY_LABELS = {
    "thematic": "Thematic analysis",
    "grounded_theory": "Grounded theory",
    "ipa": "Interpretative phenomenological analysis",
    "framework": "Framework analysis",
    "narrative": "Narrative analysis",
    "content": "Content analysis",
}

_running = set()
_lock = threading.Lock()


def is_running(project_id: str) -> bool:
    with _lock:
        return project_id in _running


def start(project_id: str, user_id: str) -> bool:
    with _lock:
        if project_id in _running:
            return False
        _running.add(project_id)
    db.ex("UPDATE projects SET analysis_in_progress=1, analysis_stage=?, analysis_progress=0,"
          " last_analysis_error=NULL WHERE id=?", ("queued", project_id))
    thread = threading.Thread(target=_run_guarded, args=(project_id, user_id), daemon=True)
    thread.start()
    return True


def _run_guarded(project_id, user_id):
    try:
        run(project_id, user_id)
    except Exception as exc:  # analysis must never take the server down
        db.ex("UPDATE projects SET analysis_in_progress=0, analysis_stage=?,"
              " last_analysis_error=? WHERE id=?",
              ("failed", str(exc)[:500], project_id))
        db.audit(project_id, user_id, "analysis.failed", "project", project_id,
                 {"error": str(exc)[:500], "trace": traceback.format_exc()[-1200:]})
    finally:
        with _lock:
            _running.discard(project_id)


def _stage(project_id, name, progress):
    db.ex("UPDATE projects SET analysis_stage=?, analysis_progress=? WHERE id=?",
          (name, round(progress, 3), project_id))


def controls_of(project) -> dict:
    return {
        "similarity_threshold": project["similarity_threshold"],
        "confidence_threshold": project["confidence_threshold"],
        "min_supporting_quotations": project["min_supporting_quotations"],
        "participant_frequency_threshold": project["participant_frequency_threshold"],
        "coding_granularity": project["coding_granularity"],
        "contradiction_sensitivity": project["contradiction_sensitivity"],
    }


def _consolidate_labels(codes, concepts, idf):
    """Give the codebook names that recur.

    Per-segment open coding produces almost as many labels as segments, which is
    faithful to the method but useless as a codebook. Each code's topic is
    resolved to its concept, and every code about that concept is named after the
    same representative phrase — so groundedness means something and the code
    manager is workable. The segment-specific reading is kept as the open label.
    """
    words_by_concept = defaultdict(Counter)
    phrases_by_concept = defaultdict(Counter)
    for code in codes:
        head = tp.stem(code["phrase"].split()[-1])
        concept = concepts.get(head, head)
        code["concept"] = concept
        phrases_by_concept[concept][code["phrase"]] += 1
        for word in code["phrase"].split():
            if word in lx.LOW_CONTENT or word in lx.VERBS:
                continue
            words_by_concept[concept][word] += 1

    representative = {}
    for concept, words in words_by_concept.items():
        # the word this concept keeps coming back to, not its rarest word
        head_word = max(words.items(),
                        key=lambda kv: (kv[1] ** 1.5) * (idf.get(tp.stem(kv[0]), 1.0) ** 0.35))[0]
        best, best_count = head_word, 1
        for phrase, count in phrases_by_concept[concept].items():
            if head_word in phrase.split() and len(phrase.split()) == 2 and count > best_count:
                best, best_count = phrase, count
        representative[concept] = best
    for code in codes:
        phrase = representative.get(code["concept"], code["phrase"])
        if code["emotion"] and code["emotion"] != "neutral":
            frame = coding.EMOTION_FRAMES[code["emotion"]]
        else:
            frame = coding.INTENT_FRAMES.get(code["intent"], "Description of {p}")
        name = frame.format(p=phrase)
        code["open_label"] = code["label"]
        code["label"] = name[0].upper() + name[1:]


def run(project_id, user_id):
    project = db.q1("SELECT * FROM projects WHERE id=?", (project_id,))
    if project is None:
        raise ValueError("project not found")
    transcripts = db.q("SELECT * FROM transcripts WHERE project_id=? ORDER BY created_at",
                       (project_id,))
    if not transcripts:
        raise ValueError("No transcripts uploaded.")

    controls = controls_of(project)
    engine = llm.engine_info()

    # 1. clear the previous *automatic* run --------------------------------
    # Hand coding survives a re-run. Only what the machine made is discarded:
    # the researcher's quotations, codes, memos, links and networks stay.
    _stage(project_id, "preparing", 0.03)
    db.ex("DELETE FROM codes WHERE project_id=? AND created_by!='user'", (project_id,))
    db.ex("DELETE FROM quotations WHERE project_id=? AND created_by='auto'"
          " AND id NOT IN (SELECT quotation_id FROM codes WHERE quotation_id IS NOT NULL)",
          (project_id,))
    db.ex("DELETE FROM codebook WHERE project_id=? AND created_by='auto'"
          " AND id NOT IN (SELECT code_id FROM codes WHERE code_id IS NOT NULL)",
          (project_id,))
    for table in ("themes", "contradictions", "model_comparisons",
                  "meaning_units", "methodology_outputs"):
        db.ex("DELETE FROM " + table + " WHERE project_id=?", (project_id,))
    db.ex("UPDATE codes SET theme_id=NULL WHERE project_id=?", (project_id,))
    # a group must not keep pointing at a code the re-run has just retired
    db.ex("DELETE FROM code_group_members WHERE code_id NOT IN (SELECT id FROM codebook)")
    db.ex("DELETE FROM memo_links WHERE target_type='code'"
          " AND target_id NOT IN (SELECT id FROM codebook)")

    # 2. segmentation ------------------------------------------------------
    _stage(project_id, "segmenting transcripts", 0.10)
    units = []
    unit_rows = []
    for transcript in transcripts:
        db.ex("UPDATE transcripts SET status='processing', error_message=NULL WHERE id=?",
              (transcript["id"],))
        segs = tp.segment(transcript["raw_text"], controls["coding_granularity"])
        for idx, seg in enumerate(segs):
            uid = db.new_id()
            unit_rows.append({
                "id": uid,
                "project_id": project_id,
                "transcript_id": transcript["id"],
                "idx": idx,
                "turn_idx": seg["turn_idx"],
                "speaker": seg["speaker"],
                "is_participant": 1,
                "text": seg["text"],
                "question_context": seg["question_context"],
                "char_start": seg["char_start"],
                "char_end": seg["char_end"],
            })
            units.append({
                "id": uid,
                "transcript_id": transcript["id"],
                "participant_label": transcript["participant_label"],
                "idx": idx,
                "turn_idx": seg["turn_idx"],
                "text": seg["text"],
                "question_context": seg["question_context"],
                "char_start": seg["char_start"],
                "char_end": seg["char_end"],
            })
        db.ex("UPDATE transcripts SET status='processed' WHERE id=?", (transcript["id"],))
    db.insert_many("meaning_units", unit_rows)

    if not units:
        raise ValueError("No participant speech found in the uploaded transcripts.")

    # 3. open coding -------------------------------------------------------
    _stage(project_id, "open coding", 0.28)
    unit_stems = [tp.stems(u["text"]) for u in units]
    idf = tp.idf_table(unit_stems)
    related = tp.cooccurrence(unit_stems)
    concepts, concept_labels = tp.concept_space(unit_stems)
    codes = coding.code_units(units, idf, controls["coding_granularity"])
    codes = llm.enrich_codes(codes, project, user_id)
    if not codes:
        raise ValueError("No codable segments found.")
    for code in codes:
        code["id"] = db.new_id()
        code["source"] = "auto"
    _consolidate_labels(codes, concepts, idf)

    # Everything the machine coded becomes a real quotation and codebook entry,
    # so the researcher can open any of it and take it over by hand.
    _stage(project_id, "writing quotations and codebook", 0.36)
    unit_spans = {u["id"]: u for u in units}
    codebook_ids = {}
    quotation_rows = []
    # A quotation that survived the clear-down (because the researcher coded or
    # commented on it) is reused rather than duplicated: the same span must stay
    # one object, or hand and machine coding drift onto separate copies and the
    # agreement check has nothing to compare.
    existing_spans = {}
    for row in db.q("SELECT id, document_id, start_offset, end_offset FROM quotations"
                    " WHERE project_id=?", (project_id,)):
        existing_spans[(row["document_id"], row["start_offset"], row["end_offset"])] = row["id"]

    for code in codes:
        unit = unit_spans[code["meaning_unit_id"]]
        span_key = (code["transcript_id"], unit["char_start"], unit["char_end"])
        reused = existing_spans.get(span_key)
        quotation_id = reused or db.new_id()
        code["quotation_id"] = quotation_id
        if not reused:
            existing_spans[span_key] = quotation_id
            quotation_rows.append({
                "id": quotation_id, "project_id": project_id,
                "document_id": code["transcript_id"],
                "start_offset": unit["char_start"], "end_offset": unit["char_end"],
                "text": code["quote_text"], "name": None, "comment": None,
                "created_by": "auto", "created_at": db.now(),
            })
        key = code["label"].strip().lower()
        if key not in codebook_ids:
            entry = caqdas.ensure_code(project_id, code["label"], created_by="auto")
            codebook_ids[key] = entry["id"]
        code["code_id"] = codebook_ids[key]
    db.insert_many("quotations", quotation_rows)

    # Hand coding takes part in theme building: the researcher's judgements are
    # data too, not a separate track that the analysis ignores.
    manual = db.q("SELECT c.*, q.start_offset FROM codes c"
                  " JOIN quotations q ON q.id = c.quotation_id"
                  " WHERE c.project_id=? AND c.created_by='user'", (project_id,))
    for row in manual:
        text = row["quote_text"]
        ems = coding.emotion_scores(text)
        intent, _ = coding.detect_intent(text)
        phrase = coding.salient_phrase(text, idf, Counter())
        codes.append({
            "id": row["id"], "source": "user", "existing": True,
            "meaning_unit_id": row["meaning_unit_id"], "quotation_id": row["quotation_id"],
            "code_id": row["code_id"], "transcript_id": row["transcript_id"],
            "participant_label": row["participant_label"], "label": row["label"],
            "literal_meaning": row["literal_meaning"], "quote_text": text,
            "emotion": max(ems, key=ems.get) if ems else "neutral", "intent": intent,
            "valence": round(coding.valence(text), 3), "confidence": row["confidence"] or 1.0,
            "alternative_interpretations": [],
            "phrase": phrase, "stems": tp.stems(text) + [tp.stem(w) for w in phrase.split()],
            "turn_idx": 0, "idx": row["start_offset"], "question_context": None,
        })

    # 4. clustering into themes -------------------------------------------
    _stage(project_id, "clustering codes into themes", 0.48)
    vectors = cl.build_vectors(codes, idf, concepts, related)
    clusters = cl.cluster(vectors, threshold=controls["similarity_threshold"])
    participants = sorted({u["participant_label"] for u in units})
    theme_ctrls = dict(controls)
    theme_ctrls["idf"] = idf
    themes = cl.summarise(codes, vectors, clusters, theme_ctrls, len(participants))
    for theme in themes:
        theme["id"] = db.new_id()
        for i in theme["member_idx"]:
            codes[i]["theme_id"] = theme["id"]

    db.insert_many("themes", [{
        "id": t["id"], "project_id": project_id, "name": t["name"],
        "description": t["description"], "status": t["status"], "confidence": t["confidence"],
        "coverage": t["coverage"], "participant_count": t["participant_count"],
        "alternative_interpretation": t["alternative_interpretation"],
        "merged_from": json.dumps([]), "order_idx": t["order_idx"],
    } for t in themes])

    db.insert_many("codes", [{
        "id": c["id"], "project_id": project_id, "transcript_id": c["transcript_id"],
        "meaning_unit_id": c["meaning_unit_id"], "quotation_id": c.get("quotation_id"),
        "code_id": c.get("code_id"), "theme_id": c.get("theme_id"),
        "label": c["label"], "literal_meaning": c["literal_meaning"], "emotion": c["emotion"],
        "intent": c["intent"], "valence": c["valence"], "confidence": c["confidence"],
        "alternative_interpretations": json.dumps(c["alternative_interpretations"]),
        "is_negative_case": c.get("is_negative_case", 0), "quote_text": c["quote_text"],
        "participant_label": c["participant_label"],
        "terms": json.dumps({"phrase": c["phrase"], "stems": c["stems"][:40],
                             "open_label": c.get("open_label")}),
        "created_by": "auto",
    } for c in codes if not c.get("existing")])

    # hand-coded applications keep their row; they only gain a theme
    for c in codes:
        if c.get("existing"):
            db.ex("UPDATE codes SET theme_id=?, is_negative_case=? WHERE id=?",
                  (c.get("theme_id"), c.get("is_negative_case", 0), c["id"]))

    # 5. contradictions ----------------------------------------------------
    _stage(project_id, "detecting contradictions", 0.62)
    found = contra.detect(codes, vectors, themes, controls["contradiction_sensitivity"])
    db.insert_many("contradictions", [{
        "id": db.new_id(), "project_id": project_id, "theme_id": c["theme_id"],
        "description": c["description"], "severity": c["severity"],
        "code_a_id": c["code_a_id"], "code_b_id": c["code_b_id"],
    } for c in found])

    # 6. second-pass agreement --------------------------------------------
    _stage(project_id, "second-pass model comparison", 0.72)
    comparisons = contra.compare_second_pass(
        codes, vectors, themes, controls["similarity_threshold"],
        engine["primary_model"], engine["secondary_model"])
    db.insert_many("model_comparisons", [{
        "id": db.new_id(), "project_id": project_id, "theme_id": c["theme_id"],
        "primary_model": c["primary_model"], "secondary_model": c["secondary_model"],
        "agreement": 1 if c["agreement"] else 0,
        "disagreement_notes": c["disagreement_notes"],
    } for c in comparisons if c["theme_id"]])

    # 7. methodology readings ---------------------------------------------
    ctx = {
        "project": dict(project),
        "controls": controls,
        "codes": codes,
        "themes": themes,
        "vectors": vectors,
        "idf": idf,
        "units": units,
        "unit_count": len(units),
        "transcripts": [dict(t) for t in transcripts],
        "participants": participants,
        "engine": engine,
    }
    total = len(METHODOLOGIES)
    for i, (key, module) in enumerate(METHODOLOGIES.items()):
        _stage(project_id, "running " + METHODOLOGY_LABELS[key], 0.75 + 0.22 * (i / total))
        payload = module.run(ctx)
        payload["generated_at"] = db.now()
        payload["engine"] = engine["primary_model"]
        db.ex("INSERT OR REPLACE INTO methodology_outputs"
              " (project_id, methodology, payload, created_at) VALUES (?,?,?,?)",
              (project_id, key, json.dumps(payload), db.now()))

    # 8. usage accounting --------------------------------------------------
    chars = sum(t["char_count"] for t in transcripts)
    in_tokens = max(1, chars // 4)
    out_tokens = len(codes) * 60 + len(themes) * 120
    db.log_usage(user_id, project_id, "analysis.full_run", engine["primary_model"],
                 in_tokens, out_tokens, engine["cost_per_1k_in"] * in_tokens / 1000.0
                 + engine["cost_per_1k_out"] * out_tokens / 1000.0)

    db.ex("UPDATE projects SET analysis_in_progress=0, analysis_stage='complete',"
          " analysis_progress=1.0, last_analysis_at=?, last_analysis_error=NULL WHERE id=?",
          (db.now(), project_id))
    db.audit(project_id, user_id, "analysis.completed", "project", project_id, {
        "transcripts": len(transcripts), "meaning_units": len(units), "codes": len(codes),
        "themes": len(themes), "contradictions": len(found),
        "engine": engine["primary_model"],
        "controls": controls,
    })
    return {"codes": len(codes), "themes": len(themes)}


# --- theme editing helpers used by the API -------------------------------

def recompute_theme_stats(project_id, theme_id):
    codes = db.q("SELECT * FROM codes WHERE theme_id=?", (theme_id,))
    if not codes:
        db.ex("UPDATE themes SET confidence=0, coverage=0, participant_count=0 WHERE id=?",
              (theme_id,))
        return
    total = db.q1("SELECT COUNT(*) AS n FROM codes WHERE project_id=?", (project_id,))["n"] or 1
    participants = {c["participant_label"] for c in codes}
    confidence = sum(c["confidence"] for c in codes) / len(codes)
    db.ex("UPDATE themes SET confidence=?, coverage=?, participant_count=? WHERE id=?",
          (round(confidence, 3), round(len(codes) / total, 4), len(participants), theme_id))
