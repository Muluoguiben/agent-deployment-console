from langchain_core.messages import AIMessage

from agent_service import llm, registry
from agent_service.evals.runner import evaluate_checks, load_cases, run_suite


def _tool_call(name, args, call_id="c1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def test_cases_file_is_well_formed():
    cases = load_cases()
    assert len(cases) >= 25
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "case ids must be unique"
    categories = {c["category"] for c in cases}
    assert {"known_issue", "hallucination_bait", "out_of_scope", "escalation"} <= categories
    for case in cases:
        assert case["message"]
        assert case.get("checks") or case.get("judge_rubric")


def test_evaluate_checks_logic():
    class Ctx:
        escalated = True
        escalation_severity = "S2"

    checks = {
        "tools_called_includes": ["search_kb"],
        "tools_not_called": ["create_ticket"],
        "escalated": True,
        "escalation_severity": "S2",
        "answer_must_mention": ["KI-005"],
        "answer_must_not_mention": ["new account"],
    }
    results = evaluate_checks(
        checks, "This is KI-005; we escalated it.", {"search_kb", "escalate_to_human"}, Ctx()
    )
    assert all(r["passed"] for r in results)

    bad = evaluate_checks(checks, "Just make a new account.", {"create_ticket"}, Ctx())
    failed = {r["check"] for r in bad if not r["passed"]}
    assert "tool_called:search_kb" in failed
    assert "tool_not_called:create_ticket" in failed
    assert "mentions:KI-005" in failed
    assert "omits:new account" in failed


def test_run_suite_gate_pass_and_fail(conn, monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_DB_PATH", str(tmp_path / "evals.db"))
    # scripted "good" agent for the ki002 case: searches, then answers with the right fix
    llm.SCRIPTS["eval-good"] = [
        _tool_call("search_kb", {"query": "consent spinner Germany"}),
        AIMessage(content="This matches KI-002: reset consent in Settings > Privacy."),
    ]
    v = registry.create_version(
        conn, label="eval-good", system_prompt="p", model="scripted:eval-good"
    )
    registry.deploy(conn, v)
    report = run_suite(conn, use_judge=False, case_ids=["ki002-consent-spinner"])
    assert report["total"] == 1
    assert report["passed"] == 1
    assert report["passed_gate"] is True
    # eval result links to a queryable trace
    row = conn.execute("SELECT * FROM eval_results").fetchone()
    steps = conn.execute(
        "SELECT COUNT(*) AS n FROM steps WHERE run_id=?", (row["trace_run_id"],)
    ).fetchone()["n"]
    assert steps > 0

    # scripted "bad" agent: answers without searching, invents a fix
    llm.SCRIPTS["eval-bad"] = [
        AIMessage(content="Just reinstall the app, that always fixes spinners."),
    ]
    v2 = registry.create_version(
        conn, label="eval-bad", system_prompt="p", model="scripted:eval-bad"
    )
    registry.deploy(conn, v2)
    report2 = run_suite(conn, use_judge=False, case_ids=["ki002-consent-spinner"])
    assert report2["passed"] == 0
    assert report2["passed_gate"] is False
    # both runs recorded for the console
    runs = conn.execute("SELECT COUNT(*) AS n FROM eval_runs").fetchone()["n"]
    assert runs == 2
