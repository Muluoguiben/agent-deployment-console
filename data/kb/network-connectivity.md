# Network and Connectivity

## Error VP-2001 (stream fetch failure)

1. Check signal: Settings > About > Network shows carrier and signal quality.
2. If the vehicle is in an underground garage or dead zone, retry in coverage.
3. If persistent on good signal, export a log bundle and check for a
   proxy/firewall on fleet SIMs (fleet APNs sometimes block the CDN domains;
   the fleet admin portal lists required domains under "Network allowlist").

## Cellular handoff

Head units switch towers frequently while driving. The player pre-buffers
45 seconds to bridge handoffs. Known open issue: on HU-9 the audio pipeline
resumes faster than video after a handoff, causing A/V desync (**KI-006**,
investigating). Collect logs and escalate S3.

## Offline behavior

- Premium accounts: downloaded content plays offline; browsing is disabled.
- Standard accounts: fully online; the app shows the offline screen without
  connectivity. This is expected behavior.

## Buffering guidance

Persistent buffering with good signal usually indicates the CDN edge is being
reached through a distant PoP (common right after regional launches). Collect
the CDN node ID from the log bundle. If the node region does not match the
vehicle region, escalate S3 with the node ID — routing fixes are backend-side.
