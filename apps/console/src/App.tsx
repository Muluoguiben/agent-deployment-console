import { useEffect, useState } from "react";
import { HashRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";
import { api, type Meta } from "./api";
import Chat from "./pages/Chat";
import Evals from "./pages/Evals";
import Inbox from "./pages/Inbox";
import Traces from "./pages/Traces";
import Versions from "./pages/Versions";

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);

  useEffect(() => {
    const load = () => api.meta().then(setMeta).catch(() => setMeta(null));
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  return (
    <HashRouter>
      <div className="layout">
        <nav className="sidebar">
          <div className="brand">
            Agent Deployment Console
            <small>CabinCast triage agent</small>
          </div>
          <NavLink to="/chat">Chat</NavLink>
          <NavLink to="/traces">Traces</NavLink>
          <NavLink to="/evals">Evals</NavLink>
          <NavLink to="/versions">Versions</NavLink>
          <NavLink to="/inbox">
            Inbox{meta && meta.open_escalations > 0 ? ` (${meta.open_escalations})` : ""}
          </NavLink>
          <div className="foot">
            {meta ? (
              <>
                live: <code>v{meta.live_version.id} · {meta.live_version.label}</code>
                <br />
                model: <code>{meta.live_version.model}</code>
                <br />
                tokens today: <code>{meta.daily_tokens_used.toLocaleString()}</code>
              </>
            ) : (
              "API unreachable"
            )}
          </div>
        </nav>
        <main className="content">
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/traces" element={<Traces />} />
            <Route path="/traces/:runId" element={<Traces />} />
            <Route path="/evals" element={<Evals />} />
            <Route path="/evals/:evalRunId" element={<Evals />} />
            <Route path="/versions" element={<Versions />} />
            <Route path="/inbox" element={<Inbox />} />
          </Routes>
        </main>
      </div>
    </HashRouter>
  );
}
