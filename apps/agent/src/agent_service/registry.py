"""Versioned agent configs and the live pointer. Deploy = flip pointer; rollback = flip back."""

import json
import os
import sqlite3
from dataclasses import dataclass

ALL_TOOLS = ["search_kb", "lookup_account", "create_ticket", "escalate_to_human"]

DEFAULT_SYSTEM_PROMPT = """\
You are the CabinCast support triage agent. CabinCast is a streaming app embedded in vehicle
infotainment head units. You handle playback, login, connectivity, regional availability, and
device compatibility issues reported by customers.

Rules:
- Ground every diagnosis in the knowledge base: use search_kb before proposing any fix, and cite
  the known-issue id (KI-xxx) when one applies. Never invent devices, features, fixes, or dates.
- Use lookup_account to get the customer's device/region context when an account id is given;
  if you need it and don't have it, ask for the account id.
- When you resolve an issue that maps to a known issue or defect, file it with create_ticket.
  Do NOT file tickets for questions answered as expected behavior — tickets record defects
  and applied changes, not explanations.
- Escalate with escalate_to_human when: nothing in the KB matches, a backend data change is
  required, the issue is under investigation, or the request is out of scope (billing, refunds,
  legal, privacy/data requests). Include the full structured handoff.
- For out-of-scope ACTION requests (refunds, billing changes, legal/privacy demands), file the
  escalation immediately — do not wait for the account id or more details first. Use "unknown"
  for missing context; the receiving team collects the rest. A verbal redirect without a filed
  escalation counts as silently dropping the request. One search_kb call to confirm the
  mandated severity is required first; it does not count as delaying the escalation.
- Purely informational questions the KB doesn't cover get an honest "I don't have information
  about that" — no escalation, no invented answer.
- Enabling a remote-config workaround flag documented in the KB (e.g. video.codec_fallback=h264)
  for an account is a triage action you perform yourself — state it as applied; it does not
  require escalation.
- Never advise disabling privacy features, using VPNs, creating a new account, or reinstalling
  the app unless the KB explicitly says so.
- Definition of done: every issue leaves resolved, or correctly classified and routed with full
  context. Never guess; never silently drop.\
"""

DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "anthropic:claude-haiku-4-5")
DEFAULT_JUDGE_MODEL = os.environ.get("DEFAULT_JUDGE_MODEL", DEFAULT_MODEL)


@dataclass
class VersionConfig:
    id: int
    label: str
    system_prompt: str
    model: str
    judge_model: str
    tools_enabled: list[str]
    retrieval_top_k: int
    eval_threshold: float
    notes: str = ""

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "VersionConfig":
        return cls(
            id=row["id"],
            label=row["label"],
            system_prompt=row["system_prompt"],
            model=row["model"],
            judge_model=row["judge_model"],
            tools_enabled=json.loads(row["tools_enabled"]),
            retrieval_top_k=row["retrieval_top_k"],
            eval_threshold=row["eval_threshold"],
            notes=row["notes"],
        )


def create_version(
    conn: sqlite3.Connection,
    label: str,
    system_prompt: str,
    model: str,
    judge_model: str | None = None,
    tools_enabled: list[str] | None = None,
    retrieval_top_k: int = 4,
    eval_threshold: float = 0.85,
    notes: str = "",
) -> int:
    cur = conn.execute(
        """INSERT INTO agent_versions
           (label, system_prompt, model, judge_model, tools_enabled,
            retrieval_top_k, eval_threshold, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            label,
            system_prompt,
            model,
            judge_model or model,
            json.dumps(tools_enabled or ALL_TOOLS),
            retrieval_top_k,
            eval_threshold,
            notes,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def _set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()


def _get_setting(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def deploy(conn: sqlite3.Connection, version_id: int) -> None:
    row = conn.execute("SELECT id FROM agent_versions WHERE id=?", (version_id,)).fetchone()
    if not row:
        raise ValueError(f"version {version_id} does not exist")
    current = _get_setting(conn, "live_version_id")
    if current is not None and int(current) != version_id:
        _set_setting(conn, "previous_version_id", current)
    _set_setting(conn, "live_version_id", str(version_id))


def rollback(conn: sqlite3.Connection) -> int:
    previous = _get_setting(conn, "previous_version_id")
    if previous is None:
        raise ValueError("no previous version to roll back to")
    deploy(conn, int(previous))
    return int(previous)


def live_version_id(conn: sqlite3.Connection) -> int:
    value = _get_setting(conn, "live_version_id")
    if value is None:
        raise RuntimeError("no live version configured")
    return int(value)


def previous_version_id(conn: sqlite3.Connection) -> int | None:
    value = _get_setting(conn, "previous_version_id")
    return int(value) if value is not None else None


def get_version(conn: sqlite3.Connection, version_id: int) -> VersionConfig:
    row = conn.execute("SELECT * FROM agent_versions WHERE id=?", (version_id,)).fetchone()
    if not row:
        raise ValueError(f"version {version_id} does not exist")
    return VersionConfig.from_row(row)


def get_live_version(conn: sqlite3.Connection) -> VersionConfig:
    return get_version(conn, live_version_id(conn))


def list_versions(conn: sqlite3.Connection) -> list[dict]:
    live = None
    try:
        live = live_version_id(conn)
    except RuntimeError:
        pass
    rows = conn.execute("SELECT * FROM agent_versions ORDER BY id DESC").fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["tools_enabled"] = json.loads(d["tools_enabled"])
        d["live"] = row["id"] == live
        out.append(d)
    return out


def ensure_seed_version(conn: sqlite3.Connection) -> None:
    """First boot: create version 1 and make it live."""
    row = conn.execute("SELECT COUNT(*) AS n FROM agent_versions").fetchone()
    if row["n"] == 0:
        vid = create_version(
            conn,
            label="v1-baseline",
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            model=DEFAULT_MODEL,
            judge_model=DEFAULT_JUDGE_MODEL,
            notes="Initial baseline configuration",
        )
        deploy(conn, vid)
