"""Exercise the manual-analysis (CAQDAS) endpoints."""
import os
import sys
import json
import urllib.request
import urllib.error

BASE = os.environ.get("QRIP_TEST_BASE", "http://127.0.0.1:8000") + "/api"
TOKEN = None
results = []


def call(method, path, body=None):
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def check(name, ok, detail=""):
    results.append(("PASS" if ok else "FAIL", name, str(detail)))


status, payload = call("POST", "/auth/login",
                       {"email": "demo@qrip.local", "password": "demo-password"})
TOKEN = payload["access_token"]
projects = call("GET", "/projects")[1]
# pin to the demo project: never write test data into a real one
pid = next(p["id"] for p in projects if "referral" in p["name"])

status, overview = call("GET", "/projects/" + pid + "/overview")
check("overview", status == 200 and overview["quotations"] > 100, overview)

docs = call("GET", "/projects/" + pid + "/transcripts")[1]
doc_id = docs[0]["id"]
status, reader = call("GET", "/projects/" + pid + "/documents/" + doc_id + "/reader")
ok = status == 200 and reader["document"]["raw_text"] and reader["quotations"]
check("document reader", ok, str(len(reader["quotations"])) + " quotations")

# every auto quotation must line up with the document text exactly
body = reader["document"]["raw_text"]
mismatched = [q for q in reader["quotations"]
              if body[q["start_offset"]:q["end_offset"]] != q["text"]]
check("quotation offsets exact", not mismatched, str(len(mismatched)) + " mismatched")

# hand coding
status, quotations = call("POST", "/projects/" + pid + "/quotations", {
    "document_id": doc_id, "start": 118, "end": 200,
    "code_names": ["Broken promise of timescale"], "comment": "Coded by hand in the test."})
check("create quotation + code", status == 200 and any(
    q["created_by"] == "user" for q in quotations), status)
mine = [q for q in quotations if q["created_by"] == "user"][0]

status, updated = call("POST", "/projects/" + pid + "/quotations/" + mine["id"] + "/codes",
                       {"name": "Waiting"})
check("apply second code", status == 200 and len(
    [q for q in updated if q["id"] == mine["id"]][0]["codes"]) == 2, status)

codebook = call("GET", "/projects/" + pid + "/codebook")[1]
hand = [c for c in codebook if c["created_by"] == "user"]
check("codebook has hand codes", len(hand) >= 2, str(len(codebook)) + " total")
check("groundedness computed", all("groundedness" in c for c in codebook), "")

target = sorted(codebook, key=lambda c: -c["groundedness"])[0]
status, renamed = call("PATCH", "/projects/" + pid + "/codebook/" + target["id"],
                       {"name": "Renamed by hand", "color": "#7A2E4A",
                        "definition": "Applied where the account turns on the system."})
check("rename + recolour code", status == 200 and renamed["name"] == "Renamed by hand", status)

status, suggestions = call("GET", "/projects/" + pid + "/codebook/suggestions")
check("merge suggestions", status == 200, str(len(suggestions)) + " pairs")

if suggestions:
    status, merged = call("POST", "/projects/" + pid + "/codebook/merge",
                          {"keep_id": suggestions[0]["keep_id"],
                           "merge_ids": [suggestions[0]["merge_id"]]})
    check("merge codes", status == 200 and len(merged) == len(codebook) - 1, status)

# groups
group_name = "Access and waiting " + str(len(codebook))
status, groups = call("POST", "/projects/" + pid + "/code-groups",
                      {"name": group_name, "code_ids": [c["id"] for c in codebook[:4]]})
made = [g for g in groups if g["name"] == group_name]
check("create code group", status == 200 and made and len(made[0]["code_ids"]) == 4, status)
for stale in [g for g in groups if g["name"] != group_name]:
    call("DELETE", "/projects/" + pid + "/code-groups/" + stale["id"])

# memos
status, memos = call("POST", "/projects/" + pid + "/memos", {
    "title": "Why 'the system does not do that' matters",
    "body": "Every participant reaches for the passive voice when describing the process.",
    "links": [{"type": "code", "id": codebook[0]["id"]}]})
check("create memo", status == 200 and memos[0]["links"], status)
status, memos = call("PATCH", "/projects/" + pid + "/memos/" + memos[0]["id"],
                     {"body": "Updated body."})
