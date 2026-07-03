"""REST + SSE API for the console."""

import json
import sqlite3
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from . import db, registry
from .graph import build_graph
from .guards import RateLimiter, budget_exceeded, daily_budget, daily_tokens_used
from .retrieval import get_index
from .tools import RunContext
from .tracing import RunRecorder

router = APIRouter(prefix="/api")
rate_limiter = RateLimiter()


def _conn() -> sqlite3.Connection:
    conn = db.connect()
    db.init_db(conn)
    registry.ensure_seed_version(conn)
    return conn


def _data_dir() -> Path:
    return db.find_data_dir()


# ---------------------------------------------------------------- chat

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


def _load_history(conn: sqlite3.Connection, conversation_id: str):
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id",
        (conversation_id,),
    ).fetchall()
    history = []
    for row in rows:
        cls = HumanMessage if row["role"] == "user" else AIMessage
        history.append(cls(content=row["content"]))
    return history


@router.post("/chat")
def chat(body: ChatRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(ip):
        raise HTTPException(429, "Rate limit exceeded for this demo — try again later.")

    def stream():
        conn = _conn()
        try:
            if budget_exceeded(conn):
                yield _sse({"type": "error", "message": "Daily demo token budget exhausted."})
                return
            conversation_id = body.conversation_id or f"conv_{uuid.uuid4().hex[:10]}"
            conn.execute(
                "INSERT OR IGNORE INTO conversations (id) VALUES (?)", (conversation_id,)
            )
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'user', ?)",
                (conversation_id, body.message),
            )
            conn.commit()
            yield _sse({"type": "conversation", "conversation_id": conversation_id})

            config = registry.get_live_version(conn)
            recorder = RunRecorder(conn, config.id, conversation_id, body.message)
            ctx = RunContext(
                conn=conn,
                index=get_index(_data_dir() / "kb"),
                data_dir=_data_dir(),
                run_id=recorder.run_id,
                top_k=config.retrieval_top_k,
            )
            run = build_graph(config, ctx, recorder)
            history = _load_history(conn, conversation_id)
            final_text = ""
            for event in run(history):
                if event.type == "final":
                    final_text = event.data.get("text", "")
                yield _sse({"type": event.type, **event.data})
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'assistant', ?)",
                (conversation_id, final_text),
            )
            conn.commit()
        except Exception as exc:
            yield _sse({"type": "error", "message": str(exc)})
        finally:
            conn.close()

    return StreamingResponse(stream(), media_type="text/event-stream")


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------- traces

@router.get("/runs")
def list_runs(limit: int = 50, source: str | None = None):
    conn = _conn()
    try:
        query = "SELECT * FROM runs"
        params: list = []
        if source:
            query += " WHERE source=?"
            params.append(source)
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)
        return db.rows_to_dicts(conn.execute(query, params).fetchall())
    finally:
        conn.close()


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    conn = _conn()
    try:
        run = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not run:
            raise HTTPException(404, "run not found")
        steps = conn.execute(
            "SELECT * FROM steps WHERE run_id=? ORDER BY idx", (run_id,)
        ).fetchall()
        return {"run": dict(run), "steps": db.rows_to_dicts(steps)}
    finally:
        conn.close()


# ---------------------------------------------------------------- versions

class VersionCreate(BaseModel):
    label: str
    system_prompt: str
    model: str
    judge_model: str | None = None
    tools_enabled: list[str] | None = None
    retrieval_top_k: int = 4
    eval_threshold: float = 0.85
    notes: str = ""


@router.get("/versions")
def versions():
    conn = _conn()
    try:
        return {
            "versions": registry.list_versions(conn),
            "previous_version_id": registry.previous_version_id(conn),
        }
    finally:
        conn.close()


@router.post("/versions")
def create_version(body: VersionCreate):
    conn = _conn()
    try:
        vid = registry.create_version(conn, **body.model_dump())
        return {"id": vid}
    finally:
        conn.close()


@router.post("/versions/{version_id}/deploy")
def deploy_version(version_id: int):
    conn = _conn()
    try:
        registry.deploy(conn, version_id)
        return {"live_version_id": version_id}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        conn.close()


@router.post("/rollback")
def rollback():
    conn = _conn()
    try:
        vid = registry.rollback(conn)
        return {"live_version_id": vid}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        conn.close()


# ---------------------------------------------------------------- evals

class EvalTrigger(BaseModel):
    model: str | None = None      # override the live config's model for comparison runs
    judge: bool = True


@router.get("/evals/runs")
def eval_runs(limit: int = 20):
    conn = _conn()
    try:
        return db.rows_to_dicts(
            conn.execute(
                "SELECT * FROM eval_runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        )
    finally:
        conn.close()


@router.get("/evals/runs/{eval_run_id}")
def eval_run_detail(eval_run_id: str):
    conn = _conn()
    try:
        run = conn.execute("SELECT * FROM eval_runs WHERE id=?", (eval_run_id,)).fetchone()
        if not run:
            raise HTTPException(404, "eval run not found")
        results = conn.execute(
            "SELECT * FROM eval_results WHERE eval_run_id=? ORDER BY case_id", (eval_run_id,)
        ).fetchall()
        return {"run": dict(run), "results": db.rows_to_dicts(results)}
    finally:
        conn.close()


@router.post("/evals/run")
def trigger_eval(body: EvalTrigger):
    from .evals.runner import run_suite  # late import: keeps API import cheap

    conn = _conn()
    try:
        config = registry.get_live_version(conn)
    finally:
        conn.close()
    eval_run_id = f"eval_{uuid.uuid4().hex[:10]}"

    def work():
        worker_conn = _conn()
        try:
            run_suite(
                worker_conn,
                eval_run_id=eval_run_id,
                model_override=body.model,
                use_judge=body.judge,
            )
        finally:
            worker_conn.close()

    threading.Thread(target=work, daemon=True).start()
    return {"eval_run_id": eval_run_id, "model": body.model or config.model}


# ---------------------------------------------------------------- inbox

@router.get("/inbox")
def inbox(status: str = "open"):
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM escalations WHERE status=? ORDER BY created_at DESC", (status,)
        ).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            d["summary"] = json.loads(d.pop("summary_json"))
            out.append(d)
        return out
    finally:
        conn.close()


@router.post("/inbox/{escalation_id}/resolve")
def resolve_escalation(escalation_id: str):
    conn = _conn()
    try:
        cur = conn.execute(
            "UPDATE escalations SET status='resolved', resolved_at=datetime('now') WHERE id=?",
            (escalation_id,),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, "escalation not found")
        return {"status": "resolved"}
    finally:
        conn.close()


# ---------------------------------------------------------------- meta

@router.get("/meta")
def meta():
    conn = _conn()
    try:
        config = registry.get_live_version(conn)
        open_escalations = conn.execute(
            "SELECT COUNT(*) AS n FROM escalations WHERE status='open'"
        ).fetchone()["n"]
        return {
            "milestone": "M2",
            "live_version": {"id": config.id, "label": config.label, "model": config.model},
            "open_escalations": open_escalations,
            "daily_tokens_used": daily_tokens_used(conn),
            "daily_token_budget": daily_budget(),
        }
    finally:
        conn.close()
