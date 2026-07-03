# CabinCast Product Overview

CabinCast is a video and music streaming web application embedded in vehicle
infotainment head units. It runs inside an Android WebView provided by the OEM
system image and is delivered through OEM and Tier-1 supplier channels.

## OEM partners and hardware

| Partner | Type | Regions | Head units |
|---|---|---|---|
| Aurora Motors | OEM | EU | AuroraOS 3.x (in-house head unit) |
| Kestrel Automotive | OEM | North America | HU-7, HU-9 (Helios Systems) |
| Nanhai Auto | OEM | APAC | HU-7, HU-9 (Helios Systems) |
| Helios Systems | Tier-1 supplier | all | HU-7 (2023), HU-9 (2025) |

## Plans

- **Standard** — included with vehicle purchase, ad-supported.
- **Premium** — subscription, offline caching and 1080p playback.
- **Fleet** — volume licensing for fleet operators (Kestrel fleet program);
  managed through the fleet admin portal, includes channel authorization keys.

## Runtime environment

- App runs in the OEM's Android WebView. Minimum supported WebView is **92**;
  full video codec support requires **95+** (see device-compatibility.md).
- Layouts adapt to center, passenger, overhead, and split-screen displays.
- Regional availability, login, and content catalogs are region-gated
  (see regional-compliance-eu.md and login-and-accounts.md).

## Support scope

The triage desk handles product, playback, login, connectivity, and
compatibility issues. **Billing, refunds, legal, and privacy/data requests are
out of triage scope and must be escalated** (see escalation-policy.md).
