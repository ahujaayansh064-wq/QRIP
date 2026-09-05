"""QRIP server — JSON API under /api plus the static single-page frontend.

Run:  python backend/server.py [--port 8000] [--demo]
"""
import argparse
import json
import mimetypes
import os
import posixpath
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import api  # noqa: E402
import auth  # noqa: E402
import db  # noqa: E402

FRONTEND_DIR = os.path.join(db.BASE_DIR, "frontend")
API_PREFIX = "/api"


# --- multipart ------------------------------------------------------------

def parse_multipart(body: bytes, content_type: str):
    """Minimal multipart/form-data parser: returns (fields, files)."""
    fields, files = {}, {}
    marker = "boundary="
    if marker not in content_type:
        return fields, files
    boundary = content_type.split(marker, 1)[1].strip().strip('"')
    sep = b"--" + boundary.encode()
    for part in body.split(sep):
        part = part.strip(b"\r\n")
        if not part or part in (b"--", b"--\r\n"):
            continue
        if b"\r\n\r\n" not in part:
            continue
        head, data = part.split(b"\r\n\r\n", 1)
        if data.endswith(b"\r\n"):
            data = data[:-2]
        headers = head.decode("utf-8", "replace")
        disposition = ""
        for line in headers.split("\r\n"):
            if line.lower().startswith("content-disposition:"):
                disposition = line
        if 'name="' not in disposition:
            continue
        name = disposition.split('name="', 1)[1].split('"', 1)[0]
        if 'filename="' in disposition:
            filename = disposition.split('filename="', 1)[1].split('"', 1)[0]
            files[name] = (os.path.basename(filename), data)
        else:
            fields[name] = data.decode("utf-8", "replace")
    return fields, files


# Cross-origin support, for deployments that serve the frontend from a static
# host (Netlify, Pages, S3) and the API from somewhere that can run Python.
# Same-origin deployments need none of this and should leave it unset.
ALLOWED_ORIGINS = [origin.strip().rstrip("/") for origin
                   in os.environ.get("QRIP_ALLOWED_ORIGINS", "").split(",")
                   if origin.strip()]


