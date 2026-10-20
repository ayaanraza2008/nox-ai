# NOX + LUMI dual-personality integration

## Implemented in this branch

- Adds a NOX/LUMI switcher to the existing conversation toolbar and to the minimal holographic home screen.
- Both personalities call the same existing `/api/chat` and `/api/chat/stream` routes, use the existing provider fallback logic, and share authorized tools and retrieval context.
- The selected personality is validated server-side and selects a separate system identity. NOX remains composed, direct, technically focused, and calm. LUMI is warm, expressive, cute-but-mature, and technically capable without claiming literal human feelings.
- Assistant messages retain a `personality` field in the existing chat history schema, so historical responses keep their label when the active personality changes.
- Switching personalities aborts the in-flight chat request, cancels queued speech and active audio, increments a response generation, and discards stale stream deltas. The current conversation is not cleared.
- Existing Edge neural TTS is reused. NOX defaults to Guy (US English), Prabhat (Indian English), Madhur (Hindi), and Asad (Urdu). LUMI defaults to Neerja (Indian English), Swara (Hindi), and Asad (Urdu fallback).
- Voice choice, rate, and pitch preferences are stored separately for each personality in the browser's existing local storage. A voice preview control uses the real `/api/tts` endpoint.
- Text-only privacy mode blocks microphone startup and spoken playback, stops an active voice session, cancels audio, and persists the preference.
- Pitch is passed to Edge TTS with a bounded server-side range. Voice IDs are constrained to the existing supported allowlist.

## Real limitations (not claimed as complete)

- Speech recognition still depends on the browser's SpeechRecognition implementation and its own processing/privacy behavior. This is not full-duplex server-side audio streaming.
- The currently configured voice allowlist contains only one Urdu voice (Asad), so NOX and LUMI use the same voice for Urdu until a verified supported female Urdu voice is added.
- LUMI has a distinct violet holographic accent and active identity in the existing NOX core, but a dedicated humanoid/Live2D avatar and genuine lip-sync are not implemented by this change.
- Browser/device availability, Edge TTS network access, and AI-provider configuration must be tested in the deployed environment.

## Tests

`backend/tests/test_dual_personality.py` checks personality prompts, request validation, conversation metadata, voice mapping, and pitch bounds. The repository's existing CI checks Python syntax, backend tests, Docker build, and inline JavaScript syntax. Use the PR's latest Actions run as the source of truth; do not infer a successful live deployment from a green build alone.
