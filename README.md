# Agent Deployment Console

> A production-style operations console for an LLM support-triage agent — versioned deploys, eval-gated CI, step-level traces, one-click rollback.

**Status: M2 — feature-complete core.** The agent, the eval gate, versioned deploys with rollback, step-level traces, and the human-handoff inbox are all working; remaining work is packaging (walkthrough video, live-demo URL). Roadmap below.

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

## What's inside

- **The agent** — a hand-built LangGraph `StateGraph` with four tools (`search_kb`,
  `lookup_account`, `create_ticket`, `escalate_to_human`) and a hard 8-turn iteration cap
  that forces an escalation instead of looping — the same "never silently drop" rule the
  KB imposes on human triage.
- **Provider-agnostic models** — the model is a provider-prefixed string
  (`anthropic:…`, `openai:…`, `google_genai:…`) stored in the **versioned agent config**,
  so switching providers is a deploy, not a code change.
- **Eval gate** — 26 scenario cases (known issues, hallucination bait, out-of-scope,
  escalations, tool failures) asserted against real captured traces plus an optional
  LLM judge. `python -m agent_service.evals` exits nonzero below the threshold, and the
  deploy workflow requires it.
- **Versions & rollback** — prompt/model/knobs are rows in a registry; deploy flips the
  live pointer, rollback flips it back, every trace records which version served it.
- **Traces** — every run stores a step-level timeline (LLM calls, tool I/O, latency,
  tokens) the console renders; eval failures link straight to their trace.
- **Inbox** — escalations arrive with the structured handoff the escalation policy
  requires: symptom, context, ruled-out causes, suspected cause, severity.
- **Demo mode** — `DEMO_SEED=1` seeds three honest scripted conversations (real graph,
  real tools, real traces; only the LLM replies are scripted, marked `source=seed`) so
  the console is fully browsable with no API key.

## Failure cases the eval suite caught

The first real-model run (`openai:gpt-5.5` through an OpenAI-compatible endpoint) scored
**24/26**. Working through the failures — and the failures the fixes then caused — is the
point of this project:

1. **Ambiguous authority → wrong escalation.** In interactive testing the agent diagnosed
   KI-001 correctly but escalated instead of resolving: the KB said "enable the remote-config
   flag" without saying *who may do that*. Fixed in the system prompt: applying a documented
   workaround flag is a triage action, not a backend change.
2. **Out-of-scope requests verbally deflected, never filed.** Refund and GDPR-deletion
   requests got a polite "I'll route this once you send your account id" — if the customer
   walks away, no record exists. That is exactly the "silently dropped" failure the escalation
   policy forbids. Fixed: file immediately with `unknown` context; ask for details after.
3. **The fix for #2 caused a regression the suite caught.** "Escalate immediately" made the
   agent skip retrieval entirely — so it *guessed* severity S3 where policy mandates S2 for
   privacy requests. Fixed in two places: the severity table in the KB now names
   legal/privacy requests explicitly (docs are the source of truth), and the escalate tool's
   description requires a severity lookup first.
4. **Over-broad policy wording → escalation noise.** After #2, a harmless "does CabinCast
   support Spotify?" question got escalated to a human. The policy's "no KB match" rule now
   distinguishes reported problems (escalate) from informational questions (answer honestly
   that no information exists).
5. **An eval-suite bug: the check flagged a correct refusal.** The agent answered "I can't
   turn off privacy scrubbing" — and a naive substring check on "turn off privacy" failed it.
   Deterministic checks now test for *compliance claims*, not topic mentions, with phrasing
   quality left to the LLM judge.

A later full run surfaced one more noise pattern — a ticket filed for a question that was
answered as expected behavior — fixed with the same loop (trace → rule → targeted re-run).

After the fixes, full-suite runs score 25–26/26. The residual run-to-run variance is real —
LLM agents are not deterministic — which is exactly why the deploy gate is a threshold (85%)
rather than perfection, and why every eval failure links to its trace.

## Roadmap

- [x] **M0 — walking skeleton**: monorepo, CI, Docker + Fly.io deploy, mock domain data
- [x] **M1 — agent core**: LangGraph agent with 4 tools, trace capture, SSE chat
- [x] **M2 — the console**: trace viewer, 26-case eval gate in CI, versioned configs with one-click rollback, human-handoff inbox
- [ ] **M3 — packaging**: walkthrough video, public live-demo URL

## Development

```bash
# agent (Python 3.12)
cd apps/agent && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
export ANTHROPIC_API_KEY=...     # or OPENAI_API_KEY / GOOGLE_API_KEY
export DEFAULT_MODEL=anthropic:claude-haiku-4-5   # any provider:model-id
make dev-agent      # FastAPI on :8080

# console (Node 22+)
cd apps/console && npm install
make dev-console    # Vite on :5173, proxies /api to :8080

make test && make lint

# run the eval gate locally
cd apps/agent && .venv/bin/python -m agent_service.evals --report report.json
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
