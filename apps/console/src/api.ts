// Typed client for the agent service API.

export interface Meta {
  milestone: string;
  live_version: { id: number; label: string; model: string };
  open_escalations: number;
  daily_tokens_used: number;
  daily_token_budget: number;
}

export interface Run {
  id: string;
  conversation_id: string | null;
  version_id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  latency_ms: number | null;
  input_tokens: number;
  output_tokens: number;
  user_message: string;
  final_text: string;
  source: string;
}

export interface Step {
  idx: number;
  kind: string;
  name: string;
  input_json: string;
  output_json: string;
  latency_ms: number | null;
}

export interface Version {
  id: number;
  created_at: string;
  label: string;
  system_prompt: string;
  model: string;
  judge_model: string;
  tools_enabled: string[];
  retrieval_top_k: number;
  eval_threshold: number;
  notes: string;
  live: boolean;
}

export interface EvalRun {
  id: string;
  version_id: number;
  model: string;
  started_at: string;
  finished_at: string | null;
  total: number;
  passed: number;
  pass_rate: number;
  threshold: number;
  passed_gate: number | null;
  status: string;
}

export interface EvalResult {
  case_id: string;
  category: string;
  passed: number;
  checks_json: string;
  judge_score: number | null;
  trace_run_id: string | null;
}

export interface Escalation {
  id: string;
  run_id: string;
  account_id: string | null;
  severity: string;
  status: string;
  created_at: string;
  resolved_at: string | null;
  summary: {
    symptom: string;
    account_context: string;
    docs_consulted: string;
    ruled_out: string;
    suspected_cause: string;
    severity: string;
  };
}

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(path);
  if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
  return resp.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const resp = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
  return resp.json();
}

export const api = {
  meta: () => get<Meta>("/api/meta"),
  runs: (source?: string) =>
    get<Run[]>(`/api/runs${source ? `?source=${source}` : ""}`),
  run: (id: string) => get<{ run: Run; steps: Step[] }>(`/api/runs/${id}`),
  versions: () =>
    get<{ versions: Version[]; previous_version_id: number | null }>("/api/versions"),
  createVersion: (body: Partial<Version>) => post<{ id: number }>("/api/versions", body),
  deploy: (id: number) => post<{ live_version_id: number }>(`/api/versions/${id}/deploy`),
  rollback: () => post<{ live_version_id: number }>("/api/rollback"),
  evalRuns: () => get<EvalRun[]>("/api/evals/runs"),
  evalRun: (id: string) =>
    get<{ run: EvalRun; results: EvalResult[] }>(`/api/evals/runs/${id}`),
  triggerEval: (model?: string) =>
    post<{ eval_run_id: string }>("/api/evals/run", { model: model || null, judge: true }),
  inbox: (status = "open") => get<Escalation[]>(`/api/inbox?status=${status}`),
  resolve: (id: string) => post<{ status: string }>(`/api/inbox/${id}/resolve`),
};

export interface ChatEvent {
  type: string;
  [key: string]: unknown;
}

// POST /api/chat and yield parsed SSE events.
export async function* streamChat(
  message: string,
  conversationId: string | null,
): AsyncGenerator<ChatEvent> {
  const resp = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
  if (!resp.ok || !resp.body) throw new Error(`${resp.status}: ${await resp.text()}`);
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.trim();
      if (line.startsWith("data: ")) {
        yield JSON.parse(line.slice(6)) as ChatEvent;
      }
    }
  }
}
