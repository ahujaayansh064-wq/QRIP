"""End-to-end API exercise against a running QRIP server."""
import json
import urllib.request
import urllib.error
import zipfile
import io
import os
import sys

BASE = os.environ.get("QRIP_TEST_BASE", "http://127.0.0.1:8000") + "/api"
TOKEN = None


def call(method, path, body=None, raw=False, form=None):
    url = BASE + path
    data = None
    headers = {}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if form is not None:
        boundary = "----qriptest"
        parts = []
        for key, value in form["fields"].items():
            parts.append("--" + boundary)
            parts.append('Content-Disposition: form-data; name="%s"' % key)
            parts.append("")
            parts.append(value)
        name, filename, content = form["file"]
        parts.append("--" + boundary)
        parts.append('Content-Disposition: form-data; name="%s"; filename="%s"' % (name, filename))
        parts.append("Content-Type: text/plain")
        parts.append("")
        parts.append(content)
        parts.append("--" + boundary + "--")
        parts.append("")
        data = "\r\n".join(parts).encode()
        headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            payload = resp.read()
            if raw:
                return resp.status, payload
            return resp.status, json.loads(payload or b"null")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


results = []


def check(name, condition, detail=""):
    results.append((("PASS" if condition else "FAIL"), name, detail))


status, payload = call("POST", "/auth/login",
                       {"email": "demo@qrip.local", "password": "demo-password"})
check("login", status == 200 and "access_token" in payload, str(status))
TOKEN = payload.get("access_token")

status, me = call("GET", "/auth/me")
check("auth/me", status == 200 and me["email"] == "demo@qrip.local", me.get("role", ""))

status, bad = call("POST", "/auth/login", {"email": "demo@qrip.local", "password": "wrong"})
check("bad password rejected", status == 401, str(status))

status, projects = call("GET", "/projects")
check("list projects", status == 200 and len(projects) >= 1, str(len(projects)))
# pin to the demo project: never write test data into a real one
pid = next(p["id"] for p in projects if "referral" in p["name"])

for path, key in [("/dashboard", "theme_count"), ("/themes", None), ("/codes", None),
                  ("/contradictions", None), ("/model-comparisons", None),
                  ("/audit-log", None), ("/transcripts", None), ("/methodologies", None),
                  ("/analysis/status", "stage"), ("/themes/merge-suggestions", None)]:
    status, data = call("GET", "/projects/" + pid + path)
    ok = status == 200 and (key is None or key in data)
    check("GET" + path, ok, str(status) + " n=" + str(len(data) if isinstance(data, list) else "-"))

for method in ["thematic", "grounded_theory", "ipa", "framework", "narrative", "content"]:
    status, data = call("GET", "/projects/" + pid + "/methodology/" + method)
    check("methodology " + method, status == 200 and data.get("methodology") == method, str(status))

# theme editing
status, themes = call("GET", "/projects/" + pid + "/themes")
first = themes[0]
status, renamed = call("PATCH", "/projects/" + pid + "/themes/" + first["id"] + "/rename",
                       {"name": "Waiting without information"})
check("rename theme", status == 200 and renamed["name"] == "Waiting without information", str(status))

status, updated = call("PATCH", "/projects/" + pid + "/themes/" + first["id"] + "/status",
                       {"status": "review"})
check("set theme status", status == 200 and updated["status"] == "review", str(status))

status, bad = call("PATCH", "/projects/" + pid + "/themes/" + first["id"] + "/status",
                   {"status": "nonsense"})
check("reject bad status", status == 400, str(status))

code_ids = [c["id"] for c in first["codes"][:2]]
status, split = call("POST", "/projects/" + pid + "/themes/split",
                     {"new_theme_name": "Split test theme", "code_ids_for_new_theme": code_ids})
check("split theme", status == 200 and split["quote_count"] == len(code_ids), str(status))

