from agent_service.seed import seed


def test_seed_creates_browsable_demo_data(conn):
    created = seed(conn)
    assert created == 3

    runs = conn.execute("SELECT * FROM runs WHERE source='seed'").fetchall()
    assert len(runs) == 3
    statuses = {r["status"] for r in runs}
    assert "final" in statuses and "escalated" in statuses

    # every seed run has a real step-level trace
    for run in runs:
        steps = conn.execute(
            "SELECT COUNT(*) AS n FROM steps WHERE run_id=?", (run["id"],)
        ).fetchone()["n"]
        assert steps >= 2

    # the escalation scenario landed in the inbox with severity S2
    esc = conn.execute("SELECT * FROM escalations WHERE status='open'").fetchall()
    assert len(esc) == 1
    assert esc[0]["severity"] == "S2"

    # ticket scenario filed against KI-001
    ticket = conn.execute("SELECT * FROM tickets").fetchone()
    assert ticket["ki_ref"] == "KI-001"

    # idempotent
    assert seed(conn) == 0
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM runs WHERE source='seed'"
    ).fetchone()["n"] == 3
