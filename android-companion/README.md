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