status, merged = call("POST", "/projects/" + pid + "/themes/merge",
                      {"theme_ids": [first["id"], split["id"]], "new_name": "Re-merged theme"})
check("merge themes", status == 200 and merged["name"] == "Re-merged theme", str(status))

# controls
status, ctrl = call("PATCH", "/projects/" + pid + "/controls",
                    {"similarity_threshold": 0.3, "confidence_threshold": 0.6,
                     "min_supporting_quotations": 4, "participant_frequency_threshold": 2,
                     "contradiction_sensitivity": 0.6, "coding_granularity": "sentence"})
check("patch controls", status == 200 and ctrl["min_supporting_quotations"] == 4, str(status))

status, bad = call("PATCH", "/projects/" + pid + "/controls", {"coding_granularity": "wrong"})
check("reject bad granularity", status == 400, str(status))

# transcript upload + delete
sample = ("Interviewer: How did you find the process?\n"
          "P9: It took months and nobody told me anything, which was the hardest part.\n"
          "P9: When the letter finally came I had almost given up on hearing from them at all.\n")
status, uploaded = call("POST", "/projects/" + pid + "/transcripts", form={
    "fields": {"participant_label": "P9"},
    "file": ("file", "p9_test.txt", sample)})
check("upload transcript", status == 200 and uploaded["participant_label"] == "P9", str(status))

status, detail = call("GET", "/projects/" + pid + "/transcripts/" + uploaded["id"])
check("transcript detail", status == 200 and "raw_text" in detail, str(status))

status, _ = call("DELETE", "/projects/" + pid + "/transcripts/" + uploaded["id"])
check("delete transcript", status == 200, str(status))

# exports
out_dir = os.path.dirname(os.path.abspath(__file__))
status, xlsx = call("GET", "/projects/" + pid + "/export/xlsx", raw=True)
ok = status == 200 and xlsx[:2] == b"PK"
if ok:
    with zipfile.ZipFile(io.BytesIO(xlsx)) as z:
        names = z.namelist()
        ok = "xl/workbook.xml" in names and z.testzip() is None
        open(os.path.join(out_dir, "export.xlsx"), "wb").write(xlsx)
check("export xlsx", ok, str(len(xlsx)) + " bytes")

status, docx = call("GET", "/projects/" + pid + "/export/docx", raw=True)
ok = status == 200 and docx[:2] == b"PK"
if ok:
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        ok = "word/document.xml" in z.namelist() and z.testzip() is None
        open(os.path.join(out_dir, "export.docx"), "wb").write(docx)
check("export docx", ok, str(len(docx)) + " bytes")

status, pdf = call("GET", "/projects/" + pid + "/export/pdf", raw=True)
ok = status == 200 and pdf[:5] == b"%PDF-" and pdf.rstrip().endswith(b"%%EOF")
if ok:
    open(os.path.join(out_dir, "export.pdf"), "wb").write(pdf)
check("export pdf", ok, str(len(pdf)) + " bytes, pages=" + str(pdf.count(b"/Type /Page ")))

status, usage = call("GET", "/usage")
check("usage summary", status == 200 and "logs" in usage, str(usage.get("total_calls")))

status, usage_xlsx = call("GET", "/usage/export/xlsx", raw=True)
check("usage export", status == 200 and usage_xlsx[:2] == b"PK", str(len(usage_xlsx)))

# authorisation
saved, TOKEN = TOKEN, None
status, _ = call("GET", "/projects")
check("unauthenticated blocked", status == 401, str(status))
TOKEN = saved

status, _ = call("GET", "/projects/does-not-exist")
check("missing project 404", status == 404, str(status))

for outcome, name, detail in results:
    print(outcome, "-", name, ("(" + detail + ")") if detail else "")
failures = [r for r in results if r[0] == "FAIL"]
print("\n%d/%d passed" % (len(results) - len(failures), len(results)))
sys.exit(1 if failures else 0)
