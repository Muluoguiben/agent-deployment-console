"""Eval runner: executes every case against the agent in-process, asserts on the captured
trace, optionally scores answers with an LLM judge, and records the run for the console
and the CI gate."""

import json
import sqlite3
import uuid
from pathlib import Path

import yaml
from langchain_core.messages import HumanMessage

from .. import db, registry
from ..graph import build_graph
from ..retrieval import KBIndex
from ..tools import RunContext
from ..tracing import RunRecorder
from .judge import judge_answer

CASES_PATH = Path(__file__).parent / "cases.yaml"


def load_cases(case_ids: list[str] | None = None) -> list[dict]:
    cases = yaml.safe_load(CASES_PATH.read_text(encoding="utf-8"))
    if case_ids:
        wanted = set(case_ids)
        cases = [c for c in cases if c["id"] in wanted]
    return cases


def _tool_names(conn: sqlite3.Connection, run_id: str) -> set[str]:
    rows = conn.execute(
        "SELECT DISTINCT name FROM steps WHERE run_id=? AND kind='tool'", (run_id,)
    ).fetchall()
    return {r["name"] for r in rows}


def evaluate_checks(checks: dict, final_text: str, tools_used: set[str], ctx) -> list[dict]:
    results = []

    def add(name: str, passed: bool, detail: str = ""):
        results.append({"check": name, "passed": bool(passed), "detail": detail})

    text = final_text.lower()
    for tool in checks.get("tools_called_includes", []):
        add(f"tool_called:{tool}", tool in tools_used, f"used={sorted(tools_used)}")
    for tool in checks.get("tools_not_called", []):
        add(f"tool_not_called:{tool}", tool not in tools_used)
    if "escalated" in checks:
        add("escalated", ctx.escalated == checks["escalated"], f"actual={ctx.escalated}")
    if "escalation_severity" in checks:
        add(
            "escalation_severity",
            ctx.escalation_severity == checks["escalation_severity"],
            f"actual={ctx.escalation_severity}",
        )
    for phrase in checks.get("answer_must_mention", []):
        add(f"mentions:{phrase}", phrase.lower() in text)
    for phrase in checks.get("answer_must_not_mention", []):
        add(f"omits:{phrase}", phrase.lower() not in text)
    return results


def run_case(conn: sqlite3.Connection, config, case: dict, data_dir: Path, index: KBIndex,
             use_judge: bool) -> dict:
    recorder = RunRecorder(conn, config.id, None, case["message"], source="eval")
    ctx = RunContext(
        conn=conn, index=index, data_dir=data_dir,
        run_id=recorder.run_id, top_k=config.retrieval_top_k,
    )
    run = build_graph(config, ctx, recorder)
    final_text = ""
    for event in run([HumanMessage(content=case["message"])]):
        if event.type == "final":
            final_text = event.data.get("text", "")

    checks = evaluate_checks(
        case.get("checks", {}), final_text, _tool_names(conn, recorder.run_id), ctx
    )
    judge_score = None
    if use_judge and case.get("judge_rubric"):
        judge_score = judge_answer(
            config.judge_model, case["message"], final_text, case["judge_rubric"]
        )
        checks.append(
            {
                "check": "judge_score>=3",
                "passed": judge_score is None or judge_score >= 3,
                "detail": f"score={judge_score}",
            }
        )
    passed = all(c["passed"] for c in checks)
    return {
        "case_id": case["id"],
        "category": case["category"],
        "passed": passed,
        "checks": checks,
        "judge_score": judge_score,
        "trace_run_id": recorder.run_id,
    }


def run_suite(
    conn: sqlite3.Connection,
    eval_run_id: str | None = None,
    model_override: str | None = None,
    use_judge: bool = True,
    case_ids: list[str] | None = None,
    threshold_override: float | None = None,
) -> dict:
    config = registry.get_live_version(conn)
    if model_override:
        config.model = model_override
    threshold = threshold_override if threshold_override is not None else config.eval_threshold

    eval_run_id = eval_run_id or f"eval_{uuid.uuid4().hex[:10]}"
    conn.execute(
        "INSERT INTO eval_runs (id, version_id, model, threshold) VALUES (?, ?, ?, ?)",
        (eval_run_id, config.id, config.model, threshold),
    )
    conn.commit()

    data_dir = db.find_data_dir()
    index = KBIndex(data_dir / "kb")
    cases = load_cases(case_ids)
    results = []
    for case in cases:
        result = run_case(conn, config, case, data_dir, index, use_judge)
        results.append(result)
        conn.execute(
            """INSERT INTO eval_results
               (eval_run_id, case_id, category, passed, checks_json, judge_score, trace_run_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                eval_run_id,
                result["case_id"],
                result["category"],
                int(result["passed"]),
                json.dumps(result["checks"], ensure_ascii=False),
                result["judge_score"],
                result["trace_run_id"],
            ),
        )
        conn.commit()

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    pass_rate = passed / total if total else 0.0
    passed_gate = pass_rate >= threshold
    conn.execute(
        """UPDATE eval_runs SET finished_at=datetime('now'), total=?, passed=?, pass_rate=?,
           passed_gate=?, status='done' WHERE id=?""",
        (total, passed, pass_rate, int(passed_gate), eval_run_id),
    )
    conn.commit()
    return {
        "eval_run_id": eval_run_id,
        "model": config.model,
        "total": total,
        "passed": passed,
        "pass_rate": pass_rate,
        "threshold": threshold,
        "passed_gate": passed_gate,
        "results": results,
    }
