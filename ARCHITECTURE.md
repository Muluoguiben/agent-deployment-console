# Architecture

One container, three layers: a React console, a FastAPI service hosting a LangGraph
agent, and a single SQLite file for everything operational. Deliberately boring
infrastructure so the agent-operations features (eval gating, versioned deploys,
traces, rollback) are the interesting part.

```
┌───────────────────────── Browser ─────────────────────────┐
│            Console — React 19 + TypeScript + Vite         │
│   Chat · Traces · Evals · Versions/Rollback · Inbox       │
└────────────────────────────┬──────────────────────────────┘
                             │ REST + SSE  (/api/*)
┌────────────────────────────▼──────────────────────────────┐
│              Agent service — FastAPI (Python 3.12)         │
│                                                            │
│  api/        routes: chat (SSE), runs, versions, evals,    │
│              inbox, healthz                                 │
│  agent/      LangGraph StateGraph + 4 tools                 │
│  retrieval/  KB chunking + BM25 index (embeddings later)    │
│  tracing/    step recorder (+ optional LangSmith emit)      │
│  registry/   versioned agent configs + live pointer         │
│  evals/      case runner + assertions + LLM judge           │
└────────────┬───────────────────────────┬───────────────────┘
             │                           │
      ┌──────▼──────┐             ┌──────▼────────────┐
      │   SQLite    │             │ LLM providers      │
      │ (one file,  │             │ Claude / OpenAI /  │
      │ Fly volume) │             │ Gemini / compatible │
      └─────────────┘             └───────────────────┘
```

## Frontend — Console

- **React 19 + TypeScript + Vite**, plain SPA. No meta-framework: the build output
  is static files served by FastAPI in production; in dev, Vite proxies `/api` to
  the Python service.
- **Five pages** (react-router): Chat, Traces, Evals, Versions, Inbox.
- **State**: `fetch` + hooks. No Redux/query library until a page actually needs it.
- **Chat streaming**: SSE consumed with `fetch` + `ReadableStream`; tool-call
  progress events render inline ("searching knowledge base…").

## Backend — Agent service

FastAPI app in `apps/agent/src/agent_service/`, organized by responsibility
(`api/`, `agent/`, `retrieval/`, `tracing/`, `registry/`, `evals/`, `db.py`).

API surface:

| Route | Purpose |
|---|---|
| `POST /api/chat` (SSE) | Send a message; stream agent events (text deltas, tool calls, final) |
| `GET /api/runs`, `GET /api/runs/{id}` | Trace list and step-level timeline |
| `GET /api/versions`, `POST /api/versions` | List / create agent config versions |
| `POST /api/versions/{id}/deploy`, `POST /api/rollback` | Flip the live pointer |
| `GET /api/evals/runs`, `POST /api/evals/run` | Eval history / trigger a run |
| `GET /api/inbox`, `POST /api/inbox/{id}/resolve` | Human-handoff queue |
| `GET /healthz`, `GET /api/meta` | Liveness, build/version info |

## Agent — LangGraph StateGraph

Hand-built `StateGraph` (not the prebuilt ReAct helper) so the control flow is
explicit and traceable:

```
        ┌────────────┐   tool_calls    ┌───────────┐
 START ─▶   agent     ├────────────────▶   tools    │
        │ (LLM + 4    ◀────────────────┤ (execute,  │
        │  bound      │   results      │  record)   │
        │  tools)     │                └───────────┘
        └──────┬──────┘
               │ no tool_calls · or escalated · or max_iterations(8)
               ▼
              END  (final answer, or structured handoff → Inbox)
```

- **State**: message history, account context, retrieved doc refs, escalation flag.
- **Four tools**: `search_kb` (retrieval over `data/kb/`), `lookup_account`
  (profiles from `data/customers.json`), `create_ticket` (writes a classified
  ticket row), `escalate_to_human` (ends the run with a structured handoff
  summary per `escalation-policy.md`, lands in the Inbox).
- **Hard iteration cap** (8): on hitting it the agent must escalate rather than
  loop — the same "never silently drop" rule the KB imposes on human triage.
- **Conversation memory**: message history persisted in the service's own
  `messages` table (one row per turn); the graph is invoked statelessly per
  turn with full history — one source of truth, trivially inspectable.
- **System prompt, model, tool availability, retrieval params** all come from the
  versioned agent config — nothing behavioral is hard-coded.

## Data — one SQLite file

Three kinds of "memory", deliberately kept distinct:

1. **Conversation state** — LangGraph checkpoints (managed by `SqliteSaver`).
2. **Knowledge** — the KB corpus in `data/kb/`, chunked by heading, indexed with
   **BM25** in v1. Chosen over embeddings first because it is deterministic
   (stable evals), dependency-free, and works offline; the planned upgrade to
   `sqlite-vec` + an embedding model is itself a demo: swap the retrieval
   backend, let the eval suite prove no regression.
3. **Operational data** — tables: `conversations`, `runs`, `steps`, `tickets`,
   `escalations`, `agent_versions`, `settings` (live-version pointer),
   `eval_runs`, `eval_results`. Single file on a Fly volume; zero ops.

## Versioning & rollback

An agent config version is a row: system prompt, model id, tool flags, retrieval
params, eval threshold. **Deploy** = point the `live` setting at a version;
**rollback** = point it back. Every run records the version that served it, so
traces are filterable by version. This is *config-level* rollback (instant,
demoable in the UI) — *code-level* rollback stays with git + Fly releases, gated
by CI. The two layers are separated on purpose, and the README says so.

## Evals

- Cases live in `evals/cases/*.yaml`: input messages, expected tool calls,
  expected escalation, expected KI reference, forbidden claims.
- Runner executes each case against the agent **in-process** with a seeded
  database, then asserts on the captured trace (deterministic checks) plus an
  optional **LLM-judge** score for answer quality.
- Output: JSON report + pass/fail exit code. CI runs the suite on every PR;
  the deploy job `needs` the eval job and a pass rate ≥ the threshold stored in
  the live config. Red evals block the ship — that is the core demo.

## Models — provider-agnostic by design

The agent is not bound to a single model vendor. The versioned config stores two
provider-prefixed model strings — `model` (the agent) and `judge_model` (the
eval grader) — instantiated at runtime through LangChain's `init_chat_model`:

```
anthropic:claude-haiku-4-5      openai:gpt-*      google_genai:gemini-*
```

Any provider with a LangChain integration (or an OpenAI-compatible endpoint)
works; which ones are usable is decided by which API keys are present in the
environment. Because the model string lives in the versioned config, switching
providers is a **deploy, not a code change** — and running the same eval set
against two providers produces a like-for-like comparison table, gated by the
same threshold.

Practical defaults: a stronger model while developing, a low-cost model for the
public live demo and the judge. The live demo is protected by a per-IP rate
limit and a daily token budget enforced in the service; **replay mode** ships
seeded traces so the console is fully browsable with no API key at all.

## Tracing

Every run writes a `runs` row and one `steps` row per graph-node execution:
node name, tool input/output, token usage (from response metadata), latency.
The console's trace viewer reads only these tables. When `LANGCHAIN_API_KEY` is
set, the same runs also emit to **LangSmith** — the custom viewer shows the
engineering; the LangSmith integration shows ecosystem fluency.

## Deployment

Single Docker image (console build baked in, served by FastAPI), one Fly.io
machine in `sin`, SQLite on a 1GB volume. CI: lint + tests + evals on PR;
deploy on `main` only when evals pass. Secrets: `ANTHROPIC_API_KEY`
(+ optional `LANGCHAIN_API_KEY`).
