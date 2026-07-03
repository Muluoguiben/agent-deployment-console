# Video Playback Troubleshooting

Start from the error code shown on screen (Settings > About > Last error also
records it). Always collect: head unit model, OS/WebView version, app version,
region, and whether the vehicle was moving (cellular handoff).

## Error codes

| Code | Meaning | First action |
|---|---|---|
| VP-4102 | Codec/decoder failure | Check WebView version — below 95 this is known issue **KI-001** |
| VP-2001 | Network/stream fetch failure | See network-connectivity.md |
| VP-3005 | DRM license failure | Check system clock, then account region vs content region |
| VP-1000 | Generic player error | Collect logs, retry once, then classify by symptoms |

## Symptom: black screen, audio plays but no picture

Almost always a decode failure (VP-4102). On WebView below 95, H.265 streams
cannot be decoded in hardware — this is **KI-001**. Workaround: enable the
remote config flag `video.codec_fallback=h264` for the account or fleet.
Permanent fix requires the OEM to ship a WebView OTA to 95 or later.

## Symptom: infinite loading spinner before playback

- In EU regions (DE/FR/NL): consent flow v2 must be completed before the
  player can start. If the consent screen never appeared, this is **KI-002**
  — have the user reset consent in Settings > Privacy > Reset consent.
- Other regions: usually VP-2001; see network-connectivity.md.

## Symptom: audio/video drift out of sync

On HU-9 during cellular network handoff, A/V desync is a known open issue
(**KI-006**, status: investigating). No user-side fix. Collect a playback log
bundle (Settings > About > Export logs) and escalate with severity S3.

## Symptom: playback stops in split-screen mode

On AuroraOS 3.2, entering split-screen while a video plays crashes the WebView
(**KI-004**). Fix is scheduled for app 2.8. Workaround: none; set expectations
with the customer and link the release note.
