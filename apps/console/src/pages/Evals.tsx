import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type EvalResult, type EvalRun } from "../api";

function GateBadge({ run }: { run: EvalRun }) {
  if (run.status !== "done") return <span className="badge info">running…</span>;
  return run.passed_gate ? (
    <span className="badge ok">gate passed</span>
  ) : (
    <span className="badge bad">gate failed</span>
  );
}

function ResultRow({ result }: { result: EvalResult }) {
  const [open, setOpen] = useState(false);
  const checks: { check: string; passed: boolean; detail?: string }[] = JSON.parse(
    result.checks_json,
  );
  return (
    <>
      <tr className="clickable" onClick={() => setOpen(!open)}>
        <td>
          {result.passed ? (
            <span className="badge ok">pass</span>
          ) : (
            <span className="badge bad">fail</span>
          )}
        </td>
        <td className="mono">{result.case_id}</td>
        <td className="dim">{result.category}</td>
        <td className="dim">{result.judge_score != null ? `judge ${result.judge_score}/5` : "—"}</td>
        <td onClick={(e) => e.stopPropagation()}>
          {result.trace_run_id && <Link to={`/traces/${result.trace_run_id}`}>trace</Link>}
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={5}>
            <ul className="checks">
              {checks.map((check, i) => (
                <li key={i} className={check.passed ? "pass" : "fail"}>
                  {check.passed ? "✓" : "✗"} {check.check}
                  {check.detail ? `  (${check.detail})` : ""}
                </li>
              ))}
            </ul>
          </td>
        </tr>
      )}
    </>
  );
}

export default function Evals() {
  const { evalRunId } = useParams();
  const navigate = useNavigate();
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [detail, setDetail] = useState<{ run: EvalRun; results: EvalResult[] } | null>(null);
  const [modelOverride, setModelOverride] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    api.evalRuns().then(setRuns).catch(() => {});
    if (evalRunId) api.evalRun(evalRunId).then(setDetail).catch(() => setDetail(null));
    else setDetail(null);
  };

  useEffect(refresh, [evalRunId]);
  useEffect(() => {
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [evalRunId]);

  async function trigger() {
    setError(null);
    try {
      const { eval_run_id } = await api.triggerEval(modelOverride.trim() || undefined);
      navigate(`/evals/${eval_run_id}`);
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <>
      <h1>Evals</h1>
      <p className="subtitle">
        The release gate: 26 triage scenarios asserted against real traces. Deploys are blocked
        below the live version’s threshold — same suite that runs in CI.
      </p>
      {error && <div className="error-banner">{error}</div>}
      <div className="card">
        <div className="row">
          <input
            style={{ maxWidth: 340 }}
            placeholder="model override, e.g. openai:gpt-… (optional)"
            value={modelOverride}
            onChange={(e) => setModelOverride(e.target.value)}
          />
          <button className="primary" onClick={trigger}>Run eval suite</button>
          <span className="dim">Runs against the live config; override to compare providers.</span>
        </div>
      </div>

      {detail && (
        <div className="card">
          <div className="row">
            <h1 style={{ fontSize: 15 }}>
              {detail.run.id} <span className="dim mono">({detail.run.model})</span>
            </h1>
            <GateBadge run={detail.run} />
            <span className="dim">
              {detail.run.passed}/{detail.run.total} passed ·{" "}
              {(detail.run.pass_rate * 100).toFixed(0)}% vs threshold{" "}
              {(detail.run.threshold * 100).toFixed(0)}%
            </span>
            <span className="spacer" />
            <Link to="/evals">← all eval runs</Link>
          </div>
          <table style={{ marginTop: 10 }}>
            <thead>
              <tr><th></th><th>case</th><th>category</th><th>judge</th><th></th></tr>
            </thead>
            <tbody>
              {detail.results.map((result) => (
                <ResultRow key={result.case_id} result={result} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>run</th><th>model</th><th>result</th><th>gate</th><th>v</th><th>started</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id} className="clickable">
                <td className="mono"><Link to={`/evals/${run.id}`}>{run.id}</Link></td>
                <td className="mono">{run.model}</td>
                <td>
                  {run.status === "done"
                    ? `${run.passed}/${run.total} (${(run.pass_rate * 100).toFixed(0)}%)`
                    : "…"}
                </td>
                <td><GateBadge run={run} /></td>
                <td className="dim">v{run.version_id}</td>
                <td className="dim mono">{run.started_at}</td>
              </tr>
            ))}
            {runs.length === 0 && (
              <tr><td colSpan={6} className="dim">No eval runs yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
