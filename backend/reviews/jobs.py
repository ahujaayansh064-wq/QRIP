"""Job orchestration: ingest, analyse, compare, store."""
import json
import threading
import traceback
from datetime import datetime, timezone

import claude
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
    # competitors: [{name, url, reviews, rows}] - any number of them
    rivals_in = list(payload.get("competitors") or [])
    if competitor_name or competitor_url or payload.get("competitor_reviews"):
        rivals_in.insert(0, {"name": competitor_name, "url": competitor_url,
                             "reviews": payload.get("competitor_reviews"),
                             "rows": payload.get("competitor_review_rows")})

    primary_records, competitor_records = [], []
    source_label = ""

    rivals = []
    if mode == "demo":
        business_name, raw = sources.demo_records("primary")
        primary_records = raw
        demo_name, demo_rows = sources.demo_records("competitor")
        rivals = [{"name": demo_name, "records": demo_rows}]
        source_label = "bundled demo dataset"
    elif mode == "url":
        if not business_url:
            raise ValueError("A Google Maps URL is required.")
        fetched, provider = sources.fetch_from_url(business_url, MAX_REVIEWS)
        primary_records = fetched["reviews"]
        business_name = business_name or fetched.get("name") or "Primary business"
        source_label = "Google Maps via " + provider
        for entry in rivals_in:
            if not (entry.get("url") or "").strip():
                continue
            fetched_rival, _ = sources.fetch_from_url(entry["url"].strip(), MAX_REVIEWS)
            rivals.append({
                "name": (entry.get("name") or "").strip()
                        or fetched_rival.get("name") or "Competitor",
                "records": fetched_rival["reviews"]})
    else:
        primary_records = sources.parse_manual(payload.get("business_reviews") or "")
        if payload.get("business_review_rows"):
            primary_records += [sources._normalise_keys(row)
                                for row in payload["business_review_rows"]]
        for index, entry in enumerate(rivals_in, start=1):
            records = sources.parse_manual(entry.get("reviews") or "")
            if entry.get("rows"):
                records += [sources._normalise_keys(row) for row in entry["rows"]]
            if records:
                rivals.append({
                    "name": (entry.get("name") or "").strip()
                            or ("Competitor " + str(index)),
                    "records": records})
        business_name = business_name or "Primary business"
        source_label = "manually entered reviews"

    primary = sources.normalise(primary_records)[:MAX_REVIEWS]
    if len(primary) < 3:
        raise ValueError("At least three reviews are needed for a meaningful report; "
                         "found " + str(len(primary)) + ".")
    prepared = []
    for rival in rivals:
        rows = sources.normalise(rival["records"])[:MAX_REVIEWS]
        if len(rows) >= 3:      # too few to compare against fairly
            prepared.append({"name": rival["name"], "reviews": rows})

    job_id = db.new_id()
    db.insert("review_jobs", {
        "id": job_id, "user_id": user_id, "business_name": business_name,
        "business_url": business_url,
        "competitor_name": prepared[0]["name"] if prepared else None,
        "competitor_url": competitor_url, "source": source_label, "status": "queued",
        "stage": "queued", "progress": 0.0, "error": None, "report": None,
        "created_at": db.now(), "completed_at": None,
    })
    _store(job_id, "primary", primary)
    for index, rival in enumerate(prepared, start=1):
        _store(job_id, "competitor:%d" % index, rival["reviews"], rival["name"])

    db.audit(None, user_id, "review_job.created", "review_job", job_id, {
        "business": business_name, "reviews": len(primary),
        "competitors": [rival["name"] for rival in prepared],
        "source": source_label})
    start(job_id)
    return job_id


def _store(job_id, side, reviews, label=None):
    rows = []
    for index, review in enumerate(reviews):
        rows.append({
            "id": db.new_id(), "job_id": job_id, "side": side,
            "side_label": label,
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

    _stage(job_id, "reading reviews", 0.05)
    primary_reviews = _load(job_id, "primary", "R")
    rival_sides = [row["side"] for row in db.q(
        "SELECT DISTINCT side FROM reviews WHERE job_id=? AND side!='primary'"
        " ORDER BY side", (job_id,))]

    usage = {"input": 0, "output": 0, "cost": 0.0, "calls": 0}

    def record(input_tokens, output_tokens, cost):
        usage["input"] += input_tokens
        usage["output"] += output_tokens
        usage["cost"] += cost
        usage["calls"] += 1

    def staged(base, span):
        def report(name, fraction):
            _stage(job_id, name, base + span * max(0.0, min(1.0, fraction)))
        return report

    primary = analysis.analyse(primary_reviews, job["business_name"],
                               on_usage=record, on_stage=staged(0.08, 0.45))

    competitors = []
    comparison = None
    if rival_sides:
        span = 0.25 / len(rival_sides)
        for index, side in enumerate(rival_sides):
            rows = _load(job_id, side, "C%d-" % (index + 1))
            if not rows:
                continue
            label = (db.q1("SELECT side_label FROM reviews WHERE job_id=? AND side=?"
                           " AND side_label IS NOT NULL LIMIT 1", (job_id, side))
                     or {"side_label": None})["side_label"]
            competitors.append(analysis.analyse(
                rows, label or ("Competitor " + str(index + 1)),
                on_usage=record, on_stage=staged(0.55 + index * span, span)))
        if competitors:
            _stage(job_id, "cross-comparing", 0.84)
            comparison = compare.compare_many(primary, competitors)

    if usage["calls"]:
        db.log_usage(job["user_id"], None, "reviews.analysis", claude.MODEL,
                     usage["input"], usage["output"], usage["cost"])

    _stage(job_id, "assembling report", 0.92)
    report = {
        "job_id": job_id,
        "primary": primary,
        "competitor": competitors[0] if competitors else None,
        "competitors": competitors,
        "comparison": comparison,
        "meta": {
            "business_name": job["business_name"],
            "business_url": job["business_url"],
            "competitor_name": job["competitor_name"],
            "competitor_names": [rival["label"] for rival in competitors],
            "competitor_url": job["competitor_url"],
            "source_label": job["source"],
            "engine": primary.get("engine", {}),
            "usage": {"calls": usage["calls"], "input_tokens": usage["input"],
                      "output_tokens": usage["output"],
                      "estimated_cost_usd": round(usage["cost"], 4)},
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
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
