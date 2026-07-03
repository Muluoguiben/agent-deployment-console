import { useEffect, useState } from "react";
import { api, type Version } from "../api";

export default function Versions() {
  const [versions, setVersions] = useState<Version[]>([]);
  const [previousId, setPreviousId] = useState<number | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    label: "",
    model: "",
    system_prompt: "",
    eval_threshold: 0.85,
    retrieval_top_k: 4,
    notes: "",
  });

  const refresh = () =>
    api
      .versions()
      .then((data) => {
        setVersions(data.versions);
        setPreviousId(data.previous_version_id);
      })
      .catch(() => {});

  useEffect(() => {
    refresh();
  }, []);

  const act = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
      refresh();
    } catch (e) {
      setError(String(e));
    }
  };

  const live = versions.find((v) => v.live);

  async function createFromForm() {
    await act(async () => {
      const base = live;
      await api.createVersion({
        label: form.label || `v${versions.length + 1}`,
        model: form.model || base?.model,
        system_prompt: form.system_prompt || base?.system_prompt,
        judge_model: base?.judge_model,
        eval_threshold: form.eval_threshold,
        retrieval_top_k: form.retrieval_top_k,
        notes: form.notes,
      });
      setShowForm(false);
    });
  }

  return (
    <>
      <h1>Versions</h1>
      <p className="subtitle">
        The agent’s prompt, model, and knobs are a versioned artifact. Deploy flips a pointer;
        rollback flips it back — instantly, without touching code.
      </p>
      {error && <div className="error-banner">{error}</div>}
      <div className="card">
        <div className="row">
          <button className="primary" onClick={() => setShowForm(!showForm)}>
            {showForm ? "Cancel" : "New version"}
          </button>
          <button
            className="danger"
            disabled={previousId == null}
            onClick={() => act(api.rollback)}
            title={previousId != null ? `back to v${previousId}` : "no previous version"}
          >
            ⟲ Rollback{previousId != null ? ` to v${previousId}` : ""}
          </button>
          <span className="dim">
            live: {live ? `v${live.id} (${live.label})` : "—"}
          </span>
        </div>
        {showForm && (
          <div style={{ marginTop: 12 }}>
            <label>label</label>
            <input
              value={form.label}
              placeholder="e.g. v2-stricter-escalation"
              onChange={(e) => setForm({ ...form, label: e.target.value })}
            />
            <label>model (provider:model-id — blank inherits the live version)</label>
            <input
              value={form.model}
              placeholder={live?.model ?? "anthropic:claude-haiku-4-5"}
              onChange={(e) => setForm({ ...form, model: e.target.value })}
            />
            <label>system prompt (blank inherits the live version)</label>
            <textarea
              value={form.system_prompt}
              placeholder={live?.system_prompt.slice(0, 200) + "…"}
              onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
            />
            <div className="row" style={{ marginTop: 8 }}>
              <div>
                <label>eval threshold</label>
                <input
                  type="number" step="0.05" min="0" max="1" style={{ width: 110 }}
                  value={form.eval_threshold}
                  onChange={(e) =>
                    setForm({ ...form, eval_threshold: parseFloat(e.target.value) })}
                />
              </div>
              <div>
                <label>retrieval top-k</label>
                <input
                  type="number" min="1" max="10" style={{ width: 110 }}
                  value={form.retrieval_top_k}
                  onChange={(e) =>
                    setForm({ ...form, retrieval_top_k: parseInt(e.target.value, 10) })}
                />
              </div>
              <div style={{ flex: 1 }}>
                <label>notes</label>
                <input
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                />
              </div>
            </div>
            <div style={{ marginTop: 12 }}>
              <button className="primary" onClick={createFromForm}>Create version</button>
            </div>
          </div>
        )}
      </div>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th></th><th>v</th><th>label</th><th>model</th><th>threshold</th>
              <th>top-k</th><th>created</th><th>notes</th><th></th>
            </tr>
          </thead>
          <tbody>
            {versions.map((version) => (
              <tr key={version.id}>
                <td>{version.live && <span className="badge ok">live</span>}</td>
                <td className="mono">v{version.id}</td>
                <td>{version.label}</td>
                <td className="mono">{version.model}</td>
                <td className="dim">{(version.eval_threshold * 100).toFixed(0)}%</td>
                <td className="dim">{version.retrieval_top_k}</td>
                <td className="dim mono">{version.created_at}</td>
                <td className="dim truncate">{version.notes}</td>
                <td>
                  {!version.live && (
                    <button onClick={() => act(() => api.deploy(version.id))}>Deploy</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
