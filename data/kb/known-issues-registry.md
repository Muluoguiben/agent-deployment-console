# Known Issues Registry

Authoritative list of tracked issues. Structured data lives in
`data/known_issues.json`; this doc is the prose mirror for retrieval.

| ID | Title | Status | Action |
|---|---|---|---|
| KI-001 | H.265 decode failure on WebView 92–94 (VP-4102) | workaround available | Enable `video.codec_fallback=h264`; permanent fix is OEM WebView OTA to 95+ |
| KI-002 | EU consent flow v2 missing/stale → infinite spinner (DE/FR/NL) | resolved by user action | Settings > Privacy > Reset consent, relaunch |
| KI-003 | HU-7 clock skew after battery disconnect → QR pairing fails | workaround available | Enable automatic time (NTP), reboot, retry pairing |
| KI-004 | AuroraOS 3.2 split-screen crash during playback | fix scheduled (app 2.8) | No workaround; set expectations, link release note |
| KI-005 | Vehicle provisioning region ≠ account region → login blocked | escalation required | Backend region reset only; escalate S2 with VIN region + account region |
| KI-006 | HU-9 A/V desync after cellular handoff | investigating | No user-side fix; collect log bundle, escalate S3 |
| KI-007 | Fleet channel authorization expired → fleet-wide login failure | self-service renewal | Fleet admin portal > Contracts > Renew; escalate S2 if still failing 24h after renewal |
| KI-008 | RTL subtitle languages (Arabic, Hebrew) not supported | planned | Known limitation; no ETA committed — do not promise a date |

## Reading the registry

- **workaround available / resolved by user action** — triage can resolve
  directly; cite the KI id and the exact steps.
- **fix scheduled / planned** — triage sets expectations; never promise an
  unannounced date.
- **escalation required / investigating** — triage must escalate per
  escalation-policy.md with the handoff summary format.
