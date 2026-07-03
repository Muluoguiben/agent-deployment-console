# Device Compatibility

## Support matrix

| Head unit | Shipped | OS | Min WebView | Full codec support | Split-screen | Notes |
|---|---|---|---|---|---|---|
| HU-7 | 2023 | Helios Android 11 | 92 | WebView 95+ (else KI-001) | no | NTP off by default (KI-003) |
| HU-9 | 2025 | Helios Android 13 | 95 | yes | yes | occupant detection; A/V desync on handoff (KI-006) |
| AuroraOS 3.x | 2024 | Aurora fork of Android 12 | 94 | 3.3+ | 3.1+ (3.2 crashes, KI-004) | WebView updated only via full OS OTA |

## WebView versions

- WebView below **92**: app refuses to start (hard floor).
- WebView **92–94**: app runs; H.265 content fails with VP-4102 (**KI-001**).
  Workaround: remote config flag `video.codec_fallback=h264`.
- WebView **95+**: full support.

On Helios units the WebView updates through the OEM OTA channel, not the app
store. Triage cannot trigger an OTA; recommend the workaround flag and note
the account for the OEM OTA campaign list.

## Display layouts

Supported aspect ratios: 16:9, 21:9 (center), 32:9 (pillar-to-pillar,
split rendering), 4:3 (overhead). Passenger-display playback while driving
is allowed only on HU-9 (occupant detection); on all other units video is
restricted to the center display while parked — see regional-compliance-eu.md
risk labels for the regulatory background.
