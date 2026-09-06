"""HTTP API surface for QRIP.

Routes mirror the platform's published API: auth, projects, controls,
transcripts, analysis, dashboard, themes, contradictions, model comparisons,
audit log, exports and usage.
"""
import json
import re
import zipfile
import io

import auth
import caqdas
import claude as claude_client
import db
import exports
from analysis import pipeline
from analysis import clustering as cl
from analysis import textproc as tp
from reviews import codebook as review_codebook
from reviews import jobs as review_jobs
from reviews import report_pdf as review_pdf
from reviews import sources as review_sources
from reviews import workbook as review_workbook


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class FileResponse:
    def __init__(self, data, filename, content_type):
        self.data = data
        self.filename = filename
        self.content_type = content_type


# --- serialisers ---------------------------------------------------------

def user_out(user):
    return {"id": user["id"], "email": user["email"], "name": user["name"],
            "role": user["role"]}


def project_out(row):
    return {
        "id": row["id"], "name": row["name"],
        "research_question": row["research_question"],
        "methodology": row["methodology"], "description": row["description"],
        "similarity_threshold": row["similarity_threshold"],
        "confidence_threshold": row["confidence_threshold"],
        "min_supporting_quotations": row["min_supporting_quotations"],
        "participant_frequency_threshold": row["participant_frequency_threshold"],
        "coding_granularity": row["coding_granularity"],
        "contradiction_sensitivity": row["contradiction_sensitivity"],
        "analysis_in_progress": bool(row["analysis_in_progress"]),
        "analysis_stage": row["analysis_stage"],
        "analysis_progress": row["analysis_progress"],
        "last_analysis_error": row["last_analysis_error"],
        "last_analysis_at": row["last_analysis_at"],
        "created_at": row["created_at"],
    }


def transcript_out(row):
    return {"id": row["id"], "filename": row["filename"],
            "participant_label": row["participant_label"], "status": row["status"],
            "error_message": row["error_message"], "created_at": row["created_at"],
            "char_count": row["char_count"]}


def code_out(row):
    return {
        "id": row["id"], "label": row["label"], "literal_meaning": row["literal_meaning"],
        "emotion": row["emotion"], "intent": row["intent"], "valence": row["valence"],
        "confidence": row["confidence"],
        "alternative_interpretations": json.loads(row["alternative_interpretations"] or "[]"),
        "is_negative_case": bool(row["is_negative_case"]), "quote_text": row["quote_text"],
        "participant_label": row["participant_label"], "transcript_id": row["transcript_id"],
        "meaning_unit_id": row["meaning_unit_id"], "theme_id": row["theme_id"],
    }


def theme_out(row, codes):
    return {
        "id": row["id"], "name": row["name"], "description": row["description"],
        "status": row["status"], "confidence": row["confidence"], "coverage": row["coverage"],
        "participant_count": row["participant_count"],
        "alternative_interpretation": row["alternative_interpretation"],
        "merged_from": json.loads(row["merged_from"] or "[]"),
        "quote_count": len(codes),
        "contradiction_count": db.q1(
            "SELECT COUNT(*) AS n FROM contradictions WHERE theme_id=?", (row["id"],))["n"],
        "codes": [code_out(c) for c in codes],
    }


# --- helpers -------------------------------------------------------------

def require_user(ctx):
    if ctx.get("user") is None:
        raise ApiError(401, "Not authenticated.")
    return ctx["user"]


def get_project(ctx, project_id):
    user = require_user(ctx)
    row = db.q1("SELECT * FROM projects WHERE id=?", (project_id,))
    if row is None:
        raise ApiError(404, "Project not found.")
    if row["user_id"] != user["id"] and user["role"] != "owner":
        raise ApiError(403, "This project belongs to another researcher.")
    return row


def body_of(ctx):
    return ctx.get("json") or {}


def clamp(value, low, high, default):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


# --- auth ----------------------------------------------------------------

def post_register(ctx):
    data = body_of(ctx)
    try:
        user = auth.register(data.get("email"), data.get("password"), data.get("name"))
    except ValueError as exc:
        raise ApiError(400, str(exc))
    return {"access_token": auth.make_token(user["id"]), "token_type": "bearer",
            "user": user_out(user)}


def post_login(ctx):
    data = body_of(ctx)
    try:
        user = auth.login(data.get("email"), data.get("password"))
    except ValueError as exc:
        raise ApiError(401, str(exc))
    return {"access_token": auth.make_token(user["id"]), "token_type": "bearer",
            "user": user_out(user)}


def get_me(ctx):
    return user_out(require_user(ctx))


# --- projects ------------------------------------------------------------

def list_projects(ctx):
    user = require_user(ctx)
    if user["role"] == "owner":
        rows = db.q("SELECT * FROM projects ORDER BY created_at DESC")
    else:
        rows = db.q("SELECT * FROM projects WHERE user_id=? ORDER BY created_at DESC",
                    (user["id"],))
    counts = {}
    for table, key in (("transcripts", "documents"), ("quotations", "quotations"),
                       ("codebook", "codes"), ("themes", "themes")):
        for row in db.q("SELECT project_id, COUNT(*) AS n FROM " + table
                        + " GROUP BY project_id"):
            counts.setdefault(row["project_id"], {})[key] = row["n"]
    out = []
    for row in rows:
        project = project_out(row)
        project["counts"] = counts.get(row["id"], {})
        out.append(project)
    return out


def create_project(ctx):
    user = require_user(ctx)
    data = body_of(ctx)
    name = (data.get("name") or "").strip()
    if not name:
        raise ApiError(400, "A project name is required.")
    row = {
        "id": db.new_id(), "user_id": user["id"], "name": name,
        "research_question": (data.get("research_question") or "").strip() or None,
        "methodology": (data.get("methodology") or "thematic").strip() or None,
        "description": (data.get("description") or "").strip() or None,
        "created_at": db.now(),
    }
    db.insert("projects", row)
    db.audit(row["id"], user["id"], "project.created", "project", row["id"],
             {"name": name, "methodology": row["methodology"]})
    return project_out(db.q1("SELECT * FROM projects WHERE id=?", (row["id"],)))


def get_project_route(ctx, project_id):
    return project_out(get_project(ctx, project_id))


def patch_project(ctx, project_id):
    project = get_project(ctx, project_id)
    data = body_of(ctx)
    fields = {}
    for key in ("name", "research_question", "methodology", "description"):
        if key in data:
            fields[key] = (data[key] or "").strip() or None
    if fields.get("name") is None and "name" in fields:
        raise ApiError(400, "A project name is required.")
    if fields:
        sets = ", ".join(k + "=?" for k in fields)
        db.ex("UPDATE projects SET " + sets + " WHERE id=?",
              tuple(fields.values()) + (project_id,))
        db.audit(project_id, ctx["user"]["id"], "project.updated", "project", project_id, fields)
    return project_out(db.q1("SELECT * FROM projects WHERE id=?", (project_id,)))


def delete_project(ctx, project_id):
    project = get_project(ctx, project_id)
    db.ex("DELETE FROM projects WHERE id=?", (project_id,))
    db.audit(None, ctx["user"]["id"], "project.deleted", "project", project_id,
             {"name": project["name"]})
    return {"deleted": True}


