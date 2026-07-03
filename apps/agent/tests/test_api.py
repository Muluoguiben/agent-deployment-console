import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from agent_service import llm
from agent_service.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("CHAT_RATE_LIMIT_PER_HOUR", "1000")
    return TestClient(app)


def _sse_events(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: "):]))
    return events


def test_healthz(client):
    assert client.get("/healthz").json()["status"] == "ok"


def test_meta_reports_live_version(client):
    meta = client.get("/api/meta").json()
    assert meta["live_version"]["id"] == 1
    assert meta["daily_token_budget"] > 0


def test_version_lifecycle_via_api(client):
    created = client.post(
        "/api/versions",
        json={
            "label": "v2-test",
            "system_prompt": "prompt",
            "model": "scripted:none",
            "eval_threshold": 0.9,
        },
    ).json()
    v2 = created["id"]

    assert client.post(f"/api/versions/{v2}/deploy").json()["live_version_id"] == v2
    listing = client.get("/api/versions").json()
    live = [v for v in listing["versions"] if v["live"]]
    assert live[0]["id"] == v2

    assert client.post("/api/rollback").json()["live_version_id"] == 1
    assert client.post("/api/versions/999/deploy").status_code == 400


def test_chat_end_to_end_with_scripted_model(client):
    llm.SCRIPTS["chat-demo"] = [
        AIMessage(
            content="",
            tool_calls=[{"name": "search_kb", "args": {"query": "consent spinner"}, "id": "c1"}],
        ),
        AIMessage(content="This matches KI-002 — reset consent in Settings > Privacy."),
    ]
    v = client.post(
        "/api/versions",
        json={"label": "scripted", "system_prompt": "p", "model": "scripted:chat-demo"},
    ).json()["id"]
    client.post(f"/api/versions/{v}/deploy")

    resp = client.post("/api/chat", json={"message": "infinite spinner in Germany"})
    assert resp.status_code == 200
    events = _sse_events(resp.text)
    types = [e["type"] for e in events]
    assert "conversation" in types
    assert "tool_call" in types
    assert "tool_result" in types
    final = [e for e in events if e["type"] == "final"][0]
    assert "KI-002" in final["text"]

    # trace is queryable
    run = client.get(f"/api/runs/{final['run_id']}").json()
    assert run["run"]["status"] == "final"
    assert any(s["name"] == "search_kb" for s in run["steps"])

    # conversation history persisted; second turn sees it
    conversation_id = [e for e in events if e["type"] == "conversation"][0]["conversation_id"]
    runs = client.get("/api/runs").json()
    assert any(r["conversation_id"] == conversation_id for r in runs)


def test_inbox_resolve_flow(client):
    llm.SCRIPTS["esc-demo"] = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "escalate_to_human",
                    "args": {
                        "account_id": "ACCT-1010",
                        "severity": "S2",
                        "symptom": "billing dispute",
                        "docs_consulted": "escalation-policy.md",
                        "ruled_out": "product issue",
                        "suspected_cause": "out of triage scope",
                    },
                    "id": "c1",
                }
            ],
        ),
        AIMessage(content="I've escalated this to the billing team."),
    ]
    v = client.post(
        "/api/versions",
        json={"label": "esc", "system_prompt": "p", "model": "scripted:esc-demo"},
    ).json()["id"]
    client.post(f"/api/versions/{v}/deploy")
    client.post("/api/chat", json={"message": "I want a refund"})

    inbox = client.get("/api/inbox").json()
    assert len(inbox) == 1
    assert inbox[0]["summary"]["severity"] == "S2"

    client.post(f"/api/inbox/{inbox[0]['id']}/resolve")
    assert client.get("/api/inbox").json() == []
    assert len(client.get("/api/inbox", params={"status": "resolved"}).json()) == 1


def test_rate_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DB_PATH", str(tmp_path / "rl.db"))
    monkeypatch.setenv("CHAT_RATE_LIMIT_PER_HOUR", "1000")
    from agent_service.api import RateLimiter, rate_limiter

    tight = RateLimiter(max_per_hour=2)
    assert tight.allow("1.2.3.4") and tight.allow("1.2.3.4")
    assert not tight.allow("1.2.3.4")
    assert tight.allow("5.6.7.8")  # other IPs unaffected
    assert rate_limiter is not None
