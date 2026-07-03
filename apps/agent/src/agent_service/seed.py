"""Demo seed: three scripted conversations so the console is browsable with no API key.

Runs are recorded with source='seed' — they are honest demo data (real graph, real tools,
real traces; only the LLM replies are scripted). Enable at startup with DEMO_SEED=1 or run
    python -m agent_service.seed
"""

import uuid

from langchain_core.messages import AIMessage, HumanMessage

from . import db, registry
from .graph import build_graph
from .llm import ScriptedChatModel
from .retrieval import KBIndex
from .tools import RunContext
from .tracing import RunRecorder


def _tc(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


SCENARIOS = [
    {
        "message": "My account is ACCT-1002. The video shows a black screen but audio keeps "
                   "playing on my Kestrel K3.",
        "script": [
            _tc("search_kb", {"query": "black screen audio plays no picture decode"}, "s1"),
            _tc("lookup_account", {"account_id": "ACCT-1002"}, "s2"),
            _tc(
                "create_ticket",
                {
                    "account_id": "ACCT-1002",
                    "classification": "known-issue",
                    "summary": "VP-4102 H.265 decode failure on WebView 93; "
                               "codec_fallback workaround applied",
                    "ki_ref": "KI-001",
                    "severity": "S3",
                },
                "s3",
            ),
            AIMessage(
                content="This matches known issue KI-001: your head unit runs WebView 93, and "
                "H.265 video can't be hardware-decoded below WebView 95 (error VP-4102). I've "
                "enabled the h264 codec fallback for your account and filed a ticket — playback "
                "should recover after an app restart. The permanent fix arrives with your OEM's "
                "WebView update, which your unit is already queued for."
            ),
        ],
    },
    {
        "message": "I imported my car from Japan to Singapore (ACCT-1007) and now CabinCast "
                   "says the service is not available in my region.",
        "script": [
            _tc("search_kb", {"query": "service not available region vehicle imported"}, "s1"),
            _tc("lookup_account", {"account_id": "ACCT-1007"}, "s2"),
            _tc(
                "escalate_to_human",
                {
                    "account_id": "ACCT-1007",
                    "severity": "S2",
                    "symptom": "Login blocked with region-unavailable after JP->SG import",
                    "docs_consulted": "login-and-accounts.md, regional-compliance-eu.md",
                    "ruled_out": "Genuinely unsupported region (SG is supported); "
                                 "account misconfiguration",
                    "suspected_cause": "KI-005: vehicle provisioning region (JP) does not "
                                       "match account region (SG); needs backend region reset",
                },
                "s3",
            ),
            AIMessage(
                content="Your account region is Singapore but the vehicle's provisioning record "
                "still says Japan — a known situation after imports (KI-005). Fixing it needs a "
                "backend region reset that only our operations team can do, so I've escalated "
                "this with severity S2 and the full context. They'll contact you once the reset "
                "is done; please don't create a new account in the meantime, as that would "
                "orphan your subscription."
            ),
        ],
    },
    {
        "message": "All 42 Northgate Logistics vehicles (ACCT-1011) got logged out at once "
                   "this morning.",
        "script": [
            _tc("search_kb", {"query": "fleet vehicles all logged out authorization"}, "s1"),
            _tc("lookup_account", {"account_id": "ACCT-1011"}, "s2"),
            AIMessage(
                content="A simultaneous logout across a whole fleet almost always means the "
                "fleet's channel authorization key expired — and your account notes confirm it "
                "expired on 2026-07-01 (known issue KI-007). Renewal is self-service: in the "
                "fleet admin portal go to Admin > Contracts > Renew. Vehicles re-authenticate "
                "within the hour. If they're still logged out 24 hours after renewal, contact "
                "us again and we'll escalate with severity S2."
            ),
        ],
    },
]


def seed(conn) -> int:
    """Insert the demo scenarios if not present; returns how many were created."""
    existing = conn.execute(
        "SELECT COUNT(*) AS n FROM runs WHERE source='seed'"
    ).fetchone()["n"]
    if existing:
        return 0

    config = registry.get_live_version(conn)
    data_dir = db.find_data_dir()
    index = KBIndex(data_dir / "kb")
    for scenario in SCENARIOS:
        conversation_id = f"conv_seed_{uuid.uuid4().hex[:8]}"
        conn.execute("INSERT INTO conversations (id) VALUES (?)", (conversation_id,))
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'user', ?)",
            (conversation_id, scenario["message"]),
        )
        recorder = RunRecorder(conn, config.id, conversation_id, scenario["message"],
                               source="seed")
        ctx = RunContext(conn=conn, index=index, data_dir=data_dir, run_id=recorder.run_id,
                         top_k=config.retrieval_top_k)
        run = build_graph(config, ctx, recorder,
                          model=ScriptedChatModel(script=list(scenario["script"])))
        final_text = ""
        for event in run([HumanMessage(content=scenario["message"])]):
            if event.type == "final":
                final_text = event.data.get("text", "")
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'assistant', ?)",
            (conversation_id, final_text),
        )
        conn.commit()
    return len(SCENARIOS)


def main() -> None:
    conn = db.connect()
    db.init_db(conn)
    registry.ensure_seed_version(conn)
    try:
        created = seed(conn)
        print(f"seeded {created} demo conversations" if created else "seed data already present")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
