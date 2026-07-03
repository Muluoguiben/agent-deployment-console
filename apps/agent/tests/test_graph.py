import json

from langchain_core.messages import AIMessage, HumanMessage

from agent_service import registry
from agent_service.graph import MAX_AGENT_TURNS, build_graph
from agent_service.llm import ScriptedChatModel
from agent_service.retrieval import KBIndex
from agent_service.tools import RunContext
from agent_service.tracing import RunRecorder


def _tool_call(name, args, call_id="c1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def _make(conn, data_dir, script):
    config = registry.get_live_version(conn)
    recorder = RunRecorder(conn, config.id, None, "test", source="eval")
    ctx = RunContext(
        conn=conn,
        index=KBIndex(data_dir / "kb"),
        data_dir=data_dir,
        run_id=recorder.run_id,
        top_k=config.retrieval_top_k,
    )
    run = build_graph(config, ctx, recorder, model=ScriptedChatModel(script=script))
    return run, recorder, ctx


def test_happy_path_tool_loop(conn, data_dir):
    script = [
        _tool_call("search_kb", {"query": "black screen webview"}),
        _tool_call("lookup_account", {"account_id": "ACCT-1002"}, "c2"),
        AIMessage(content="This matches KI-001; enable video.codec_fallback=h264."),
    ]
    run, recorder, ctx = _make(conn, data_dir, script)
    events = list(run([HumanMessage(content="black screen but audio plays, ACCT-1002")]))

    final = events[-1]
    assert final.type == "final"
    assert "KI-001" in final.data["text"]
    assert final.data["status"] == "final"
    # trace recorded: 3 llm steps + 2 tool steps
    steps = conn.execute(
        "SELECT kind, name FROM steps WHERE run_id=? ORDER BY idx", (recorder.run_id,)
    ).fetchall()
    kinds = [(s["kind"], s["name"]) for s in steps]
    assert ("tool", "search_kb") in kinds
    assert ("tool", "lookup_account") in kinds
    assert ctx.account_id == "ACCT-1002"


def test_escalation_marks_run(conn, data_dir):
    script = [
        _tool_call(
            "escalate_to_human",
            {
                "account_id": "ACCT-1007",
                "severity": "S2",
                "symptom": "region mismatch after import",
                "docs_consulted": "login-and-accounts.md",
                "ruled_out": "unsupported region",
                "suspected_cause": "KI-005 provisioning mismatch",
            },
        ),
        AIMessage(content="I've escalated this to our operations team."),
    ]
    run, recorder, ctx = _make(conn, data_dir, script)
    events = list(run([HumanMessage(content="can't log in after importing my car")]))

    assert events[-1].data["status"] == "escalated"
    esc = conn.execute("SELECT * FROM escalations WHERE run_id=?", (recorder.run_id,)).fetchone()
    assert esc["severity"] == "S2"
    summary = json.loads(esc["summary_json"])
    assert summary["suspected_cause"].startswith("KI-005")


def test_iteration_cap_forces_escalation(conn, data_dir):
    # model that always wants another search: hits the cap
    script = [_tool_call("search_kb", {"query": "loop"}, f"c{i}") for i in range(20)]
    run, recorder, ctx = _make(conn, data_dir, script)
    events = list(run([HumanMessage(content="mystery issue")]))

    final = events[-1]
    assert final.data["status"] == "max_iterations"
    assert ctx.escalated is True
    esc = conn.execute("SELECT * FROM escalations WHERE run_id=?", (recorder.run_id,)).fetchone()
    assert esc is not None
    llm_steps = conn.execute(
        "SELECT COUNT(*) AS n FROM steps WHERE run_id=? AND kind='llm'", (recorder.run_id,)
    ).fetchone()["n"]
    assert llm_steps <= MAX_AGENT_TURNS


def test_ticket_tool_writes_row(conn, data_dir):
    script = [
        _tool_call(
            "create_ticket",
            {
                "account_id": "ACCT-1002",
                "classification": "known-issue",
                "summary": "VP-4102 decode failure, workaround applied",
                "ki_ref": "KI-001",
                "severity": "S3",
            },
        ),
        AIMessage(content="Filed a ticket referencing KI-001."),
    ]
    run, recorder, _ = _make(conn, data_dir, script)
    list(run([HumanMessage(content="file it")]))
    ticket = conn.execute("SELECT * FROM tickets WHERE run_id=?", (recorder.run_id,)).fetchone()
    assert ticket["ki_ref"] == "KI-001"
