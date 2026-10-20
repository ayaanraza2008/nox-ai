# NOX AI — God's Eye View integration

## Architecture

God's Eye View is maintained upstream at https://github.com/bilawalsidhu/gods-eye-view.
NOX runs it as a dedicated Node/Vite service rather than copying its frontend into
NOX's static bundle. The upstream Vite middleware also serves provider APIs under
/api/*; NOX's FastAPI app already owns that path, so combining the two servers
under one origin without a deliberate API proxy would cause route collisions.

The service container is defined by deploy/gods-eye-view.Dockerfile. It fetches
the exact upstream commit 505d2cb5861905c76a98465799a29e1fd71b869b, installs
the upstream lockfile with npm ci, and launches the upstream-supported
scripts/docker-start.mjs entry point. The commit is pinned for reproducible
builds; update it only after reviewing upstream changes and their tests.

NOX's dedicated GOD'S EYE VIEW workspace is a launch/status surface, not an
iframe or a fake globe. It opens the actual upstream application in a new tab.
Native layer controls live inside that application. Cross-window remote control
from NOX chat is not implemented; NOX must not claim that a layer was toggled
unless a future, authenticated bridge confirms the action.

## Deploy on Render

1. Push the NOX repository to GitHub (the integration files are committed there).
2. In Render, open the existing NOX Blueprint and sync/apply the updated
   render.yaml. This adds the separate nox-gods-eye-view Docker web service.
3. Wait for the new service's first build and deployment. It uses the upstream
   Docker launcher and listens on Render's PORT.
4. The NOX service receives GODS_EYE_VIEW_URL=https://nox-gods-eye-view.onrender.com
   from the Blueprint. If Render assigns a different hostname or you use a custom
   domain, set GODS_EYE_VIEW_URL on NOX to that HTTPS origin and set the exact
   host in GODS_EYE_VIEW_ALLOWED_HOSTS as documented below.
5. Deploy NOX after the Blueprint change and open GOD'S EYE VIEW from the top
   bar or mobile workspace tabs.

Both services are configured for Render's free plan. Free instances may sleep
when idle and have limited CPU/RAM; first load can be slow, and Cesium/WebGL
performance depends on the browser/device. If the service fails to build or runs
out of memory, inspect Render's build/runtime logs before changing the plan.
No paid upgrade is made automatically.

## Environment and providers

- GODS_EYE_VIEW_URL: HTTPS root URL of the dedicated service. Defaults to the
  Blueprint's https://nox-gods-eye-view.onrender.com.
- GODS_EYE_VIEW_ALLOWED_HOSTS: optional comma-separated exact hostnames for
  a custom domain. Never use wildcard entries.
- GEV_ALLOWED_HOSTS: exact hostname allowed by the upstream Vite Host check;
  update it if the service hostname changes.
- CESIUM_ION_TOKEN, GOOGLE_MAPS_API_KEY, MAPILLARY_CLIENT_TOKEN, and voice-provider
  keys are optional upstream settings. Add them only through the Render service's
  private environment settings. Follow upstream/provider terms, quotas, and key
  restrictions. Client-exposed map tokens must be public-scoped and restricted
  as the provider documents.
- Keyless basemaps and some public feeds are supported upstream, but no specific
  live layer is guaranteed: provider availability, rate limits, geography, and
  source freshness vary. Read the in-app provider/layer status and upstream
  data-source notes at https://github.com/bilawalsidhu/gods-eye-view/blob/main/DATA_SOURCES.md.

Do not place secrets in this repository or in frontend JavaScript. The upstream
source code is MIT-licensed; some included datasets and third-party models have
separate licenses, including non-commercial restrictions. Review upstream
LICENSE, DATA_SOURCES.md, and THIRD_PARTY_NOTICES.md at the pinned commit
before distributing or using data commercially.

## Local development

Clone NOX, then fetch the pinned upstream project in its own directory:

    git clone https://github.com/ayaanraza2008/nox-ai.git
    cd nox-ai
    git clone https://github.com/bilawalsidhu/gods-eye-view.git integrations/gods-eye-view
    git -C integrations/gods-eye-view checkout 505d2cb5861905c76a98465799a29e1fd71b869b
    cd integrations/gods-eye-view
    npm ci
    HOST=127.0.0.1 PORT=4173 npm run dev

Use Node.js 24.14.x for the upstream version pinned by this integration. The
upstream Vite server is the application entry point because its middleware
provides live-data routes; a static npm run build alone is not an equivalent
deployment for those routes. Never expose a local development server publicly
without the upstream host/security controls.

## Test status

Repository inspection and CI syntax checks can verify the NOX-side integration,
but they cannot prove that the separate Render service is live. After syncing the
Blueprint, test the new service URL in a browser, confirm the globe loads, use
zoom/pan/rotation, enable a layer with a real source, and check provider timestamps
and errors. Run upstream npm run doctor, npm test, npm run test:track, and relevant
npm run qa:* scripts from a local checkout with their documented prerequisites.
Do not report a layer as live if its provider is unavailable.
