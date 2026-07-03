# Agent Deployment Console

> A production-style operations console for an LLM support-triage agent — versioned deploys, eval-gated CI, step-level traces, one-click rollback.

**Status: M0 — walking skeleton.** Deploy pipeline, CI, and the mock support domain land first; the agent and console are built on top. Roadmap below.

## Why this exists

Most agent demos stop at "the model answers questions." In production, the hard part is everything around the agent: knowing that a new prompt version didn't regress *before* it ships, tracing a bad answer back to the exact step that produced it, and rolling back fast when something breaks.

This project demonstrates that operational layer around a deliberately simple agent: a customer-support **triage agent** for a fictional in-car streaming app ("CabinCast"). The domain data is fictional; the operational patterns are drawn from real production delivery work on embedded automotive web apps.

## The agent

Given a customer-reported issue, the triage agent:

1. retrieves troubleshooting docs and known issues (RAG over [`data/kb/`](data/kb)),
2. looks up the account and device profile ([`data/customers.json`](data/customers.json)),
3. either resolves with a grounded answer and files a classified ticket,
4. or escalates to a human with a structured handoff summary when nothing matches.

The definition of done for triage: every issue leaves **resolved** or **correctly classified and routed with full context** — never a hallucinated fix, never silently dropped.

## Architecture (target)

```
apps/console  React + TypeScript        chat · trace viewer · eval dashboard · versions/rollback · handoff inbox
apps/agent    Python + FastAPI          LangGraph agent · 4 tools · trace capture · version registry
data/         mock support domain       KB docs (RAG corpus) · accounts/devices · known issues
CI            GitHub Actions            lint + tests now · eval-gated deploys in M2
```

## Roadmap

- [x] **M0 — walking skeleton**: monorepo, CI, Docker + Fly.io deploy, mock domain data
- [ ] **M1 — agent core**: LangGraph agent with 4 tools, trace capture, minimal chat UI
- [ ] **M2 — the console**: trace viewer, 25+ case eval set, eval-gated deploys, versioned agent configs with one-click rollback, human-handoff inbox
- [ ] **M3 — packaging**: walkthrough video, live-demo hardening (rate limits, replay mode)

## Development

```bash
# agent (Python 3.12)
cd apps/agent && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
make dev-agent      # FastAPI on :8080

# console (Node 22+)
cd apps/console && npm install
make dev-console    # Vite on :5173, proxies /api to :8080

make test && make lint
```

## Deploy

Single container: the Dockerfile builds the console and serves it from FastAPI.

```bash
fly launch --copy-config --no-deploy   # first time
fly deploy
```

CI deploys on `main` once the `FLY_API_TOKEN` secret is set (skips gracefully otherwise). From M2 onward, deploys are gated on the eval suite passing.

## License

MIT
