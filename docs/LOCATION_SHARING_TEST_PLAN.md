# NOX Location Sharing — Verification Plan

## Automated backend checks

Run:

```bash
python -m unittest backend.tests.test_location_sharing -v
python -m unittest discover -s backend/tests -v
```

The focused tests cover account-authentication gating, invalid coordinates, missing device tokens, paused/expired consent, freshness/stale state, and request throttling. They do not replace a live PostgreSQL migration test.

## Database and authorization test

1. Apply `supabase/migrations/202610200001_location_sharing.sql` to a disposable PostgreSQL database.
2. Configure `DATABASE_URL` or `SUPABASE_DB_URL` for the API runtime.
3. Use two separate NOX accounts. Enroll a device under account A, create an invitation as account B, and accept it as account A.
4. Confirm account B cannot read any location before A explicitly enables sharing.
5. Enable sharing for one hour, upload a test point from the enrolled device, and verify B sees a fresh point and its accuracy.
6. Pause sharing as A. Verify B immediately loses current coordinates and cannot fetch history. Verify A can still inspect their own last-known point.
7. Revoke the device and confirm its token can no longer upload or read mobile consent status.
8. Wait beyond the two-minute freshness threshold and verify the point is labelled stale/offline, never shown as a live map marker.
9. Confirm history older than `NOX_LOCATION_RETENTION_DAYS` is deleted by the scheduled server cleanup.

Use synthetic test coordinates only in a non-production account.

## Android physical-device test

1. Build `android-companion` with `./gradlew assembleDebug` and install on a real Android phone.
2. Enroll with a single-use web-generated code. Confirm enrollment alone does not start location uploads.
3. Deny location permission and confirm no location is uploaded.
4. Grant location permission, start the visible foreground service, and confirm the persistent NOX notification appears.
5. Keep account sharing paused: confirm the service reports paused and does not request GPS updates.
6. Enable sharing from the web dashboard: confirm the service starts location updates and the dashboard shows timestamp and accuracy.
7. Pause/revoke sharing, disable GPS, enable airplane mode, and test battery saver separately. Confirm the UI labels offline/stale data accurately.
8. Stop the service from the companion and confirm new updates cease. Reboot the phone and verify OS-specific restart behavior; do not assume the OS guarantees restart.
9. Test Android versions supported by the release and inspect permission disclosures before distribution.

## Not covered yet

iOS/Core Location and APNs, Flutter packaging, geofence alerts, verified-phone/SMS delivery, multi-instance distributed rate limiting, automated emulator tests, and app-store review are not implemented in this increment. The repository currently contains a native Android companion, not a Flutter/iOS application.