def patch_controls(ctx, project_id):
    project = get_project(ctx, project_id)
    data = body_of(ctx)
    granularity = data.get("coding_granularity") or project["coding_granularity"]
    if granularity not in ("clause", "sentence", "utterance"):
        raise ApiError(400, "coding_granularity must be clause, sentence or utterance.")
    fields = {
        "similarity_threshold": clamp(data.get("similarity_threshold"), 0.05, 0.95,
                                      project["similarity_threshold"]),
        "confidence_threshold": clamp(data.get("confidence_threshold"), 0.0, 1.0,
                                      project["confidence_threshold"]),
        "min_supporting_quotations": int(clamp(data.get("min_supporting_quotations"), 1, 50,
                                               project["min_supporting_quotations"])),
        "participant_frequency_threshold": int(clamp(
            data.get("participant_frequency_threshold"), 1, 50,
            project["participant_frequency_threshold"])),
        "coding_granularity": granularity,
        "contradiction_sensitivity": clamp(data.get("contradiction_sensitivity"), 0.0, 1.0,
                                           project["contradiction_sensitivity"]),
    }
    sets = ", ".join(k + "=?" for k in fields)
    db.ex("UPDATE projects SET " + sets + " WHERE id=?", tuple(fields.values()) + (project_id,))
    db.audit(project_id, ctx["user"]["id"], "controls.updated", "project", project_id, fields)
    return project_out(db.q1("SELECT * FROM projects WHERE id=?", (project_id,)))


# --- transcripts ---------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")


