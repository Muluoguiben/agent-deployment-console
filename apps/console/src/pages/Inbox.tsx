import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Escalation } from "../api";

export default function Inbox() {
  const [items, setItems] = useState<Escalation[]>([]);
  const [view, setView] = useState<"open" | "resolved">("open");

  const refresh = () => {
    api.inbox(view).then(setItems).catch(() => {});
  };
  useEffect(refresh, [view]);

  async function resolve(id: string) {
    await api.resolve(id);
    refresh();
  }

  return (
    <>
      <h1>Inbox</h1>
      <p className="subtitle">
        Human handoffs. Every escalation arrives with the structured summary the escalation
        policy requires: symptom, context, what was ruled out, suspected cause, severity.
      </p>
      <div className="row" style={{ marginBottom: 14 }}>
        <button
          className={view === "open" ? "primary" : ""}
          onClick={() => setView("open")}
        >
          Open
        </button>
        <button
          className={view === "resolved" ? "primary" : ""}
          onClick={() => setView("resolved")}
        >
          Resolved
        </button>
      </div>
      {items.length === 0 && (
        <div className="card dim">No {view} escalations.</div>
      )}
      {items.map((item) => (
        <div className="card" key={item.id}>
          <div className="row">
            <span className={`badge ${item.severity === "S1" || item.severity === "S2" ? "bad" : "warn"}`}>
              {item.severity}
            </span>
            <span className="mono">{item.id}</span>
            <span className="dim">{item.account_id ?? "unknown account"}</span>
            <span className="dim mono">{item.created_at}</span>
            <span className="spacer" />
            <Link to={`/traces/${item.run_id}`}>trace</Link>
            {view === "open" && (
              <button className="primary" onClick={() => resolve(item.id)}>Resolve</button>
            )}
          </div>
          <table style={{ marginTop: 10 }}>
            <tbody>
              <tr><th style={{ width: 140 }}>symptom</th><td>{item.summary.symptom}</td></tr>
              <tr><th>docs consulted</th><td>{item.summary.docs_consulted}</td></tr>
              <tr><th>ruled out</th><td>{item.summary.ruled_out}</td></tr>
              <tr><th>suspected cause</th><td>{item.summary.suspected_cause}</td></tr>
            </tbody>
          </table>
        </div>
      ))}
    </>
  );
}
