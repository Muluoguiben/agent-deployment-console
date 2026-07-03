import { useEffect, useState } from "react";

type Meta = { milestone: string; agent: string };

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/meta")
      .then((r) => r.json())
      .then(setMeta)
      .catch((e: unknown) => setError(String(e)));
  }, []);

  return (
    <main
      style={{
        fontFamily: "system-ui, sans-serif",
        maxWidth: 640,
        margin: "4rem auto",
        padding: "0 1rem",
        lineHeight: 1.5,
      }}
    >
      <h1>Agent Deployment Console</h1>
      <p>
        Production-style operations console for an LLM triage agent — versioned deploys, eval-gated
        CI, step-level traces, one-click rollback.
      </p>
      {meta ? (
        <p>
          API: <strong>up</strong> · milestone <strong>{meta.milestone}</strong> · agent:{" "}
          {meta.agent}
        </p>
      ) : error ? (
        <p>API unreachable: {error}</p>
      ) : (
        <p>Checking API…</p>
      )}
    </main>
  );
}