def cors_headers(origin):
    if not ALLOWED_ORIGINS or not origin:
        return {}
    cleaned = origin.rstrip("/")
    if "*" in ALLOWED_ORIGINS:
        allow = "*"
    elif cleaned in ALLOWED_ORIGINS:
        allow = cleaned
    else:
        return {}
    return {
        "Access-Control-Allow-Origin": allow,
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
        "Access-Control-Allow-Methods": "GET, POST, PATCH, PUT, DELETE, OPTIONS",
        "Access-Control-Expose-Headers": "Content-Disposition",
        "Access-Control-Max-Age": "86400",
        "Vary": "Origin",
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "QRIP/1.0"
    protocol_version = "HTTP/1.1"

    # --- plumbing ---------------------------------------------------------

    def log_message(self, fmt, *args):
        sys.stderr.write("%s  %s\n" % (self.log_date_time_string(), fmt % args))

    def _send(self, status, body: bytes, content_type="application/json",
              extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in cors_headers(self.headers.get("Origin")).items():
            self.send_header(key, value)
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_OPTIONS(self):
        headers = cors_headers(self.headers.get("Origin"))
        self.send_response(204 if headers else 405)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _json(self, status, payload):
        self._send(status, json.dumps(payload, default=str).encode("utf-8"))

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return b""
        return self.rfile.read(length)

    # --- dispatch ---------------------------------------------------------

    def _handle(self, method):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path.startswith(API_PREFIX):
            return self._handle_api(method, path[len(API_PREFIX):] or "/", parsed.query)
        if method in ("GET", "HEAD"):
            return self._serve_static(path)
        return self._json(404, {"detail": "Not found."})

    def _handle_api(self, method, path, query):
        ctx = {"query": query, "user": None, "json": None, "form": None, "files": None}
        try:
            ctx["user"] = auth.user_from_header(self.headers.get("Authorization", ""))
            content_type = self.headers.get("Content-Type", "") or ""
            body = self._read_body() if method in ("POST", "PATCH", "PUT") else b""
            if body:
                if content_type.startswith("multipart/form-data"):
                    ctx["form"], ctx["files"] = parse_multipart(body, content_type)
                elif "json" in content_type or body[:1] in (b"{", b"["):
                    ctx["json"] = json.loads(body.decode("utf-8", "replace") or "{}")
            result = api.dispatch(method, path, ctx)
        except api.ApiError as exc:
            return self._json(exc.status, {"detail": exc.message})
        except json.JSONDecodeError:
            return self._json(400, {"detail": "Malformed JSON body."})
        except Exception as exc:
            traceback.print_exc()
            return self._json(500, {"detail": "Server error: " + str(exc)[:300]})

        if isinstance(result, api.FileResponse):
            return self._send(200, result.data, result.content_type, {
                "Content-Disposition": 'attachment; filename="' + result.filename + '"',
            })
        return self._json(200, result)

    # --- static -----------------------------------------------------------

    def _serve_static(self, path):
        rel = posixpath.normpath(path).lstrip("/")
        target = os.path.join(FRONTEND_DIR, *rel.split("/")) if rel else \
            os.path.join(FRONTEND_DIR, "index.html")
        if os.path.isdir(target):
            target = os.path.join(target, "index.html")
        if not os.path.abspath(target).startswith(os.path.abspath(FRONTEND_DIR)):
            return self._json(403, {"detail": "Forbidden."})
        if not os.path.isfile(target):
            # single-page app: unknown routes fall back to the shell
            target = os.path.join(FRONTEND_DIR, "index.html")
        content_type = mimetypes.guess_type(target)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in (
                "application/javascript", "application/json"):
            content_type += "; charset=utf-8"
        with open(target, "rb") as fh:
            data = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def do_GET(self):
        self._handle("GET")

    def do_HEAD(self):
        self._handle("HEAD")

    def do_POST(self):
        self._handle("POST")

    def do_PATCH(self):
        self._handle("PATCH")

    def do_PUT(self):
        self._handle("PUT")

    def do_DELETE(self):
        self._handle("DELETE")


def seed_demo():
    """Create a demo account and a project loaded with the sample transcripts."""
    email = "demo@qrip.local"
    user = db.q1("SELECT * FROM users WHERE email=?", (email,))
    if user is None:
        user = auth.register(email, "demo-password", "Demo Researcher")
        print("Created demo account:", email, "/ demo-password")
    project = db.q1("SELECT * FROM projects WHERE user_id=? AND name=?",
                    (user["id"], "Patient experience of referral delays"))
    if project is not None:
        print("Demo project already exists:", project["id"])
        return
    project_id = db.new_id()
    db.insert("projects", {
        "id": project_id, "user_id": user["id"],
        "name": "Patient experience of referral delays",
        "research_question": "How do patients experience and make sense of long waits "
                             "between referral and first appointment?",
        "methodology": "thematic",
        "description": "Six semi-structured interviews with patients referred to a "
                       "secondary care service in the last eighteen months.",
        "created_at": db.now(),
    })
    samples_dir = os.path.join(db.BASE_DIR, "samples")
    count = 0
    for filename in sorted(os.listdir(samples_dir)):
        if not filename.endswith(".txt"):
            continue
        with open(os.path.join(samples_dir, filename), encoding="utf-8") as fh:
            text = fh.read()
        label = filename.split("_")[0].upper()
        db.insert("transcripts", {
            "id": db.new_id(), "project_id": project_id, "filename": filename,
            "participant_label": label, "status": "uploaded", "error_message": None,
            "raw_text": text, "char_count": len(text), "created_at": db.now(),
        })
        count += 1
    db.audit(project_id, user["id"], "project.created", "project", project_id,
             {"seeded": True, "transcripts": count})
    print("Seeded demo project", project_id, "with", count, "transcripts.")


def main():
    # Managed hosts (Render, Railway, Fly, Heroku) inject $PORT and expect the
    # process to listen on every interface; locally we stay on loopback.
    platform_port = os.environ.get("PORT") or os.environ.get("QRIP_PORT")
    default_host = os.environ.get("QRIP_HOST") or (
        "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")

    parser = argparse.ArgumentParser(description="QRIP server")
    parser.add_argument("--port", type=int, default=int(platform_port or 8000))
    parser.add_argument("--host", default=default_host)
    parser.add_argument("--demo", action="store_true",
                        help="create the demo account and sample project, then serve")
    args = parser.parse_args()

    db.init()
    if args.demo:
        seed_demo()

    from analysis import llm
    engine = llm.engine_info()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print("QRIP running at http://" + args.host + ":" + str(args.port))
    print("Analysis engine:", engine["label"])
    print("Data directory:", db.DATA_DIR)
    if ALLOWED_ORIGINS:
        print("CORS allowed origins:", ", ".join(ALLOWED_ORIGINS))
    if not os.environ.get("QRIP_SECRET"):
        print("NOTE: QRIP_SECRET is not set. A key file is used instead, so on a host "
              "with an ephemeral disk every deploy signs users out. Set QRIP_SECRET "
              "in production.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
        server.shutdown()


if __name__ == "__main__":
    main()
