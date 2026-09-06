"""End-to-end tests for the review intelligence tool."""
import os
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               os.pardir, "backend"))

BASE = os.environ.get("QRIP_TEST_BASE", "http://127.0.0.1:8000") + "/api"
TOKEN = None
results = []


def call(method, path, body=None, raw=False, token=None):
    headers = {"Content-Type": "application/json"}
    bearer = token if token is not None else TOKEN
    if bearer:
        headers["Authorization"] = "Bearer " + bearer
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            payload = response.read()
            return response.status, (payload if raw else json.loads(payload or b"null"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def check(name, ok, detail=""):
    results.append(("PASS" if ok else "FAIL", name, str(detail)))


def wait_for(job_id, timeout=40):
    for _ in range(int(timeout / 0.4)):
        status, payload = call("GET", "/report/" + job_id + "/status")
        if payload.get("status") in ("complete", "failed"):
            return payload
        time.sleep(0.4)
    return {"status": "timeout"}


# --- unit-level: parsing --------------------------------------------------

from reviews import sources  # noqa: E402

iso, months = sources.parse_relative_time("3 months ago")
check("relative time: months", months == 3.0, months)
iso, months = sources.parse_relative_time("a year ago")
check("relative time: a year", 11.9 < months < 12.1, months)
iso, months = sources.parse_relative_time("2 weeks ago")
check("relative time: weeks", 0.4 < months < 0.5, months)
check("relative time: yesterday", sources.parse_relative_time("yesterday")[1] is not None)
check("relative time: junk", sources.parse_relative_time("banana")[1] is None)
check("bucketing", [sources.bucket_for(v) for v in (1, 4, 9, 20, None)]
      == ["0-3 months", "3-6 months", "6-12 months", "12+ months", "unknown"])

ids = sources.parse_maps_url(
    "https://www.google.com/maps/place/Harbour+Coffee/@51.5,-0.12,17z/"
    "data=!4m6!3m5!1s0x487605:0x1f2b3c!8m2")
check("maps url: name", ids.get("name") == "Harbour Coffee", ids.get("name"))
check("maps url: coords", ids.get("lat") == 51.5, ids.get("lat"))
check("maps url: feature id -> cid", ids.get("cid") == str(0x1f2b3c), ids.get("cid"))

parsed = sources.parse_manual("5 | Great staff (2 weeks ago)\n1 | Cold food, long wait")
check("manual: pipe format", [row["rating"] for row in parsed] == [5.0, 1.0], parsed)
check("manual: relative captured", parsed[0]["relative_time"] == "2 weeks ago",
      parsed[0]["relative_time"])
csv_rows = sources.parse_manual("rating,review,date\n4,Nice place,3 months ago\n"
                                "2,Slow service,a month ago")
check("manual: csv", len(csv_rows) == 2 and csv_rows[0]["rating"] == 4.0, csv_rows)
json_rows = sources.parse_manual('[{"stars": 5, "text": "Lovely", "when": "a week ago"}]')
check("manual: json", json_rows and json_rows[0]["rating"] == 5.0, json_rows)

# --- API ------------------------------------------------------------------

status, payload = call("POST", "/auth/login",
                       {"email": "demo@qrip.local", "password": "demo-password"})
TOKEN = payload["access_token"]

status, providers = call("GET", "/review-providers")
check("providers endpoint", status == 200 and "providers" in providers, status)

status, refused = call("POST", "/analyze", {"mode": "manual",
                                            "business_reviews": "Only one review here"})
check("rejects too few reviews", status == 400 and "three reviews" in refused["detail"],
      refused.get("detail", "")[:60])

if not providers["any"]:
    status, no_provider = call("POST", "/analyze", {
        "mode": "url", "business_url": "https://maps.google.com/?cid=123"})
    check("url mode explains missing provider",
          status == 400 and "provider is configured" in no_provider["detail"],
          no_provider.get("detail", "")[:60])

PASTE = """5 | The flat white is the best in town and the baristas remember your order (2 weeks ago)
2 | Waited 25 minutes for a sandwich that arrived cold. Nobody apologised (a month ago)
4 | Lovely spot by the water, though the prices have crept up a lot (3 months ago)
1 | Card machine down again and they would not take cash. Second time this has happened (2 months ago)
5 | Staff are genuinely warm and the pastries are excellent (5 months ago)
3 | Coffee good, seating cramped and the toilets were out of order (8 months ago)
2 | Ordered online, the order never came through to the counter. Had to queue again (10 months ago)
5 | Best independent cafe locally, the owner is lovely (14 months ago)"""
COMPETITOR = """5 | Order ready in four minutes and they text you when it is done (3 weeks ago)
5 | Prices clearly on the board, no surprises, comfortable seating (2 months ago)
4 | Good coffee and spotless tables every visit (6 months ago)
5 | The app works properly and the staff are quick and friendly (9 months ago)
3 | Slightly pricey but you get what you pay for (12 months ago)"""

status, job = call("POST", "/analyze", {
    "mode": "paste", "business_name": "Harbour Coffee House",
    "competitor_name": "Bridge Street Roasters",
    "business_reviews": PASTE, "competitor_reviews": COMPETITOR})
check("analyze accepted", status == 200 and job.get("job_id"), status)
job_id = job["job_id"]
final = wait_for(job_id)
check("job completes", final.get("status") == "complete",
      (final.get("error") or final.get("status") or "")[:120])

status, full = call("GET", "/report/" + job_id)
report = full.get("report") or {}
primary = report.get("primary") or {}
check("report: kpis", all(key in primary.get("kpis", {}) for key in
      ("net_sentiment_score", "total_reviews", "average_rating", "negative_ratio")),
      list(primary.get("kpis", {}))[:4])
check("report: codebook is sentence-level",
      len(primary.get("codebook", [])) >= len(primary.get("reviews", [])),
      str(len(primary.get("codebook", []))) + " codes / "
      + str(len(primary.get("reviews", []))) + " reviews")
first_code = (primary.get("codebook") or [{}])[0]
check("codebook schema", all(key in first_code for key in
      ("code", "theme", "reviewer_id", "emotion", "intent", "valence", "confidence",
       "quote", "literal_meaning", "alternative_interpretation")),
      list(first_code)[:5])
check("report: temporal buckets", len(primary.get("temporal", {}).get("series", [])) >= 3,
      len(primary.get("temporal", {}).get("series", [])))
check("report: bottlenecks", len(primary.get("bottlenecks", [])) >= 1,
      [b["issue"] for b in primary.get("bottlenecks", [])])
check("report: bottlenecks carry evidence",
      all(entry["evidence"] for entry in primary.get("bottlenecks", [])), "")
check("report: contradictions", isinstance(primary.get("contradictions"), list),
      len(primary.get("contradictions", [])))
check("report: content counts has 8 categories",
      len(primary.get("content", {}).get("categories", [])) == 8,
      primary.get("content", {}).get("categories"))
check("report: framework has 6 stages",
      len(primary.get("framework", {}).get("stages", [])) == 6,
      primary.get("framework", {}).get("stages"))
check("report: 5 radar dimensions", len(primary.get("dimensions", [])) == 5,
      [d["dimension"] for d in primary.get("dimensions", [])])
comparison = report.get("comparison") or {}
check("comparison: radar", len(comparison.get("radar", [])) == 5, "")
check("comparison: adoption parameters", len(comparison.get("adoption_parameters", [])) >= 1,
      [a["parameter"] for a in comparison.get("adoption_parameters", [])])
check("comparison: headline", bool(comparison.get("headline")),
      comparison.get("headline", "")[:60])
check("scores are 1-10", all(1 <= entry["primary"] <= 10 and 1 <= entry["competitor"] <= 10
                             for entry in comparison.get("radar", [])), "")

# a five-star review whose text is negative must be caught
status, flag_job = call("POST", "/analyze", {
    "mode": "paste", "business_name": "Contradiction check",
    "business_reviews": (
        "5 | Waited an hour, the food was cold and the manager was rude and dismissive\n"
        "4 | Lovely staff and quick service, no complaints at all\n"
        "5 | Excellent coffee, friendly team, will be back\n"
        "3 | Fine but nothing special")})
flag_final = wait_for(flag_job["job_id"])
status, flag_full = call("GET", "/report/" + flag_job["job_id"])
flags = [item for item in flag_full["report"]["primary"]["contradictions"]
         if item["kind"] == "rating-vs-text"]
check("catches five-star complaint", len(flags) >= 1,
      flags[0]["description"][:80] if flags else "none found")

# exports
status, pdf = call("GET", "/report/" + job_id + "/pdf", raw=True)
check("pdf export", status == 200 and pdf[:5] == b"%PDF-"
      and pdf.rstrip().endswith(b"%%EOF"), str(len(pdf)) + " bytes")
check("pdf has pages", pdf.count(b"/Type /Page ") >= 4, pdf.count(b"/Type /Page "))
text = pdf.decode("latin-1")
streams = re.findall(r"stream\r?\n(.*?)\r?\nendstream", text, re.S)
rendered = " ".join(" ".join(re.findall(r"\((.*?)\) Tj", stream, re.S))
                    for stream in streams)
for marker in ["Executive dashboard", "Temporal", "bottleneck", "Framework matrix",
               "Competitor cross-comparison", "Adoption parameters",
               "Method and limitations"]:
    check("pdf section: " + marker, marker in rendered, "")

status, xlsx = call("GET", "/report/" + job_id + "/excel", raw=True)
check("xlsx export", status == 200 and xlsx[:2] == b"PK", str(len(xlsx)) + " bytes")
with zipfile.ZipFile(io.BytesIO(xlsx)) as archive:
    check("xlsx valid", archive.testzip() is None, "")
    names = re.findall(r'name="([^"]+)"', archive.read("xl/workbook.xml").decode())
for sheet in ["Codebook", "Themes", "Contradictions", "Content Counts", "Framework Matrix"]:
    check("xlsx sheet: " + sheet, sheet in names, "")

# demo mode and job listing
status, demo_job = call("POST", "/analyze", {"mode": "demo"})
demo_final = wait_for(demo_job["job_id"])
check("demo mode", demo_final.get("status") == "complete",
      (demo_final.get("error") or demo_final.get("status") or "")[:80])

status, one_by_one = call("POST", "/analyze", {
    "mode": "form", "business_name": "Manual entry check",
    "business_review_rows": [
        {"rating": 5, "reviewer": "A", "relative_time": "1 month ago",
         "text": "Superb service and the room was spotless throughout our stay"},
        {"rating": 2, "reviewer": "B", "relative_time": "2 months ago",
         "text": "Check in took 40 minutes and nobody explained the delay"},
        {"rating": 4, "reviewer": "C", "relative_time": "3 months ago",
         "text": "Comfortable bed, decent breakfast, parking was a nightmare"},
    ]})
form_final = wait_for(one_by_one["job_id"])
check("one-by-one entry mode", form_final.get("status") == "complete",
      (form_final.get("error") or form_final.get("status") or "")[:80])

status, jobs = call("GET", "/jobs")
check("job listing", status == 200 and any(item["job_id"] == job_id for item in jobs),
      len(jobs))

# authorisation
saved = TOKEN
status, blocked = call("GET", "/report/" + job_id, token="")
check("unauthenticated blocked", status == 401, status)
TOKEN = saved
status, missing = call("GET", "/report/does-not-exist")
check("missing report 404", status == 404, status)

for outcome, name, detail in results:
    print(outcome, "-", name, ("(" + detail + ")") if detail else "")
failures = [row for row in results if row[0] == "FAIL"]
print("\n%d/%d passed" % (len(results) - len(failures), len(results)))
sys.exit(1 if failures else 0)
