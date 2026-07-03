# Escalation Policy

Triage's definition of done: every issue leaves **resolved** or **correctly
classified and routed with full context**. Never guess a fix that is not
grounded in the KB; never drop an issue silently.

## Severity levels

| Severity | Definition | Example |
|---|---|---|
| S1 | Safety-relevant or fleet-wide outage | Fleet-wide login failure |
| S2 | Feature unusable, no workaround, backend action required; legal/privacy/data-subject requests | Region provisioning mismatch (KI-005); GDPR deletion or export request |
| S3 | Degraded experience, workaround exists or fix scheduled | A/V desync (KI-006), buffering with CDN mis-routing |
| S4 | Cosmetic, question, or expected behavior | Layout question, private-mode behavior |

## The agent MUST escalate when

1. **No KB match for a reported problem** — the customer's symptoms match no doc
   and no known issue. Do not invent a resolution. (Purely informational or
   product questions the KB doesn't cover are different: answer honestly that
   the information isn't available — no escalation needed.)
2. **Backend data change required** — e.g., region provisioning reset
   (KI-005). Triage has no write access to provisioning records.
3. **Out of scope** — billing, refunds, legal, privacy/data-subject requests,
   press inquiries. These have dedicated teams.
4. **Open investigations** — issues marked "investigating" (e.g., KI-006)
   need a log bundle attached and go to the owning team.
5. **Suspected new defect** — reproducible behavior contradicting the KB.

## Handoff summary format

Every escalation must include:

- **Symptom** — one sentence, plus error code if any.
- **Account context** — account ID, head unit, OS/WebView, app version, region.
- **Docs consulted** — which KB docs / known issues were checked.
- **Ruled out** — causes eliminated and why.
- **Suspected cause** — best hypothesis, or "unknown".
- **Severity** — S1–S4 per the table above.
