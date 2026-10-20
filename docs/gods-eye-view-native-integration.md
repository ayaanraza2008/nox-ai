# God's Eye View: native NOX integration boundary

## Current status

The upstream repository is pinned for traceability at `505d2cb5861905c76a98465799a29e1fd71b869b`. NOX currently has a configuration/status panel, but the upstream Cesium application is **not yet mounted as a native NOX component**. The previous launch button opened a separate Render service in a new tab. That does not satisfy the native-integration requirement.

This change deliberately disables that external launch path, reports `native_integration_pending`, and makes the limitation visible in the NOX panel. It does not claim that a globe, live data, or remote layer controls are available inside NOX.

## Why a simple import is not enough

God's Eye View is a vanilla-JavaScript + Vite + Cesium application, not a framework-neutral widget. Its standalone entry owns page-level markup, document-wide IDs, CSS, loading/error surfaces, Cesium viewer lifecycle, data controllers, and several global UI controls. The NOX frontend is a separate static HTML/JavaScript application. Copying its built page, opening a new tab, or wrapping it in an iframe would preserve two separate application shells rather than integrate the module.

A proper native integration must create an explicit mount/unmount boundary in the upstream app (or a maintained NOX adapter) and make its DOM, styles, viewer lifecycle, data providers, and teardown scoped to a NOX workspace. It also needs to bundle Cesium assets and worker files into the NOX production build and preserve the upstream source/data attribution and provider-key rules.

## Included in this change

- External God’s Eye View launch is disabled in the UI and configuration API.
- The UI clearly reports that the native globe is pending instead of implying that a separate service is integrated.
- A viewport-aware CSS layer standardizes minimum sizing, desktop internal scroll regions, responsive single-column behavior, overflow containment, and reduced-motion behavior.
- Regression tests verify that setting `GODS_EYE_VIEW_URL` cannot re-enable external navigation.

## Remaining work before calling the integration complete

1. Refactor or adapt the upstream application to expose a supported `mount(root, options)` / `destroy()` contract.
2. Scope upstream DOM and CSS to the NOX God’s Eye workspace; remove duplicate global shell controls without breaking accessibility.
3. Bundle the upstream Cesium/Vite dependencies and worker assets with the NOX deployment rather than requiring a second frontend service.
4. Connect only documented, authorized data providers through same-origin APIs; preserve upstream attribution and rate limits.
5. Test globe startup, resizing, navigation away/back, WebGL context loss, data-feed failures, and resource cleanup on desktop and mobile.

Until those steps and their tests pass, the UI must continue to show the native integration as pending.
