import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Run, type Step } from "../api";

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "final" ? "ok" : status === "escalated" ? "warn" : status === "running" ? "info" : "bad";
  return <span className={`badge ${cls}`}>{status}</span>;
}

function pretty(json: string): string {
  try {
    return JSON.stringify(JSON.parse(json), null, 2);
  } catch {
    return json;
  }
}

function StepView({ step }: { step: Step }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`step ${step.kind}`}>
      <div className="head">
        <span className="name">{step.kind === "tool" ? "⚙" : "◆"} {step.name}</span>
        <span className="dim mono">{step.latency_ms != null ? `${step.latency_ms}ms` : ""}</span>
        <button onClick={() => setOpen(!open)}>{open ? "hide I/O" : "show I/O"}</button>
      </div>
      {open && (
        <>
          <div className="dim mono">input</div>
          <pre>{pretty(step.input_json)}</pre>
          <div className="dim mono">output</div>
          <pre>{pretty(step.output_json)}</pre>
        </>
      )}
    </div>
  );
}

export default function Traces() {
  const { runId } = useParams();
  const [runs, setRuns] = useState<Run[]>([]);
  const [detail, setDetail] = useState<{ run: Run; steps: Step[] } | null>(null);

  useEffect(() => {
    api.runs().then(setRuns).catch(() => {});
  }, [runId]);

  useEffect(() => {
    if (runId) api.run(runId).then(setDetail).catch(() => setDetail(null));
    else setDetail(null);
  }, [runId]);

  if (detail) {
    const { run, steps } = detail;
    return (
      <>
        <h1>
          Trace <span className="mono">{run.id}</span>
        </h1>
        <p className="subtitle">
          <Link to="/traces">← all runs</Link>
        </p>
        <div className="card">
          <div className="row">
            <StatusBadge status={run.status} />
            <span className="badge neutral">v{run.version_id}</span>
            <span className="badge neutral">{run.source}</span>
            <span className="dim">
              {run.latency_ms != null ? `${(run.latency_ms / 1000).toFixed(1)}s` : ""} ·{" "}
              {run.input_tokens + run.output_tokens} tokens
            </span>
          </div>
          <p style={{ marginTop: 10 }}>
            <b>User:</b> {run.user_message}
          </p>
          <p style={{ marginTop: 6 }}>
            <b>Final:</b> {run.final_text || <span className="dim">(none)</span>}
          </p>
        </div>
        <div className="card">
          <h1 style={{ fontSize: 15, marginBottom: 10 }}>Steps ({steps.length})</h1>
          {steps.map((step) => (
            <StepView key={step.idx} step={step} />
          ))}
        </div>
      </>
    );
  }

  return (
    <>
      <h1>Traces</h1>
      <p className="subtitle">
        Every agent run, step by step — the on-call view for “why did it answer that?”
      </p>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>run</th>
              <th>status</th>
              <th>source</th>
              <th>v</th>
              <th>message</th>
              <th>latency</th>
              <th>tokens</th>
              <th>started</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id} className="clickable">
                <td className="mono">
                  <Link to={`/traces/${run.id}`}>{run.id.slice(0, 12)}</Link>
                </td>
                <td><StatusBadge status={run.status} /></td>
                <td className="dim">{run.source}</td>
                <td className="dim">v{run.version_id}</td>
                <td className="truncate">{run.user_message}</td>
                <td className="dim">
                  {run.latency_ms != null ? `${(run.latency_ms / 1000).toFixed(1)}s` : "—"}
                </td>
                <td className="dim">{run.input_tokens + run.output_tokens}</td>
                <td className="dim mono">{run.started_at}</td>
              </tr>
            ))}
            {runs.length === 0 && (
              <tr>
                <td colSpan={8} className="dim">No runs yet — send a chat message first.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
