# NOX Android Companion

This native Android app can launch matching installed apps from a NOX website deep link and can join a NOX pairing session for remote app-opening/search commands.

## Build and install

1. Open the android-companion folder in Android Studio.
2. Use JDK 17 and Android SDK 35, then sync Gradle.
3. Build and install the debug app on your Android device.
4. Open NOX in a browser on the same account/session, open Device Pairing, and create a six-digit code.
5. Open NOX App Launcher on Android, enter the code within five minutes, and allow the persistent NOX notification/service to remain enabled.

## Paired control

- The app stores its pairing session and token in Android app-private SharedPreferences.
- A foreground service polls the hosted relay every five seconds and retries after temporary network failures.
- Choose NOX Android Companion in the website's Send chat commands to selector, then send a command in the normal NOX chat.
- If Android allows the app to launch while the companion is foreground, it launches directly. When the app is in the background, Android may require you to tap the NOX notification to open the requested app. This is an OS security restriction, not a failed pairing.
- Open the companion again to manage the session. Disconnect clears the local pairing token and stops the service; disconnect the companion device in the website if needed.
- The Android service supports app names, a small allowlist of common websites, explicit HTTP(S) URLs, and Google/YouTube/Bing searches. It does not execute shell commands, send messages, or control arbitrary app internals.

Pairing tokens are private credentials. Do not share them. A device can reconnect only while its session is still present on the server and its token has not been revoked.


## Android Emergency Stop

The paired-control foreground notification now includes an **EMERGENCY STOP** action. Tapping it latches a local stopped flag in the app's private preferences, interrupts command polling, stops the paired-control foreground service, and stops the local location service. If a command has already been fetched but not yet executed, the service checks the latch before acting and attempts to report it as cancelled.

To resume, open NOX Android Companion and explicitly choose **Resume NOX** in the Emergency Stop dialog. The service does not restart itself while the local latch is set. Android may delay or restrict background work according to system policy; the notification action is the supported user-visible control.

**Scope:** this is a local Android stop control. The hosted dashboard does not yet send an authenticated, per-device emergency-stop signal to every paired Android service, so do not treat dashboard and Android local stop states as one distributed atomic switch.