check("update memo", status == 200 and memos[0]["body"] == "Updated body.", status)

# links and networks
targets = call("GET", "/projects/" + pid + "/link-targets")[1]
codes_t = [t for t in targets["targets"] if t["type"] == "code"][:2]
status, links = call("POST", "/projects/" + pid + "/links", {
    "source_type": "code", "source_id": codes_t[0]["id"],
    "target_type": "code", "target_id": codes_t[1]["id"],
    "relation": "is cause of"})
check("create typed link", status == 200 and links[0]["relation"] == "is cause of", status)
status, bad = call("POST", "/projects/" + pid + "/links", {
    "source_type": "code", "source_id": codes_t[0]["id"],
    "target_type": "code", "target_id": codes_t[1]["id"], "relation": "invented"})
check("reject unknown relation", bad and status == 400, status)

status, networks = call("POST", "/projects/" + pid + "/networks", {
    "name": "Access map", "layout": {"nodes": [{"id": codes_t[0]["id"], "x": 10, "y": 20}]}})
check("save network", status == 200 and networks[0]["layout"]["nodes"], status)

# queries
status, co = call("GET", "/projects/" + pid + "/queries/co-occurrence")
check("co-occurrence", status == 200 and co["nodes"], str(len(co["edges"])) + " edges")

status, table = call("GET", "/projects/" + pid + "/queries/code-document")
check("code-document table", status == 200 and table["rows"],
      str(len(table["rows"])) + "x" + str(len(table["columns"])))

ids = [c["id"] for c in sorted(codebook, key=lambda c: -c["groundedness"])[:2]]
status, retrieved = call("POST", "/projects/" + pid + "/queries/retrieve",
                         {"operator": "any", "code_ids": ids})
check("retrieve any", status == 200 and retrieved["count"] > 0, retrieved.get("count"))
status, retrieved_all = call("POST", "/projects/" + pid + "/queries/retrieve",
                             {"operator": "all", "code_ids": ids})
check("retrieve all <= any", status == 200 and retrieved_all["count"] <= retrieved["count"],
      retrieved_all.get("count"))
status, bad_op = call("POST", "/projects/" + pid + "/queries/retrieve",
                      {"operator": "sideways", "code_ids": ids})
check("reject bad operator", status == 400, status)

status, words = call("GET", "/projects/" + pid + "/word-frequency")
check("word frequency", status == 200 and words["words"], str(words.get("total_words")))

status, coded = call("POST", "/projects/" + pid + "/auto-code/search",
                     {"term": "referral", "code_name": "Mentions referral"})
check("auto-code by search", status == 200 and coded["applications"] > 0,
      str(coded.get("applications")) + " applications")

status, agree = call("GET", "/projects/" + pid + "/agreement")
check("agreement", status == 200 and "comparable_quotations" in agree,
      "comparable=" + str(agree.get("comparable_quotations")))

# re-run analysis must preserve hand work
before = call("GET", "/projects/" + pid + "/overview")[1]["hand_coded"]
call("POST", "/projects/" + pid + "/analysis/run")
import time
for _ in range(80):
    st = call("GET", "/projects/" + pid + "/analysis/status")[1]
    if not st["analysis_in_progress"]:
        break
    time.sleep(0.4)
after = call("GET", "/projects/" + pid + "/overview")[1]
check("re-run preserves hand coding", after["hand_coded"] == before,
      str(before) + " -> " + str(after["hand_coded"]))
check("re-run preserves memos", after["memos"] >= 1, after["memos"])
check("re-run preserves links", after["links"] >= 1, after["links"])
check("analysis completed", not st["analysis_in_progress"] and not st["last_analysis_error"],
      st.get("last_analysis_error"))

status, agree2 = call("GET", "/projects/" + pid + "/agreement")
check("agreement after re-run", status == 200, agree2.get("note", "")[:60])

for outcome, name, detail in results:
    print(outcome, "-", name, ("(" + detail + ")") if detail else "")
fails = [r for r in results if r[0] == "FAIL"]
print("\n%d/%d passed" % (len(results) - len(fails), len(results)))
sys.exit(1 if fails else 0)
