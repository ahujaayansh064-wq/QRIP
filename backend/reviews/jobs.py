"""Job orchestration: ingest, analyse, compare, store."""
import json
import threading
import traceback
from datetime import datetime, timezone

import db
from . import analysis, compare, sources

_running = set()
_lock = threading.Lock()

MAX_REVIEWS = 400


def create(user_id, payload):
    """Validate the request, ingest reviews, and queue the analysis."""
    mode = (payload.get("mode") or "manual").lower()
    business_name = (payload.get("business_name") or "").strip()
    business_url = (payload.get("business_url") or "").strip() or None
    competitor_name = (payload.get("competitor_name") or "").strip() or None
    competitor_url = (payload.get("competitor_url") or "").strip() or None

    primary_records, competitor_records = [], []
    source_label = ""

    if mode == "demo":
        business_name, raw = sources.demo_records("primary")
        primary_records = raw
        competitor_name, raw_competitor = sources.demo_records("competitor")
        competitor_records = raw_competitor
        source_label = "bundled demo dataset"
    elif mode == "url":
        if not business_url:
            raise ValueError("A Google Maps URL is required.")
        fetched, provider = sources.fetch_from_url(business_url, MAX_REVIEWS)
        primary_records = fetched["reviews"]
        business_name = business_name or fetched.get("name") or "Primary business"
        source_label = "Google Maps via " + provider
        if competitor_url:
            rival, _ = sources.fetch_from_url(competitor_url, MAX_REVIEWS)
            competitor_records = rival["reviews"]
            competitor_name = competitor_name or rival.get("name") or "Competitor"
    else:
        primary_records = sources.parse_manual(payload.get("business_reviews") or "")
        if payload.get("business_review_rows"):
            primary_records += [sources._normalise_keys(row)
                                for row in payload["business_review_rows"]]
        competitor_records = sources.parse_manual(payload.get("competitor_reviews") or "")
        if payload.get("competitor_review_rows"):
            competitor_records += [sources._normalise_keys(row)
                                   for row in payload["competitor_review_rows"]]
        business_name = business_name or "Primary business"
        source_label = "manually entered reviews"

    primary = sources.normalise(primary_records)[:MAX_REVIEWS]
    rival = sources.normalise(competitor_records)[:MAX_REVIEWS]
    if len(primary) < 3:
        raise ValueError("At least three reviews are needed for a meaningful report; "
                         "found " + str(len(primary)) + ".")
    if rival and len(rival) < 3:
        rival = []

    job_id = db.new_id()
    db.insert("review_jobs", {
        "id": job_id, "user_id": user_id, "business_name": business_name,
        "business_url": business_url, "competitor_name": competitor_name if rival else None,
        "competitor_url": competitor_url, "source": source_label, "status": "queued",
        "stage": "queued", "progress": 0.0, "error": None, "report": None,
        "created_at": db.now(), "completed_at": None,
    })
    _store(job_id, "primary", primary)
    if rival:
        _store(job_id, "competitor", rival)

    db.audit(None, user_id, "review_job.created", "review_job", job_id, {
        "business": business_name, "reviews": len(primary),
        "competitor_reviews": len(rival), "source": source_label})
    start(job_id)
    return job_id


def _store(job_id, side, reviews):
    rows = []
    for index, review in enumerate(reviews):
        rows.append({
            "id": db.new_id(), "job_id": job_id, "side": side,
            "reviewer": review["reviewer"], "rating": review["rating"],
            "text": review["text"], "relative_time": review["relative_time"],
            "published_at": review["published_at"], "months_ago": review["months_ago"],
            "owner_response": review["owner_response"],
            "photo_count": review["photo_count"], "idx": index,
        })
    db.insert_many("reviews", rows)


def start(job_id):
    with _lock:
        if job_id in _running:
            return False
        _running.add(job_id)
    thread = threading.Thread(target=_run_guarded, args=(job_id,), daemon=True)
    thread.start()
    return True


def _run_guarded(job_id):
    try:
        run(job_id)
    except Exception as exc:
        db.ex("UPDATE review_jobs SET status='failed', stage='failed', error=? WHERE id=?",
              (str(exc)[:400] + " | " + traceback.format_exc()[-400:], job_id))
    finally:
        with _lock:
            _running.discard(job_id)


def _stage(job_id, stage, progress):
    db.ex("UPDATE review_jobs SET status='running', stage=?, progress=? WHERE id=?",
          (stage, round(progress, 3), job_id))


def _load(job_id, side, prefix):
    rows = db.q("SELECT * FROM reviews WHERE job_id=? AND side=? ORDER BY idx",
                (job_id, side))
    out = []
    for index, row in enumerate(rows, start=1):
        out.append({
            "id": row["id"], "reviewer_id": prefix + str(index),
            "reviewer": row["reviewer"] or "Anonymous", "rating": row["rating"],
            "text": row["text"], "relative_time": row["relative_time"],
            "published_at": row["published_at"], "months_ago": row["months_ago"],
            "owner_response": row["owner_response"], "photo_count": row["photo_count"],
        })
    return out


def run(job_id):
    job = db.q1("SELECT * FROM review_jobs WHERE id=?", (job_id,))
    if job is None:
        raise ValueError("job not found")

    _stage(job_id, "reading reviews", 0.08)
    primary_reviews = _load(job_id, "primary", "R")
    competitor_reviews = _load(job_id, "competitor", "C")

    _stage(job_id, "coding statements", 0.28)
    primary = analysis.analyse(primary_reviews, job["business_name"])

    competitor = None
    comparison = None
    if competitor_reviews:
        _stage(job_id, "coding competitor reviews", 0.6)
        competitor = analysis.analyse(competitor_reviews,
                                      job["competitor_name"] or "Competitor")
        _stage(job_id, "cross-comparing", 0.82)
        comparison = compare.compare(primary, competitor)

    _stage(job_id, "assembling report", 0.92)
    report = {
        "job_id": job_id,
        "primary": primary,
        "competitor": competitor,
        "comparison": comparison,
        "meta": {
            "business_name": job["business_name"],
            "business_url": job["business_url"],
            "competitor_name": job["competitor_name"],
            "competitor_url": job["competitor_url"],
            "source_label": job["source"],
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "engine": _engine_label(),
        },
    }
    db.ex("UPDATE review_jobs SET status='complete', stage='complete', progress=1.0,"
          " report=?, completed_at=? WHERE id=?",
          (json.dumps(report), db.now(), job_id))
    return report


def _engine_label():
    from analysis import llm
    return llm.engine_info()["primary_model"]


def report_of(job_id):
    row = db.q1("SELECT report FROM review_jobs WHERE id=?", (job_id,))
    if row is None or not row["report"]:
        return None
    return json.loads(row["report"])