def _text_from_upload(filename: str, raw: bytes) -> str:
    lower = (filename or "").lower()
    if lower.endswith(".docx"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                xml = z.read("word/document.xml").decode("utf-8", "replace")
            xml = xml.replace("</w:p>", "\n").replace("<w:tab/>", "\t")
            return _TAG_RE.sub("", xml)
        except Exception:
            raise ApiError(400, "That .docx could not be read.")
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def list_transcripts(ctx, project_id):
    get_project(ctx, project_id)
    return [transcript_out(r) for r in db.q(
        "SELECT * FROM transcripts WHERE project_id=? ORDER BY created_at", (project_id,))]


def upload_transcript(ctx, project_id):
    project = get_project(ctx, project_id)
    form = ctx.get("form") or {}
    files = ctx.get("files") or {}
    if "file" not in files:
        raise ApiError(400, "No file was uploaded.")
    filename, raw = files["file"]
    text = tp.normalise(_text_from_upload(filename, raw))
    if len(text.split()) < 20:
        raise ApiError(400, "That file has too little text to analyse.")
    label = (form.get("participant_label") or "").strip()
    if not label:
        n = db.q1("SELECT COUNT(*) AS n FROM transcripts WHERE project_id=?",
                  (project_id,))["n"]
        label = "P" + str(n + 1)
    row = {
        "id": db.new_id(), "project_id": project_id, "filename": filename or "transcript.txt",
        "participant_label": label, "status": "uploaded", "error_message": None,
        "raw_text": text, "char_count": len(text), "created_at": db.now(),
    }
    db.insert("transcripts", row)
    db.audit(project_id, ctx["user"]["id"], "transcript.uploaded", "transcript", row["id"],
             {"filename": row["filename"], "participant_label": label,
              "char_count": row["char_count"]})
    return transcript_out(db.q1("SELECT * FROM transcripts WHERE id=?", (row["id"],)))


def get_transcript(ctx, project_id, transcript_id):
    get_project(ctx, project_id)
    row = db.q1("SELECT * FROM transcripts WHERE id=? AND project_id=?",
                (transcript_id, project_id))
    if row is None:
        raise ApiError(404, "Transcript not found.")
    codes = db.q("SELECT * FROM codes WHERE transcript_id=? ORDER BY rowid", (transcript_id,))
    out = transcript_out(row)
    out["raw_text"] = row["raw_text"]
    out["codes"] = [code_out(c) for c in codes]
    return out


def delete_transcript(ctx, project_id, transcript_id):
    get_project(ctx, project_id)
    row = db.q1("SELECT * FROM transcripts WHERE id=? AND project_id=?",
                (transcript_id, project_id))
    if row is None:
        raise ApiError(404, "Transcript not found.")
    db.ex("DELETE FROM codes WHERE transcript_id=?", (transcript_id,))
    db.ex("DELETE FROM meaning_units WHERE transcript_id=?", (transcript_id,))
    db.ex("DELETE FROM transcripts WHERE id=?", (transcript_id,))
    db.audit(project_id, ctx["user"]["id"], "transcript.deleted", "transcript", transcript_id,
             {"filename": row["filename"]})
    return {"deleted": True}


# --- analysis ------------------------------------------------------------

def run_analysis(ctx, project_id):
    project = get_project(ctx, project_id)
    if project["analysis_in_progress"] or pipeline.is_running(project_id):
        raise ApiError(409, "An analysis is already running for this project.")
    pending = db.q1("SELECT COUNT(*) AS n FROM transcripts WHERE project_id=?",
                    (project_id,))["n"]
    if not pending:
        raise ApiError(400, "Upload at least one transcript before running an analysis.")
    db.audit(project_id, ctx["user"]["id"], "analysis.started", "project", project_id,
             {"transcripts": pending})
    pipeline.start(project_id, ctx["user"]["id"])
    return {"status": "started", "transcripts": pending}


def analysis_status(ctx, project_id):
    project = get_project(ctx, project_id)
    return {
        "analysis_in_progress": bool(project["analysis_in_progress"]),
        "stage": project["analysis_stage"],
        "progress": project["analysis_progress"],
        "last_analysis_error": project["last_analysis_error"],
        "last_analysis_at": project["last_analysis_at"],
        "theme_count": db.q1("SELECT COUNT(*) AS n FROM themes WHERE project_id=?",
                             (project_id,))["n"],
        "code_count": db.q1("SELECT COUNT(*) AS n FROM codes WHERE project_id=?",
                            (project_id,))["n"],
    }


# --- dashboard, themes ---------------------------------------------------

def _themes_with_codes(project_id):
    themes = db.q("SELECT * FROM themes WHERE project_id=? ORDER BY order_idx", (project_id,))
    codes = db.q("SELECT * FROM codes WHERE project_id=? ORDER BY confidence DESC",
                 (project_id,))
    grouped = {}
    for code in codes:
        grouped.setdefault(code["theme_id"], []).append(code)
    return [theme_out(t, grouped.get(t["id"], [])) for t in themes]


def dashboard(ctx, project_id):
    get_project(ctx, project_id)
    themes = _themes_with_codes(project_id)
    codes = db.q("SELECT * FROM codes WHERE project_id=?", (project_id,))
    contradictions = db.q(
        "SELECT * FROM contradictions WHERE project_id=? ORDER BY severity DESC", (project_id,))
    interviews = db.q("SELECT * FROM transcripts WHERE project_id=?", (project_id,))
    units = db.q1("SELECT COUNT(*) AS n FROM meaning_units WHERE project_id=?",
                  (project_id,))["n"]
    avg_conf = (sum(c["confidence"] for c in codes) / len(codes)) if codes else 0.0

    nodes, edges = [], []
    for theme in themes:
        nodes.append({"id": theme["id"], "label": theme["name"], "kind": "theme",
                      "size": theme["quote_count"], "status": theme["status"],
                      "confidence": theme["confidence"]})
    participants = sorted({c["participant_label"] for c in codes})
    for participant in participants:
        nodes.append({"id": "p:" + participant, "label": participant, "kind": "participant",
                      "size": sum(1 for c in codes if c["participant_label"] == participant)})
    for theme in themes:
        counts = {}
        for code in theme["codes"]:
            counts[code["participant_label"]] = counts.get(code["participant_label"], 0) + 1
        for participant, n in counts.items():
            edges.append({"source": "p:" + participant, "target": theme["id"],
                          "weight": n, "kind": "contributes"})
    for c in contradictions:
        if c["theme_id"]:
            edges.append({"source": c["theme_id"], "target": c["theme_id"],
                          "weight": c["severity"], "kind": "contradiction"})

    emotions = {}
    for code in codes:
        emotions[code["emotion"]] = emotions.get(code["emotion"], 0) + 1

    return {
        "interview_count": len(interviews),
        "meaning_unit_count": units,
        "code_count": len(codes),
        "theme_count": len(themes),
        "quote_count": len(codes),
        "contradiction_count": len(contradictions),
        "average_confidence": round(avg_conf, 3),
        "participant_count": len(participants),
        "negative_case_count": sum(1 for c in codes if c["is_negative_case"]),
        "emotion_distribution": emotions,
        "themes": themes,
        "contradictions": [{"id": c["id"], "theme_id": c["theme_id"],
                            "description": c["description"], "severity": c["severity"]}
                           for c in contradictions],
        "graph_nodes": nodes,
        "graph_edges": edges,
        "methodologies": [r["methodology"] for r in db.q(
            "SELECT methodology FROM methodology_outputs WHERE project_id=?", (project_id,))],
    }


def list_themes(ctx, project_id):
    get_project(ctx, project_id)
    return _themes_with_codes(project_id)


def list_codes(ctx, project_id):
    get_project(ctx, project_id)
    return [code_out(c) for c in db.q(
        "SELECT * FROM codes WHERE project_id=? ORDER BY confidence DESC", (project_id,))]


def theme_merge_suggestions(ctx, project_id):
    project = get_project(ctx, project_id)
    themes = db.q("SELECT * FROM themes WHERE project_id=? ORDER BY order_idx", (project_id,))
    codes = db.q("SELECT * FROM codes WHERE project_id=?", (project_id,))
    if not themes or not codes:
        return []
    by_theme = {}
    for code in codes:
        by_theme.setdefault(code["theme_id"], []).append(code)
    docs = [tp.stems(c["quote_text"]) for c in codes]
    idf = tp.idf_table(docs)
    # same concept space the pipeline clusters in, so suggestions are comparable
    concepts, _ = tp.concept_space(docs)
    payload = []
    for theme in themes:
        members = by_theme.get(theme["id"], [])
        vecs = [tp.concept_vector(
            tp.stems(c["quote_text"]) + [tp.stem(w) for w in
                (json.loads(c["terms"] or "{}").get("phrase") or "").split()] * 2,
            concepts, idf)
            for c in members]
        payload.append({
            "id": theme["id"], "name": theme["name"],
            "participants": sorted({c["participant_label"] for c in members}),
            "centroid": tp.centroid(vecs) if vecs else {},
            "mean_valence": (sum(c["valence"] for c in members) / len(members)) if members else 0,
        })
    return cl.merge_suggestions(payload, project["similarity_threshold"])


def rename_theme(ctx, project_id, theme_id):
    get_project(ctx, project_id)
    name = (body_of(ctx).get("name") or "").strip()
    if not name:
        raise ApiError(400, "A theme name is required.")
    theme = db.q1("SELECT * FROM themes WHERE id=? AND project_id=?", (theme_id, project_id))
    if theme is None:
        raise ApiError(404, "Theme not found.")
    db.ex("UPDATE themes SET name=? WHERE id=?", (name, theme_id))
    db.audit(project_id, ctx["user"]["id"], "theme.renamed", "theme", theme_id,
             {"from": theme["name"], "to": name})
    return theme_out(db.q1("SELECT * FROM themes WHERE id=?", (theme_id,)),
                     db.q("SELECT * FROM codes WHERE theme_id=?", (theme_id,)))


def set_theme_status(ctx, project_id, theme_id):
    get_project(ctx, project_id)
    status = (body_of(ctx).get("status") or "").strip()
    if status not in ("confirmed", "candidate", "review", "rejected"):
        raise ApiError(400, "status must be confirmed, candidate, review or rejected.")
    theme = db.q1("SELECT * FROM themes WHERE id=? AND project_id=?", (theme_id, project_id))
    if theme is None:
        raise ApiError(404, "Theme not found.")
    db.ex("UPDATE themes SET status=? WHERE id=?", (status, theme_id))
    db.audit(project_id, ctx["user"]["id"], "theme.status_changed", "theme", theme_id,
             {"from": theme["status"], "to": status, "name": theme["name"]})
    return theme_out(db.q1("SELECT * FROM themes WHERE id=?", (theme_id,)),
                     db.q("SELECT * FROM codes WHERE theme_id=?", (theme_id,)))


def merge_themes(ctx, project_id):
    get_project(ctx, project_id)
    data = body_of(ctx)
    ids = data.get("theme_ids") or []
    if len(ids) < 2:
        raise ApiError(400, "Select at least two themes to merge.")
    themes = [db.q1("SELECT * FROM themes WHERE id=? AND project_id=?", (tid, project_id))
              for tid in ids]
    if any(t is None for t in themes):
        raise ApiError(404, "One of those themes no longer exists.")
    target = themes[0]
    new_name = (data.get("new_name") or "").strip() or target["name"]
    merged_from = json.loads(target["merged_from"] or "[]")
    for theme in themes[1:]:
        db.ex("UPDATE codes SET theme_id=? WHERE theme_id=?", (target["id"], theme["id"]))
        merged_from.append({"id": theme["id"], "name": theme["name"]})
        db.ex("UPDATE contradictions SET theme_id=? WHERE theme_id=?",
              (target["id"], theme["id"]))
        db.ex("DELETE FROM themes WHERE id=?", (theme["id"],))
    db.ex("UPDATE themes SET name=?, merged_from=?, status='review' WHERE id=?",
          (new_name, json.dumps(merged_from), target["id"]))
    pipeline.recompute_theme_stats(project_id, target["id"])
    db.audit(project_id, ctx["user"]["id"], "theme.merged", "theme", target["id"],
             {"merged": [t["name"] for t in themes[1:]], "into": new_name})
    return theme_out(db.q1("SELECT * FROM themes WHERE id=?", (target["id"],)),
                     db.q("SELECT * FROM codes WHERE theme_id=?", (target["id"],)))


def split_theme(ctx, project_id):
    get_project(ctx, project_id)
    data = body_of(ctx)
    code_ids = data.get("code_ids_for_new_theme") or []
    name = (data.get("new_theme_name") or "").strip()
    if not code_ids or not name:
        raise ApiError(400, "Provide a new theme name and the codes to move.")
    codes = [db.q1("SELECT * FROM codes WHERE id=? AND project_id=?", (cid, project_id))
             for cid in code_ids]
    codes = [c for c in codes if c is not None]
    if not codes:
        raise ApiError(404, "None of those codes were found.")
    source_theme_id = codes[0]["theme_id"]
    order = db.q1("SELECT COALESCE(MAX(order_idx), 0) + 1 AS n FROM themes WHERE project_id=?",
                  (project_id,))["n"]
    theme_id = db.new_id()
    db.insert("themes", {
        "id": theme_id, "project_id": project_id, "name": name,
        "description": "Split out by hand from an existing theme by the researcher.",
        "status": "review",
        "confidence": round(sum(c["confidence"] for c in codes) / len(codes), 3),
        "coverage": 0.0,
        "participant_count": len({c["participant_label"] for c in codes}),
        "alternative_interpretation": None, "merged_from": json.dumps([]),
        "order_idx": order,
    })
    for code in codes:
        db.ex("UPDATE codes SET theme_id=? WHERE id=?", (theme_id, code["id"]))
    pipeline.recompute_theme_stats(project_id, theme_id)
    if source_theme_id:
        pipeline.recompute_theme_stats(project_id, source_theme_id)
    db.audit(project_id, ctx["user"]["id"], "theme.split", "theme", theme_id,
             {"new_theme": name, "codes_moved": len(codes), "from_theme": source_theme_id})
    return theme_out(db.q1("SELECT * FROM themes WHERE id=?", (theme_id,)),
                     db.q("SELECT * FROM codes WHERE theme_id=?", (theme_id,)))


def list_contradictions(ctx, project_id):
    get_project(ctx, project_id)
    rows = db.q("SELECT * FROM contradictions WHERE project_id=? ORDER BY severity DESC",
                (project_id,))
    names = {t["id"]: t["name"] for t in db.q("SELECT id, name FROM themes WHERE project_id=?",
                                              (project_id,))}
    return [{"id": r["id"], "theme_id": r["theme_id"],
             "theme_name": names.get(r["theme_id"]), "description": r["description"],
             "severity": r["severity"]} for r in rows]


def list_model_comparisons(ctx, project_id):
    get_project(ctx, project_id)
    rows = db.q("SELECT * FROM model_comparisons WHERE project_id=?", (project_id,))
    names = {t["id"]: t["name"] for t in db.q("SELECT id, name FROM themes WHERE project_id=?",
                                              (project_id,))}
    return [{"id": r["id"], "theme_id": r["theme_id"], "theme_name": names.get(r["theme_id"]),
             "primary_model": r["primary_model"], "secondary_model": r["secondary_model"],
             "agreement": bool(r["agreement"]), "disagreement_notes": r["disagreement_notes"]}
            for r in rows]


def audit_log(ctx, project_id):
    get_project(ctx, project_id)
    rows = db.q("SELECT * FROM audit_log WHERE project_id=? ORDER BY created_at DESC LIMIT 300",
                (project_id,))
    return [{"id": r["id"], "action": r["action"], "entity_type": r["entity_type"],
             "entity_id": r["entity_id"], "details": json.loads(r["details"] or "{}"),
             "created_at": r["created_at"]} for r in rows]


def list_methodologies(ctx, project_id):
    get_project(ctx, project_id)
    rows = db.q("SELECT methodology, created_at FROM methodology_outputs WHERE project_id=?",
                (project_id,))
    return [{"methodology": r["methodology"],
             "label": pipeline.METHODOLOGY_LABELS.get(r["methodology"], r["methodology"]),
             "created_at": r["created_at"]} for r in rows]


def get_methodology(ctx, project_id, methodology):
    get_project(ctx, project_id)
    row = db.q1("SELECT * FROM methodology_outputs WHERE project_id=? AND methodology=?",
                (project_id, methodology))
    if row is None:
        raise ApiError(404, "That methodology has not been run for this project yet.")
    return json.loads(row["payload"])


# --- exports -------------------------------------------------------------

def _export_bundle(project_id):
    project = db.q1("SELECT * FROM projects WHERE id=?", (project_id,))
    themes = _themes_with_codes(project_id)
    codes = db.q("SELECT * FROM codes WHERE project_id=? ORDER BY participant_label",
                 (project_id,))
    contradictions = db.q(
        "SELECT * FROM contradictions WHERE project_id=? ORDER BY severity DESC", (project_id,))
    comparisons = db.q("SELECT * FROM model_comparisons WHERE project_id=?", (project_id,))
    audit = db.q("SELECT * FROM audit_log WHERE project_id=? ORDER BY created_at DESC LIMIT 500",
                 (project_id,))
    methods = {r["methodology"]: json.loads(r["payload"]) for r in db.q(
        "SELECT * FROM methodology_outputs WHERE project_id=?", (project_id,))}
    workbench = {
        "codebook": caqdas.codebook(project_id),
        "quotations": caqdas.quotations_for(project_id),
        "memos": caqdas.memos(project_id),
        "links": [dict(row) for row in db.q(
            "SELECT * FROM links WHERE project_id=?", (project_id,))],
        "documents": [dict(row) for row in db.q(
            "SELECT * FROM transcripts WHERE project_id=?", (project_id,))],
    }
    targets = {t["type"] + ":" + t["id"]: t for t in caqdas.link_targets(project_id)}
    for link in workbench["links"]:
        source = targets.get(link["source_type"] + ":" + link["source_id"])
        target = targets.get(link["target_type"] + ":" + link["target_id"])
        link["source_label"] = source["label"] if source else "(removed)"
        link["target_label"] = target["label"] if target else "(removed)"
    return project, themes, codes, contradictions, comparisons, audit, methods, workbench


def _safe_name(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")[:48] or "project"


def export_xlsx(ctx, project_id):
    project = get_project(ctx, project_id)
    bundle = _export_bundle(project_id)
    data = exports.project_workbook(*bundle)
    db.audit(project_id, ctx["user"]["id"], "export.xlsx", "project", project_id, {})
    return FileResponse(data, "QRIP_" + _safe_name(project["name"]) + ".xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def export_docx(ctx, project_id):
    project = get_project(ctx, project_id)
    (p, themes, codes, contradictions, comparisons, audit, methods,
     workbench) = _export_bundle(project_id)
    summary = dashboard(ctx, project_id)
    blocks = exports.report_blocks(p, themes, codes, contradictions, comparisons,
                                   methods, summary, workbench)
    style_map = {"title": "Title", "h1": "Heading1", "h2": "Heading2",
                 "quote": "Quote", "meta": "Meta", "body": None}
    data = exports.write_docx([(style_map.get(kind), text) for kind, text in blocks])
    db.audit(project_id, ctx["user"]["id"], "export.docx", "project", project_id, {})
    return FileResponse(data, "QRIP_" + _safe_name(project["name"]) + ".docx",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def export_pdf(ctx, project_id):
    project = get_project(ctx, project_id)
    (p, themes, codes, contradictions, comparisons, audit, methods,
     workbench) = _export_bundle(project_id)
    summary = dashboard(ctx, project_id)
    blocks = exports.report_blocks(p, themes, codes, contradictions, comparisons,
                                   methods, summary, workbench)
    data = exports.write_pdf(blocks)
    db.audit(project_id, ctx["user"]["id"], "export.pdf", "project", project_id, {})
    return FileResponse(data, "QRIP_" + _safe_name(project["name"]) + ".pdf", "application/pdf")


# --- usage ---------------------------------------------------------------

def _usage_rows(user):
    if user["role"] == "owner":
        return db.q(
            "SELECT u.*, us.name AS user_name, us.email AS user_email,"
            " us.last_login_at AS user_last_login_at, p.name AS project_name"
            " FROM usage_log u LEFT JOIN users us ON us.id = u.user_id"
            " LEFT JOIN projects p ON p.id = u.project_id ORDER BY u.created_at DESC LIMIT 1000")
    return db.q(
        "SELECT u.*, us.name AS user_name, us.email AS user_email,"
        " us.last_login_at AS user_last_login_at, p.name AS project_name"
        " FROM usage_log u LEFT JOIN users us ON us.id = u.user_id"
        " LEFT JOIN projects p ON p.id = u.project_id WHERE u.user_id=?"
        " ORDER BY u.created_at DESC LIMIT 1000", (user["id"],))


def usage(ctx):
    user = require_user(ctx)
    rows = _usage_rows(user)
    logs = [{
        "id": r["id"], "user_name": r["user_name"], "user_email": r["user_email"],
        "user_last_login_at": r["user_last_login_at"], "project_id": r["project_id"],
        "project_name": r["project_name"], "operation": r["operation"], "model": r["model"],
        "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
        "total_tokens": r["total_tokens"], "estimated_cost_usd": r["estimated_cost_usd"],
        "success": bool(r["success"]), "error_message": r["error_message"],
        "created_at": r["created_at"],
    } for r in rows]
    return {
        "total_calls": len(logs),
        "total_input_tokens": sum(l["input_tokens"] for l in logs),
        "total_output_tokens": sum(l["output_tokens"] for l in logs),
        "total_tokens": sum(l["total_tokens"] for l in logs),
        "total_estimated_cost_usd": round(sum(l["estimated_cost_usd"] for l in logs), 4),
        "failure_count": sum(1 for l in logs if not l["success"]),
        "logs": logs,
    }


def usage_export(ctx):
    user = require_user(ctx)
    summary = usage(ctx)
    rows = [["User", "Email", "Last login", "Project", "Operation", "Model", "Input tokens",
             "Output tokens", "Total tokens", "Est. cost (USD)", "Success", "Error", "When"]]
    for log in summary["logs"]:
        rows.append([log["user_name"] or "", log["user_email"] or "",
                     log["user_last_login_at"] or "", log["project_name"] or "",
                     log["operation"], log["model"], log["input_tokens"],
                     log["output_tokens"], log["total_tokens"], log["estimated_cost_usd"],
                     "yes" if log["success"] else "no", log["error_message"] or "",
                     log["created_at"]])
    totals = [["Total calls", summary["total_calls"]],
              ["Total input tokens", summary["total_input_tokens"]],
              ["Total output tokens", summary["total_output_tokens"]],
              ["Total tokens", summary["total_tokens"]],
              ["Estimated cost (USD)", summary["total_estimated_cost_usd"]],
              ["Failures", summary["failure_count"]]]
    data = exports.write_xlsx([("Summary", totals), ("Usage log", rows)])
    return FileResponse(data, "QRIP_usage_master.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# --- workbench: documents, quotations, codebook ---------------------------

def project_overview(ctx, project_id):
    get_project(ctx, project_id)
    return caqdas.project_overview(project_id)


def document_reader(ctx, project_id, document_id):
    get_project(ctx, project_id)
    document = db.q1("SELECT * FROM transcripts WHERE id=? AND project_id=?",
                     (document_id, project_id))
    if document is None:
        raise ApiError(404, "Document not found.")
    return {
        "document": {**transcript_out(document), "raw_text": document["raw_text"],
                     "comment": document["comment"], "doc_group": document["doc_group"]},
        "quotations": [dict(q) for q in caqdas.quotations_for(project_id, document_id)],
        "codebook": caqdas.codebook(project_id),
    }


def create_quotation(ctx, project_id):
    get_project(ctx, project_id)
    data = body_of(ctx)
    try:
        quotation = caqdas.create_quotation(
            project_id, data.get("document_id"), data.get("start"), data.get("end"),
            created_by="user", comment=(data.get("comment") or None))
    except ValueError as exc:
        raise ApiError(400, str(exc))
    applied = []
    for name in data.get("code_names") or []:
        code = caqdas.ensure_code(project_id, name, created_by="user")
        caqdas.apply_code(project_id, quotation, code, created_by="user")
        applied.append(code["name"])
    for code_id in data.get("code_ids") or []:
        code = db.q1("SELECT * FROM codebook WHERE id=? AND project_id=?",
                     (code_id, project_id))
        if code:
            caqdas.apply_code(project_id, quotation, code, created_by="user")
            applied.append(code["name"])
    db.audit(project_id, ctx["user"]["id"], "quotation.created", "quotation", quotation["id"],
             {"codes": applied, "chars": quotation["end_offset"] - quotation["start_offset"]})
    return caqdas.quotations_for(project_id, quotation["document_id"])


def update_quotation(ctx, project_id, quotation_id):
    get_project(ctx, project_id)
    data = body_of(ctx)
    quotation = db.q1("SELECT * FROM quotations WHERE id=? AND project_id=?",
                      (quotation_id, project_id))
    if quotation is None:
        raise ApiError(404, "Quotation not found.")
    fields = {}
    for key in ("comment", "name"):
        if key in data:
            fields[key] = (data[key] or "").strip() or None
    if fields:
        sets = ", ".join(k + "=?" for k in fields)
        db.ex("UPDATE quotations SET " + sets + " WHERE id=?",
              tuple(fields.values()) + (quotation_id,))
        db.audit(project_id, ctx["user"]["id"], "quotation.updated", "quotation",
                 quotation_id, fields)
    return dict(db.q1("SELECT * FROM quotations WHERE id=?", (quotation_id,)))


def delete_quotation(ctx, project_id, quotation_id):
    get_project(ctx, project_id)
    db.ex("DELETE FROM codes WHERE quotation_id=?", (quotation_id,))
    db.ex("DELETE FROM quotations WHERE id=? AND project_id=?", (quotation_id, project_id))
    db.audit(project_id, ctx["user"]["id"], "quotation.deleted", "quotation", quotation_id, {})
    return {"deleted": True}


def code_quotation(ctx, project_id, quotation_id):
    get_project(ctx, project_id)
    data = body_of(ctx)
    quotation = db.q1("SELECT * FROM quotations WHERE id=? AND project_id=?",
                      (quotation_id, project_id))
    if quotation is None:
        raise ApiError(404, "Quotation not found.")
    if data.get("code_id"):
        code = db.q1("SELECT * FROM codebook WHERE id=? AND project_id=?",
                     (data["code_id"], project_id))
        if code is None:
            raise ApiError(404, "Code not found.")
    else:
        try:
            code = caqdas.ensure_code(project_id, data.get("name"), created_by="user")
        except ValueError as exc:
            raise ApiError(400, str(exc))
    caqdas.apply_code(project_id, quotation, code, created_by="user")
    db.audit(project_id, ctx["user"]["id"], "code.applied", "quotation", quotation_id,
             {"code": code["name"]})
    return caqdas.quotations_for(project_id, quotation["document_id"])


def uncode_quotation(ctx, project_id, quotation_id, code_id):
    get_project(ctx, project_id)
    db.ex("DELETE FROM codes WHERE quotation_id=? AND code_id=?", (quotation_id, code_id))
    db.audit(project_id, ctx["user"]["id"], "code.removed", "quotation", quotation_id,
             {"code_id": code_id})
    quotation = db.q1("SELECT * FROM quotations WHERE id=?", (quotation_id,))
    return caqdas.quotations_for(project_id, quotation["document_id"] if quotation else None)


def list_quotations(ctx, project_id):
    get_project(ctx, project_id)
    return caqdas.quotations_for(project_id)


def list_codebook(ctx, project_id):
    get_project(ctx, project_id)
    return caqdas.codebook(project_id)


def create_code(ctx, project_id):
    get_project(ctx, project_id)
    data = body_of(ctx)
    try:
        code = caqdas.ensure_code(project_id, data.get("name"), created_by="user",
                                  definition=(data.get("definition") or None),
                                  color=data.get("color"))
    except ValueError as exc:
        raise ApiError(400, str(exc))
    db.audit(project_id, ctx["user"]["id"], "code.created", "code", code["id"],
             {"name": code["name"]})
    return dict(code)


def update_code(ctx, project_id, code_id):
    get_project(ctx, project_id)
    data = body_of(ctx)
    code = db.q1("SELECT * FROM codebook WHERE id=? AND project_id=?", (code_id, project_id))
    if code is None:
        raise ApiError(404, "Code not found.")
    if data.get("name") and data["name"].strip() != code["name"]:
        caqdas.rename_code(project_id, code_id, data["name"].strip())
        db.audit(project_id, ctx["user"]["id"], "code.renamed", "code", code_id,
                 {"from": code["name"], "to": data["name"].strip()})
    fields = {}
    if "color" in data:
        fields["color"] = data["color"] or code["color"]
    if "definition" in data:
        fields["definition"] = (data["definition"] or "").strip() or None
    if fields:
        sets = ", ".join(k + "=?" for k in fields)
        db.ex("UPDATE codebook SET " + sets + " WHERE id=?", tuple(fields.values()) + (code_id,))
    return dict(db.q1("SELECT * FROM codebook WHERE id=?", (code_id,)))


def delete_code_route(ctx, project_id, code_id):
    get_project(ctx, project_id)
    code = db.q1("SELECT * FROM codebook WHERE id=? AND project_id=?", (code_id, project_id))
    if code is None:
        raise ApiError(404, "Code not found.")
    caqdas.delete_code(project_id, code_id)
    db.audit(project_id, ctx["user"]["id"], "code.deleted", "code", code_id,
             {"name": code["name"]})
    return {"deleted": True}


def merge_codes_route(ctx, project_id):
    get_project(ctx, project_id)
    data = body_of(ctx)
    keep_id = data.get("keep_id")
    merge_ids = [cid for cid in (data.get("merge_ids") or []) if cid != keep_id]
    if not keep_id or not merge_ids:
        raise ApiError(400, "Choose a code to keep and at least one to merge into it.")
    names = [r["name"] for r in db.q(
        "SELECT name FROM codebook WHERE id IN (" + ",".join("?" * len(merge_ids)) + ")",
        tuple(merge_ids))]
    caqdas.merge_codes(project_id, keep_id, merge_ids)
    db.audit(project_id, ctx["user"]["id"], "code.merged", "code", keep_id,
             {"merged": names})
    return caqdas.codebook(project_id)


def code_suggestions(ctx, project_id):
    """Codebook entries close enough in wording to be worth merging."""
    get_project(ctx, project_id)
    entries = caqdas.codebook(project_id)
    out = []
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            a, b = entries[i], entries[j]
            a_words = set(a["name"].lower().split())
            b_words = set(b["name"].lower().split())
            overlap = a_words & b_words
            union = a_words | b_words
            score = len(overlap) / len(union) if union else 0
            if score >= 0.5:
                out.append({
                    "keep_id": a["id"] if a["groundedness"] >= b["groundedness"] else b["id"],
                    "merge_id": b["id"] if a["groundedness"] >= b["groundedness"] else a["id"],
                    "a": a["name"], "b": b["name"],
                    "similarity": round(score, 2),
                    "grounded": a["groundedness"] + b["groundedness"],
                })
    out.sort(key=lambda s: (-s["similarity"], -s["grounded"]))
    return out[:15]


# --- code groups ----------------------------------------------------------

def list_code_groups(ctx, project_id):
    get_project(ctx, project_id)
    groups = db.q("SELECT * FROM code_groups WHERE project_id=? ORDER BY name", (project_id,))
    members = {}
    for row in db.q("SELECT * FROM code_group_members"):
        members.setdefault(row["group_id"], []).append(row["code_id"])
    return [{**dict(g), "code_ids": members.get(g["id"], [])} for g in groups]


def create_code_group(ctx, project_id):
    get_project(ctx, project_id)
    data = body_of(ctx)
    name = (data.get("name") or "").strip()
    if not name:
        raise ApiError(400, "A group name is required.")
    group_id = db.new_id()
    db.insert("code_groups", {"id": group_id, "project_id": project_id, "name": name,
                              "color": data.get("color") or "#6B6D76",
                              "created_at": db.now()})
    for code_id in data.get("code_ids") or []:
        db.ex("INSERT OR IGNORE INTO code_group_members (group_id, code_id) VALUES (?,?)",
              (group_id, code_id))
    db.audit(project_id, ctx["user"]["id"], "code_group.created", "code_group", group_id,
             {"name": name, "codes": len(data.get("code_ids") or [])})
    return list_code_groups(ctx, project_id)


def update_code_group(ctx, project_id, group_id):
    get_project(ctx, project_id)
    data = body_of(ctx)
    if "name" in data and data["name"].strip():
        db.ex("UPDATE code_groups SET name=? WHERE id=? AND project_id=?",
              (data["name"].strip(), group_id, project_id))
    if "code_ids" in data:
        db.ex("DELETE FROM code_group_members WHERE group_id=?", (group_id,))
        for code_id in data["code_ids"]:
            db.ex("INSERT OR IGNORE INTO code_group_members (group_id, code_id) VALUES (?,?)",
                  (group_id, code_id))
    return list_code_groups(ctx, project_id)


def delete_code_group(ctx, project_id, group_id):
    get_project(ctx, project_id)
    db.ex("DELETE FROM code_groups WHERE id=? AND project_id=?", (group_id, project_id))
    return {"deleted": True}


# --- memos, links, networks ----------------------------------------------

def list_memos(ctx, project_id):
    get_project(ctx, project_id)
    return caqdas.memos(project_id)


def create_memo(ctx, project_id):
    get_project(ctx, project_id)
    data = body_of(ctx)
    title = (data.get("title") or "").strip()
    if not title:
        raise ApiError(400, "A memo needs a title.")
    memo_id = db.new_id()
    db.insert("memos", {
        "id": memo_id, "project_id": project_id, "title": title,
        "body": data.get("body") or "", "kind": data.get("kind") or "analytic",
        "created_at": db.now(), "updated_at": db.now(),
    })
    for target in data.get("links") or []:
        db.ex("INSERT OR IGNORE INTO memo_links (memo_id, target_type, target_id)"
              " VALUES (?,?,?)", (memo_id, target.get("type"), target.get("id")))
    db.audit(project_id, ctx["user"]["id"], "memo.created", "memo", memo_id, {"title": title})
    return caqdas.memos(project_id)


def update_memo(ctx, project_id, memo_id):
    get_project(ctx, project_id)
    data = body_of(ctx)
    fields = {}
    for key in ("title", "body", "kind"):
        if key in data:
            fields[key] = data[key]
    if fields:
        fields["updated_at"] = db.now()
        sets = ", ".join(k + "=?" for k in fields)
        db.ex("UPDATE memos SET " + sets + " WHERE id=? AND project_id=?",
              tuple(fields.values()) + (memo_id, project_id))
    if "links" in data:
        db.ex("DELETE FROM memo_links WHERE memo_id=?", (memo_id,))
        for target in data["links"]:
            db.ex("INSERT OR IGNORE INTO memo_links (memo_id, target_type, target_id)"
                  " VALUES (?,?,?)", (memo_id, target.get("type"), target.get("id")))
    return caqdas.memos(project_id)


def delete_memo(ctx, project_id, memo_id):
    get_project(ctx, project_id)
    db.ex("DELETE FROM memos WHERE id=? AND project_id=?", (memo_id, project_id))
    return {"deleted": True}


def list_links(ctx, project_id):
    get_project(ctx, project_id)
    targets = {t["type"] + ":" + t["id"]: t for t in caqdas.link_targets(project_id)}
    out = []
    for row in db.q("SELECT * FROM links WHERE project_id=? ORDER BY created_at", (project_id,)):
        source = targets.get(row["source_type"] + ":" + row["source_id"])
        target = targets.get(row["target_type"] + ":" + row["target_id"])
        out.append({**dict(row),
                    "source_label": source["label"] if source else "(removed)",
                    "target_label": target["label"] if target else "(removed)"})
    return out


def create_link(ctx, project_id):
    get_project(ctx, project_id)
    data = body_of(ctx)
    required = ("source_type", "source_id", "target_type", "target_id")
    if not all(data.get(key) for key in required):
        raise ApiError(400, "A link needs a source and a target.")
    relation = data.get("relation") or "is associated with"
    if relation not in caqdas.RELATIONS:
        raise ApiError(400, "Unknown relation.")
    link_id = db.new_id()
    db.insert("links", {
        "id": link_id, "project_id": project_id,
        "source_type": data["source_type"], "source_id": data["source_id"],
        "target_type": data["target_type"], "target_id": data["target_id"],
        "relation": relation, "comment": data.get("comment"), "created_at": db.now(),
    })
    db.audit(project_id, ctx["user"]["id"], "link.created", "link", link_id,
             {"relation": relation})
    return list_links(ctx, project_id)


def delete_link(ctx, project_id, link_id):
    get_project(ctx, project_id)
    db.ex("DELETE FROM links WHERE id=? AND project_id=?", (link_id, project_id))
    return {"deleted": True}


def link_targets_route(ctx, project_id):
    get_project(ctx, project_id)
    return {"targets": caqdas.link_targets(project_id), "relations": caqdas.RELATIONS}


def list_networks(ctx, project_id):
    get_project(ctx, project_id)
    return [{**dict(row), "layout": json.loads(row["layout"] or "{}")}
            for row in db.q("SELECT * FROM networks WHERE project_id=? ORDER BY updated_at DESC",
                            (project_id,))]


def save_network(ctx, project_id):
    get_project(ctx, project_id)
    data = body_of(ctx)
    network_id = data.get("id")
    layout = json.dumps(data.get("layout") or {})
    name = (data.get("name") or "Untitled network").strip()
    if network_id and db.q1("SELECT id FROM networks WHERE id=? AND project_id=?",
                            (network_id, project_id)):
        db.ex("UPDATE networks SET name=?, layout=?, updated_at=? WHERE id=?",
              (name, layout, db.now(), network_id))
    else:
        network_id = db.new_id()
        db.insert("networks", {"id": network_id, "project_id": project_id, "name": name,
                               "layout": layout, "created_at": db.now(),
                               "updated_at": db.now()})
        db.audit(project_id, ctx["user"]["id"], "network.created", "network", network_id,
                 {"name": name})
    return list_networks(ctx, project_id)


def delete_network(ctx, project_id, network_id):
    get_project(ctx, project_id)
    db.ex("DELETE FROM networks WHERE id=? AND project_id=?", (network_id, project_id))
    return {"deleted": True}


# --- queries and agreement ------------------------------------------------

def query_co_occurrence(ctx, project_id):
    get_project(ctx, project_id)
    return caqdas.co_occurrence(project_id)


def query_code_document(ctx, project_id):
    get_project(ctx, project_id)
    return caqdas.code_document_table(project_id)


def query_retrieve(ctx, project_id):
    get_project(ctx, project_id)
    data = body_of(ctx)
    operator = data.get("operator") or "any"
    if operator not in ("all", "any", "none", "only"):
        raise ApiError(400, "operator must be all, any, none or only.")
    results = caqdas.query(project_id, operator, data.get("code_ids") or [],
                           data.get("scope") or "quotation")
    return {"count": len(results), "results": results[:200]}


def word_frequency_route(ctx, project_id):
    get_project(ctx, project_id)
    return caqdas.word_frequency(project_id)


def auto_code_search(ctx, project_id):
    get_project(ctx, project_id)
    data = body_of(ctx)
    try:
        result = caqdas.code_by_search(project_id, data.get("term"),
                                       data.get("code_name") or data.get("term"),
                                       bool(data.get("whole_word", True)))
    except ValueError as exc:
        raise ApiError(400, str(exc))
    db.audit(project_id, ctx["user"]["id"], "code.auto_search", "code",
             result["code"]["id"], {"term": data.get("term"),
                                    "applications": result["applications"]})
    return result


def agreement_route(ctx, project_id):
    get_project(ctx, project_id)
    return caqdas.agreement(project_id)


# --- review intelligence --------------------------------------------------

def _job_out(row, include_report=False):
    out = {
        "job_id": row["id"], "business_name": row["business_name"],
        "business_url": row["business_url"], "competitor_name": row["competitor_name"],
        "competitor_url": row["competitor_url"], "source": row["source"],
        "status": row["status"], "stage": row["stage"], "progress": row["progress"],
        "error": row["error"], "created_at": row["created_at"],
        "completed_at": row["completed_at"],
        "review_count": db.q1("SELECT COUNT(*) AS n FROM reviews WHERE job_id=?"
                              " AND side='primary'", (row["id"],))["n"],
        "competitor_review_count": db.q1("SELECT COUNT(*) AS n FROM reviews WHERE job_id=?"
                                         " AND side='competitor'", (row["id"],))["n"],
    }
    if include_report and row["report"]:
        out["report"] = json.loads(row["report"])
    return out


def get_job(ctx, job_id):
    user = require_user(ctx)
    row = db.q1("SELECT * FROM review_jobs WHERE id=?", (job_id,))
    if row is None:
        raise ApiError(404, "No such report.")
    if row["user_id"] != user["id"] and user["role"] != "owner":
        raise ApiError(403, "That report belongs to another user.")
    return row


def review_providers(ctx):
    require_user(ctx)
    status = review_sources.provider_status()
    return {
        "providers": status,
        "any": any(status.values()),
        "note": ("Google Maps URLs are read through a configured provider. Set "
                 "GOOGLE_MAPS_API_KEY for the official Places API (up to 5 reviews), "
                 "or SERPAPI_KEY / OUTSCRAPER_KEY for the full review history. "
                 "Pasting reviews manually needs no key."),
    }


def parse_upload(ctx):
    """Read an uploaded Outscraper export and hand back the reviews it holds."""
    require_user(ctx)
    files = ctx.get("files") or {}
    if "file" not in files:
        raise ApiError(400, "No file was uploaded.")
    filename, raw = files["file"]
    try:
        business, reviews = review_sources.parse_outscraper_file(raw, filename)
    except ValueError as exc:
        raise ApiError(400, str(exc))
    except Exception:
        raise ApiError(400, "That file could not be read as a spreadsheet. Export "
                            "the reviews from Outscraper as .xlsx or .csv.")
    normalised = review_sources.normalise(reviews)
    return {
        "business_name": business,
        "count": len(normalised),
        "reviewers": sorted({row["reviewer"] for row in normalised})[:8],
        "dated": sum(1 for row in normalised if row["months_ago"] is not None),
        "reviews": [{
            "reviewer": row["reviewer"], "rating": row["rating"], "text": row["text"],
            "relative_time": row["relative_time"], "published_at": row["published_at"],
            "owner_response": row["owner_response"],
            "photo_count": row["photo_count"],
        } for row in normalised],
    }


def job_codebook(ctx, job_id):
    """The function-1 codebook: Themes, Codes, Quotations, Confidence, Audit."""
    row, report = _require_report(ctx, job_id)
    primary = report["primary"]
    data = review_codebook.build(
        primary.get("codebook") or [], primary.get("themes") or [],
        primary.get("contradictions") or [],
        meta={"job_id": job_id, "engine": primary.get("engine"),
              "reviews": primary["kpis"]["total_reviews"]})
    return FileResponse(
        data, "QRIP_codebook_" + _safe_name(row["business_name"]) + ".xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def engine_status(ctx):
    require_user(ctx)
    state = claude_client.status()
    providers = review_sources.provider_status()
    return {
        "reasoning": state,
        "providers": providers,
        "any_provider": any(providers.values()),
        "note": ("Functions 1 and 2 read context with Claude when "
                 "ANTHROPIC_API_KEY is set. Without it they fall back to a "
                 "lexicon that matches words rather than meaning."),
    }


def analyze(ctx):
    user = require_user(ctx)
    try:
        job_id = review_jobs.create(user["id"], body_of(ctx))
    except ValueError as exc:
        raise ApiError(400, str(exc))
    row = db.q1("SELECT * FROM review_jobs WHERE id=?", (job_id,))
    return _job_out(row)


def list_jobs(ctx):
    user = require_user(ctx)
    if user["role"] == "owner":
        rows = db.q("SELECT * FROM review_jobs ORDER BY created_at DESC LIMIT 60")
    else:
        rows = db.q("SELECT * FROM review_jobs WHERE user_id=? ORDER BY created_at DESC"
                    " LIMIT 60", (user["id"],))
    return [_job_out(row) for row in rows]


def job_status(ctx, job_id):
    return _job_out(get_job(ctx, job_id))


def job_report(ctx, job_id):
    row = get_job(ctx, job_id)
    if row["status"] != "complete":
        return _job_out(row)
    return _job_out(row, include_report=True)


def delete_job(ctx, job_id):
    row = get_job(ctx, job_id)
    db.ex("DELETE FROM review_jobs WHERE id=?", (row["id"],))
    return {"deleted": True}


def _require_report(ctx, job_id):
    row = get_job(ctx, job_id)
    report = review_jobs.report_of(job_id)
    if report is None:
        raise ApiError(409, "That report is still being generated.")
    return row, report


def job_pdf(ctx, job_id):
    row, report = _require_report(ctx, job_id)
    data = review_pdf.build(report)
    return FileResponse(data, "QRIP_review_report_" + _safe_name(row["business_name"])
                        + ".pdf", "application/pdf")


def job_excel(ctx, job_id):
    row, report = _require_report(ctx, job_id)
    data = review_workbook.build(report)
    return FileResponse(
        data, "QRIP_review_analysis_" + _safe_name(row["business_name"]) + ".xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def health(ctx):
    return {"status": "ok", "engine": __import__("analysis.llm", fromlist=["llm"]).engine_info()}


def root(ctx):
    return {"name": "QRIP — Qualitative Research Intelligence Platform", "version": "1.0.0"}


# --- routing table -------------------------------------------------------

ROUTES = [
    ("POST", r"^/auth/register$", post_register),
    ("POST", r"^/auth/login$", post_login),
    ("GET", r"^/auth/me$", get_me),

    ("GET", r"^/projects$", list_projects),
    ("POST", r"^/projects$", create_project),
    ("GET", r"^/projects/([^/]+)$", get_project_route),
    ("PATCH", r"^/projects/([^/]+)$", patch_project),
    ("DELETE", r"^/projects/([^/]+)$", delete_project),
    ("PATCH", r"^/projects/([^/]+)/controls$", patch_controls),

    ("GET", r"^/projects/([^/]+)/transcripts$", list_transcripts),
    ("POST", r"^/projects/([^/]+)/transcripts$", upload_transcript),
    ("GET", r"^/projects/([^/]+)/transcripts/([^/]+)$", get_transcript),
    ("DELETE", r"^/projects/([^/]+)/transcripts/([^/]+)$", delete_transcript),

    ("POST", r"^/projects/([^/]+)/analysis/run$", run_analysis),
    ("GET", r"^/projects/([^/]+)/analysis/status$", analysis_status),

    ("GET", r"^/projects/([^/]+)/dashboard$", dashboard),
    ("GET", r"^/projects/([^/]+)/themes$", list_themes),
    ("GET", r"^/projects/([^/]+)/codes$", list_codes),
    ("GET", r"^/projects/([^/]+)/themes/merge-suggestions$", theme_merge_suggestions),
    ("PATCH", r"^/projects/([^/]+)/themes/([^/]+)/rename$", rename_theme),
    ("PATCH", r"^/projects/([^/]+)/themes/([^/]+)/status$", set_theme_status),
    ("POST", r"^/projects/([^/]+)/themes/merge$", merge_themes),
    ("POST", r"^/projects/([^/]+)/themes/split$", split_theme),

    ("GET", r"^/projects/([^/]+)/contradictions$", list_contradictions),
    ("GET", r"^/projects/([^/]+)/model-comparisons$", list_model_comparisons),
    ("GET", r"^/projects/([^/]+)/audit-log$", audit_log),
    ("GET", r"^/projects/([^/]+)/methodologies$", list_methodologies),
    ("GET", r"^/projects/([^/]+)/methodology/([^/]+)$", get_methodology),

    ("GET", r"^/projects/([^/]+)/export/xlsx$", export_xlsx),
    ("GET", r"^/projects/([^/]+)/export/docx$", export_docx),
    ("GET", r"^/projects/([^/]+)/export/pdf$", export_pdf),

    ("GET", r"^/projects/([^/]+)/overview$", project_overview),
    ("GET", r"^/projects/([^/]+)/documents/([^/]+)/reader$", document_reader),

    ("GET", r"^/projects/([^/]+)/quotations$", list_quotations),
    ("POST", r"^/projects/([^/]+)/quotations$", create_quotation),
    ("PATCH", r"^/projects/([^/]+)/quotations/([^/]+)$", update_quotation),
    ("DELETE", r"^/projects/([^/]+)/quotations/([^/]+)$", delete_quotation),
    ("POST", r"^/projects/([^/]+)/quotations/([^/]+)/codes$", code_quotation),
    ("DELETE", r"^/projects/([^/]+)/quotations/([^/]+)/codes/([^/]+)$", uncode_quotation),

    ("GET", r"^/projects/([^/]+)/codebook$", list_codebook),
    ("POST", r"^/projects/([^/]+)/codebook$", create_code),
    ("GET", r"^/projects/([^/]+)/codebook/suggestions$", code_suggestions),
    ("POST", r"^/projects/([^/]+)/codebook/merge$", merge_codes_route),
    ("PATCH", r"^/projects/([^/]+)/codebook/([^/]+)$", update_code),
    ("DELETE", r"^/projects/([^/]+)/codebook/([^/]+)$", delete_code_route),

    ("GET", r"^/projects/([^/]+)/code-groups$", list_code_groups),
    ("POST", r"^/projects/([^/]+)/code-groups$", create_code_group),
    ("PATCH", r"^/projects/([^/]+)/code-groups/([^/]+)$", update_code_group),
    ("DELETE", r"^/projects/([^/]+)/code-groups/([^/]+)$", delete_code_group),

    ("GET", r"^/projects/([^/]+)/memos$", list_memos),
    ("POST", r"^/projects/([^/]+)/memos$", create_memo),
    ("PATCH", r"^/projects/([^/]+)/memos/([^/]+)$", update_memo),
    ("DELETE", r"^/projects/([^/]+)/memos/([^/]+)$", delete_memo),

    ("GET", r"^/projects/([^/]+)/links$", list_links),
    ("POST", r"^/projects/([^/]+)/links$", create_link),
    ("DELETE", r"^/projects/([^/]+)/links/([^/]+)$", delete_link),
    ("GET", r"^/projects/([^/]+)/link-targets$", link_targets_route),

    ("GET", r"^/projects/([^/]+)/networks$", list_networks),
    ("POST", r"^/projects/([^/]+)/networks$", save_network),
    ("DELETE", r"^/projects/([^/]+)/networks/([^/]+)$", delete_network),

    ("GET", r"^/projects/([^/]+)/queries/co-occurrence$", query_co_occurrence),
    ("GET", r"^/projects/([^/]+)/queries/code-document$", query_code_document),
    ("POST", r"^/projects/([^/]+)/queries/retrieve$", query_retrieve),
    ("GET", r"^/projects/([^/]+)/word-frequency$", word_frequency_route),
    ("POST", r"^/projects/([^/]+)/auto-code/search$", auto_code_search),
    ("GET", r"^/projects/([^/]+)/agreement$", agreement_route),

    ("POST", r"^/analyze$", analyze),
    ("POST", r"^/reviews/parse-upload$", parse_upload),
    ("GET", r"^/reviews/engine$", engine_status),
    ("GET", r"^/report/([^/]+)/codebook$", job_codebook),
    ("GET", r"^/jobs$", list_jobs),
    ("GET", r"^/review-providers$", review_providers),
    ("GET", r"^/report/([^/]+)$", job_report),
    ("GET", r"^/report/([^/]+)/status$", job_status),
    ("GET", r"^/report/([^/]+)/pdf$", job_pdf),
    ("GET", r"^/report/([^/]+)/excel$", job_excel),
    ("DELETE", r"^/report/([^/]+)$", delete_job),

    ("GET", r"^/usage$", usage),
    ("GET", r"^/usage/export/xlsx$", usage_export),
    ("GET", r"^/health$", health),
    ("GET", r"^/$", root),
]

COMPILED = [(method, re.compile(pattern), handler) for method, pattern, handler in ROUTES]


def dispatch(method, path, ctx):
    allowed = False
    for route_method, pattern, handler in COMPILED:
        match = pattern.match(path)
        if not match:
            continue
        if route_method != method:
            allowed = True
            continue
        return handler(ctx, *match.groups())
    raise ApiError(405 if allowed else 404,
                   "Method not allowed." if allowed else "No such endpoint.")
