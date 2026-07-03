"""SQLite data layer: one file, everything operational."""

import os
import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    label TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    model TEXT NOT NULL,
    judge_model TEXT NOT NULL,
    tools_enabled TEXT NOT NULL,          -- JSON list of tool names
    retrieval_top_k INTEGER NOT NULL DEFAULT 4,
    eval_threshold REAL NOT NULL DEFAULT 0.85,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    account_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL,                   -- user | assistant
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id),
    version_id INTEGER REFERENCES agent_versions(id),
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',  -- running|final|escalated|max_iterations|error
    latency_ms INTEGER,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    user_message TEXT NOT NULL DEFAULT '',
    final_text TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'chat'   -- chat | eval | seed
);

CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    idx INTEGER NOT NULL,
    kind TEXT NOT NULL,                   -- llm | tool
    name TEXT NOT NULL,
    input_json TEXT NOT NULL DEFAULT '',
    output_json TEXT NOT NULL DEFAULT '',
    latency_ms INTEGER,
    started_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES runs(id),
    account_id TEXT,
    classification TEXT NOT NULL,
    ki_ref TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL DEFAULT 'S4',
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS escalations (
    id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES runs(id),
    account_id TEXT,
    severity TEXT NOT NULL DEFAULT 'S3',
    summary_json TEXT NOT NULL,           -- structured handoff per escalation-policy.md
    status TEXT NOT NULL DEFAULT 'open',  -- open | resolved
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS eval_runs (
    id TEXT PRIMARY KEY,
    version_id INTEGER REFERENCES agent_versions(id),
    model TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    total INTEGER DEFAULT 0,
    passed INTEGER DEFAULT 0,
    pass_rate REAL DEFAULT 0,
    threshold REAL NOT NULL,
    passed_gate INTEGER,                  -- 0/1, NULL while running
    status TEXT NOT NULL DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS eval_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    eval_run_id TEXT NOT NULL REFERENCES eval_runs(id),
    case_id TEXT NOT NULL,
    category TEXT NOT NULL,
    passed INTEGER NOT NULL,
    checks_json TEXT NOT NULL,
    judge_score REAL,
    trace_run_id TEXT REFERENCES runs(id)
);
"""


def find_data_dir() -> Path:
    """Locate the repo's data/ directory locally and inside the Docker image."""
    env = os.environ.get("AGENT_DATA_DIR")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in list(here.parents)[:6]:
        candidate = parent / "data"
        if (candidate / "kb").is_dir():
            return candidate
    raise FileNotFoundError("data/ directory with kb/ not found; set AGENT_DATA_DIR")


def db_path() -> Path:
    env = os.environ.get("AGENT_DB_PATH")
    return Path(env) if env else find_data_dir() / "console.db"


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.commit()


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]
