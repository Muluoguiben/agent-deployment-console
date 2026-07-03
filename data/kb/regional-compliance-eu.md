# Regional Compliance (EU and general region handling)

## EU consent flow v2

In DE, FR, and NL, playback cannot start until the user completes consent
flow v2 (data-processing consent). The player shows an infinite spinner if
the consent state is missing or was recorded under the old v1 format —
this is **KI-002**.

Resolution: Settings > Privacy > Reset consent, then relaunch the app; the
v2 consent screen will be shown on next playback attempt.

## Data constraints

- EU accounts: playback telemetry is aggregated on-device and only uploaded
  in anonymized batches. Log bundles exported for support are scrubbed of
  personal identifiers automatically.
- US accounts: standard telemetry applies.
- Support agents must never ask users to disable privacy features to
  work around an issue.

## Unsupported regions

If an account's region is not in the supported list, the app shows a
static "not available" screen. This is expected behavior. Do not attempt
workarounds (VPN suggestions are prohibited). If the user believes the
region is wrong on their account, check for a provisioning mismatch
(**KI-005**) before concluding it is unsupported.

## Risk labels

Some content carries region-specific risk labels (e.g., driving-distraction
warnings that block video on the driver display while the vehicle is moving).
Video on the center display pausing while driving is **regulatory behavior,
not a bug**. Passenger and overhead displays are exempt on head units that
support display-level occupant detection (HU-9 only).
