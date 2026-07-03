"""The agent's four tools, built per-run around a RunContext.

search_kb        read-only retrieval (RAG)
lookup_account   structured data lookup
create_ticket    write action
escalate_to_human human handoff — ends the run
"""

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.tools import BaseTool, tool

from .retrieval import KBIndex


@dataclass
class RunContext:
    conn: sqlite3.Connection
    index: KBIndex
    data_dir: Path
    run_id: str
    top_k: int = 4
    account_id: str | None = None
    escalated: bool = False
    escalation_severity: str | None = None
    _customers: dict | None = field(default=None, repr=False)

    def customers(self) -> dict[str, dict]:
        if self._customers is None:
            raw = json.loads((self.data_dir / "customers.json").read_text(encoding="utf-8"))
            self._customers = {c["account_id"]: c for c in raw}
        return self._customers


def build_tools(ctx: RunContext, enabled: list[str]) -> list[BaseTool]:
    @tool
    def search_kb(query: str) -> str:
        """Search the CabinCast support knowledge base (troubleshooting guides, compliance
        rules, device compatibility, known-issues registry). Returns the most relevant
        sections. Always search before proposing a fix."""
        results = ctx.index.search(query, top_k=ctx.top_k)
        if not results:
            return "No knowledge-base sections matched this query."
        return "\n\n---\n\n".join(chunk.render() for chunk, _ in results)

    @tool
    def lookup_account(account_id: str) -> str:
        """Look up a customer account/device profile by account id (format ACCT-xxxx).
        Returns OEM, vehicle, head unit, OS/WebView versions, app version, region, plan,
        account status, and notes."""
        profile = ctx.customers().get(account_id.strip().upper())
        if profile is None:
            return (
                f"No account found with id {account_id!r}. Ask the customer to confirm their "
                "account id (format ACCT-xxxx). Do not guess account details."
            )
        ctx.account_id = profile["account_id"]
        return json.dumps(profile, ensure_ascii=False)

    @tool
    def create_ticket(
        account_id: str, classification: str, summary: str, ki_ref: str = "", severity: str = "S4"
    ) -> str:
        """File a classified support ticket once the issue is diagnosed. classification is a
        short label (e.g. 'known-issue', 'user-education', 'config-change'); ki_ref is the
        known-issue id (KI-xxx) when one applies; severity is S1-S4."""
        ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
        ctx.conn.execute(
            """INSERT INTO tickets (id, run_id, account_id, classification, ki_ref, severity,
               summary) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (ticket_id, ctx.run_id, account_id, classification, ki_ref, severity, summary),
        )
        ctx.conn.commit()
        return f"Ticket {ticket_id} created ({classification}, {severity}, ki_ref={ki_ref or '-'})."

    @tool
    def escalate_to_human(
        account_id: str,
        severity: str,
        symptom: str,
        docs_consulted: str,
        ruled_out: str,
        suspected_cause: str,
    ) -> str:
        """Escalate to a human agent with a structured handoff. Required when: no KB match,
        backend data change needed (e.g. region reset), issue under investigation, or the
        request is out of triage scope (billing, refunds, legal, privacy/data requests).
        severity is S1-S4 per escalation policy."""
        summary = {
            "symptom": symptom,
            "account_context": account_id,
            "docs_consulted": docs_consulted,
            "ruled_out": ruled_out,
            "suspected_cause": suspected_cause,
            "severity": severity,
        }
        esc_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"
        ctx.conn.execute(
            """INSERT INTO escalations (id, run_id, account_id, severity, summary_json)
               VALUES (?, ?, ?, ?, ?)""",
            (esc_id, ctx.run_id, account_id, severity, json.dumps(summary, ensure_ascii=False)),
        )
        ctx.conn.commit()
        ctx.escalated = True
        ctx.escalation_severity = severity
        return (
            f"Escalation {esc_id} filed with severity {severity}. A human agent will take over; "
            "tell the customer what happens next, then end the conversation politely."
        )

    by_name = {
        "search_kb": search_kb,
        "lookup_account": lookup_account,
        "create_ticket": create_ticket,
        "escalate_to_human": escalate_to_human,
    }
    return [by_name[name] for name in enabled if name in by_name]


def force_escalation(ctx: RunContext, reason: str) -> str:
    """Auto-escalate when the agent hits its iteration cap — never silently drop."""
    esc_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"
    summary = {
        "symptom": reason,
        "account_context": ctx.account_id or "unknown",
        "docs_consulted": "n/a (auto-escalation)",
        "ruled_out": "n/a",
        "suspected_cause": "agent hit iteration cap without reaching a grounded resolution",
        "severity": "S3",
    }
    ctx.conn.execute(
        """INSERT INTO escalations (id, run_id, account_id, severity, summary_json)
           VALUES (?, ?, ?, ?, ?)""",
        (esc_id, ctx.run_id, ctx.account_id, "S3", json.dumps(summary, ensure_ascii=False)),
    )
    ctx.conn.commit()
    ctx.escalated = True
    ctx.escalation_severity = "S3"
    return esc_id
