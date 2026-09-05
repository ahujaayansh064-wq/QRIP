"""SQLite storage layer for QRIP.

Single-file database, stdlib only. Every table mirrors the shapes the API
returns, so the request handlers stay thin.
"""
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# QRIP_DATA_DIR lets a deployment point the database at a mounted persistent
# disk; without it the database sits beside the code and dies with the container.
DATA_DIR = os.environ.get("QRIP_DATA_DIR") or os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "qrip.db")

_local = threading.local()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex


def connect() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'researcher',
    created_at TEXT NOT NULL,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    research_question TEXT,
    methodology TEXT,
    description TEXT,
    similarity_threshold REAL NOT NULL DEFAULT 0.28,
    confidence_threshold REAL NOT NULL DEFAULT 0.55,
    min_supporting_quotations INTEGER NOT NULL DEFAULT 3,
    participant_frequency_threshold INTEGER NOT NULL DEFAULT 2,
    coding_granularity TEXT NOT NULL DEFAULT 'sentence',
    contradiction_sensitivity REAL NOT NULL DEFAULT 0.5,
    analysis_in_progress INTEGER NOT NULL DEFAULT 0,
    analysis_stage TEXT,
    analysis_progress REAL NOT NULL DEFAULT 0,
    last_analysis_error TEXT,
    last_analysis_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transcripts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    participant_label TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploaded',
    error_message TEXT,
    raw_text TEXT NOT NULL,
    char_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meaning_units (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    transcript_id TEXT NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL,
    turn_idx INTEGER NOT NULL DEFAULT 0,
    speaker TEXT,
    is_participant INTEGER NOT NULL DEFAULT 1,
    text TEXT NOT NULL,
    question_context TEXT
);

