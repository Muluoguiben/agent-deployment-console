# Login and Accounts

## QR pairing flow

1. Head unit shows a QR code (valid **90 seconds**).
2. User scans it with the CabinCast mobile app and confirms.
3. Head unit polls for confirmation and creates a session.

### QR code "expired" immediately or within seconds

If the head unit system clock is skewed, the QR token is rejected as expired.
On HU-7 units this happens after battery disconnection because NTP sync is
disabled by default — this is **KI-003**. Fix: enable
Settings > System > Automatic time (NTP), reboot the head unit, retry pairing.

## Region-based login

The login region is determined by the account's registered region, not GPS.
Content catalogs, features, and compliance flows follow the account region.

### "This service is not available in your region"

- If the vehicle was imported or resold across regions, the vehicle's
  provisioned region and the account region can mismatch — this is **KI-005**.
  The region field on a vehicle provisioning record can only be changed by the
  backend operations team. **Escalate with severity S2**; include VIN region,
  account region, and account ID in the handoff.
- If the account region is genuinely unsupported, follow the unsupported-region
  handling in regional-compliance-eu.md (applies to all regions, not only EU).

## Session expiry

Sessions last 30 days of inactivity. Fleet accounts additionally require a
valid channel authorization key — if the key has expired, all vehicles in the
fleet see "authorization required" at login (**KI-007**). Renewal is done by
the fleet administrator in the fleet admin portal; triage can send the renewal
guide but cannot renew on the customer's behalf.

## Private accounts

Private-mode accounts hide watch history and disable personalized rows. This
is expected behavior, not a defect; point users to Settings > Privacy.
