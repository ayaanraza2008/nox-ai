# NOX Android Companion (browser-first preview)

## What works now

The hosted NOX web UI recognizes a simple task such as **Open Instagram** when it is being used in an Android browser. It asks for confirmation, then opens the official `https://www.instagram.com/` URL. Depending on the phone's Android app-link and browser settings, this may open the installed Instagram app or the website.

This is intentionally an allowlisted action. It does not run arbitrary commands, read other apps' data, or silently control the phone.

## How to test

1. Open https://nox-ai-vcqx.onrender.com on the Android phone.
2. Open Task Orchestrator.
3. Enter `Open Instagram` and press **Run task**.
4. Confirm the browser prompt.
5. Check whether Android opens Instagram or its website.

If the old behavior still appears, refresh the site after the latest Render deployment completes. GitHub commit alone does not confirm that Render is serving the new frontend.

## Limits of a browser-based companion

A website cannot provide general Android app/device control. Android restricts launching other apps and accessing their data; results also depend on browser settings and whether Instagram is installed. This preview only opens the official HTTPS link.

## Native Android companion — future step

A fuller companion would need a separately installed Android app (for example, a Kotlin app or trusted PWA wrapper), explicit Android intents for supported destinations, a visible permission/onboarding flow, and user confirmation for every action. Any Accessibility Service would require a separate, clearly disclosed opt-in and should not be used to bypass Android security or collect screen content secretly. Keep actions allowlisted and avoid arbitrary shell execution.

## Security

- Only the fixed Instagram HTTPS destination is handled by this browser preview.
- A confirmation prompt appears before navigation.
- No secret token is embedded in the web frontend.
- This is not a remote-control service and cannot guarantee that the Instagram native app opens.


## Consent-based location sharing (Android companion)

The native Kotlin companion now has a separate location-enrollment flow. It does not infer coordinates from a phone number.

1. In NOX web, sign in and open **Features → Location Intelligence**.
2. Select **Generate device code** and enter the one-time six-digit code in the Android companion under **Location sharing options → Enroll this phone**.
3. Grant Android location permission. The companion registers the device, but this alone does not share coordinates.
4. In NOX web, select **Start / resume** for that device and set the consent expiry. The companion's ongoing notification reports whether sharing is active, paused, or offline.
5. Stop the local service from the companion or pause/revoke the device in NOX web at any time.

Background updates depend on Android permissions, battery settings, network, GPS and OS scheduling. The service checks server consent before requesting location. iOS/Core Location support is not included yet.