CREATE TABLE IF NOT EXISTS codes (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    transcript_id TEXT NOT NULL,
    meaning_unit_id TEXT NOT NULL,
    theme_id TEXT,
    label TEXT NOT NULL,
    literal_meaning TEXT,
    emotion TEXT,
    intent TEXT,
    valence REAL NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 0,
    alternative_interpretations TEXT NOT NULL DEFAULT '[]',
    is_negative_case INTEGER NOT NULL DEFAULT 0,
    quote_text TEXT NOT NULL,
    participant_label TEXT NOT NULL,
    terms TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS themes (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'candidate',
    confidence REAL NOT NULL DEFAULT 0,
    coverage REAL NOT NULL DEFAULT 0,
    participant_count INTEGER NOT NULL DEFAULT 0,
    alternative_interpretation TEXT,
    merged_from TEXT NOT NULL DEFAULT '[]',
    order_idx INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS contradictions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    theme_id TEXT,
    description TEXT NOT NULL,
    severity REAL NOT NULL DEFAULT 0,
    code_a_id TEXT,
    code_b_id TEXT
);

CREATE TABLE IF NOT EXISTS model_comparisons (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    theme_id TEXT NOT NULL,
    primary_model TEXT NOT NULL,
    secondary_model TEXT NOT NULL,
    agreement INTEGER NOT NULL DEFAULT 1,
    disagreement_notes TEXT
);

CREATE TABLE IF NOT EXISTS methodology_outputs (
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    methodology TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (project_id, methodology)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    user_id TEXT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    details TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usage_log (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    project_id TEXT,
    operation TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd REAL NOT NULL DEFAULT 0,
    success INTEGER NOT NULL DEFAULT 1,
    error_message TEXT,
    created_at TEXT NOT NULL
);

-- The CAQDAS layer: quotations, a codebook, groups, memos, typed links and
-- saved networks. Automatic coding and hand coding write to exactly the same
-- objects, which is what lets a researcher take over from the machine.

CREATE TABLE IF NOT EXISTS codebook (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#2B4570',
    definition TEXT,
    created_by TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL,
    order_idx INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS code_groups (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#6B6D76',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS code_group_members (
    group_id TEXT NOT NULL REFERENCES code_groups(id) ON DELETE CASCADE,
    code_id TEXT NOT NULL REFERENCES codebook(id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, code_id)
);

CREATE TABLE IF NOT EXISTS quotations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    text TEXT NOT NULL,
    name TEXT,
    comment TEXT,
    created_by TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memos (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'analytic',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memo_links (
    memo_id TEXT NOT NULL REFERENCES memos(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    PRIMARY KEY (memo_id, target_type, target_id)
);

CREATE TABLE IF NOT EXISTS links (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation TEXT NOT NULL DEFAULT 'is associated with',
    comment TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS networks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    layout TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Review intelligence: a job takes one or two businesses' reviews and produces
-- an executive report. Reviews are stored so a report can be re-run or audited.

CREATE TABLE IF NOT EXISTS review_jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    business_name TEXT NOT NULL,
    business_url TEXT,
    competitor_name TEXT,
    competitor_url TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    status TEXT NOT NULL DEFAULT 'queued',
    stage TEXT,
    progress REAL NOT NULL DEFAULT 0,
    error TEXT,
    report TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES review_jobs(id) ON DELETE CASCADE,
    side TEXT NOT NULL DEFAULT 'primary',
    reviewer TEXT,
    rating REAL,
    text TEXT NOT NULL,
    relative_time TEXT,
    published_at TEXT,
    months_ago REAL,
    owner_response TEXT,
    photo_count INTEGER NOT NULL DEFAULT 0,
    idx INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_reviews_job ON reviews(job_id);
CREATE INDEX IF NOT EXISTS idx_review_jobs_user ON review_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_codes_project ON codes(project_id);
CREATE INDEX IF NOT EXISTS idx_codes_theme ON codes(theme_id);
CREATE INDEX IF NOT EXISTS idx_units_project ON meaning_units(project_id);
CREATE INDEX IF NOT EXISTS idx_themes_project ON themes(project_id);
CREATE INDEX IF NOT EXISTS idx_audit_project ON audit_log(project_id);
CREATE INDEX IF NOT EXISTS idx_usage_user ON usage_log(user_id);
CREATE INDEX IF NOT EXISTS idx_quotations_doc ON quotations(document_id);
CREATE INDEX IF NOT EXISTS idx_quotations_project ON quotations(project_id);
CREATE INDEX IF NOT EXISTS idx_codebook_project ON codebook(project_id);
CREATE INDEX IF NOT EXISTS idx_links_project ON links(project_id);
"""

# Columns added after the first release; applied to existing databases on boot.
MIGRATIONS = [
    ("codes", "quotation_id", "TEXT"),
    ("codes", "code_id", "TEXT"),
    ("codes", "created_by", "TEXT NOT NULL DEFAULT 'auto'"),
    ("meaning_units", "char_start", "INTEGER NOT NULL DEFAULT 0"),
    ("meaning_units", "char_end", "INTEGER NOT NULL DEFAULT 0"),
    ("transcripts", "doc_group", "TEXT"),
    ("transcripts", "comment", "TEXT"),
    ("themes", "color", "TEXT NOT NULL DEFAULT '#2B4570'"),
]


def init() -> None:
    conn = connect()
    conn.executescript(SCHEMA)
    for table, column, spec in MIGRATIONS:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(" + table + ")")}
        if column not in columns:
            conn.execute("ALTER TABLE " + table + " ADD COLUMN " + column + " " + spec)
    conn.commit()


# --- small helpers -------------------------------------------------------

def q(sql: str, args=()) -> list:
    return connect().execute(sql, args).fetchall()


def q1(sql: str, args=()):
    return connect().execute(sql, args).fetchone()


def ex(sql: str, args=()):
    conn = connect()
    cur = conn.execute(sql, args)
    conn.commit()
    return cur


def insert(table: str, row: dict) -> dict:
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    ex("INSERT INTO " + table + " (" + cols + ") VALUES (" + marks + ")", tuple(row.values()))
    return row


def insert_many(table: str, rows: list) -> None:
    if not rows:
        return
    cols = list(rows[0])
    sql = ("INSERT INTO " + table + " (" + ", ".join(cols) + ") VALUES ("
           + ", ".join("?" for _ in cols) + ")")
    conn = connect()
    conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
    conn.commit()


def audit(project_id, user_id, action, entity_type, entity_id=None, details=None) -> None:
    insert("audit_log", {
        "id": new_id(),
        "project_id": project_id,
        "user_id": user_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": json.dumps(details or {}),
        "created_at": now(),
    })


def log_usage(user_id, project_id, operation, model, input_tokens, output_tokens,
              cost, success=True, error_message=None) -> None:
    insert("usage_log", {
        "id": new_id(),
        "user_id": user_id,
        "project_id": project_id,
        "operation": operation,
        "model": model,
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "total_tokens": int(input_tokens) + int(output_tokens),
        "estimated_cost_usd": round(float(cost), 6),
        "success": 1 if success else 0,
        "error_message": error_message,
        "created_at": now(),
    })
