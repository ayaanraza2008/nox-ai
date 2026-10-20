# NOX AI — God's Eye View

## Integration design

The upstream project is pinned as a Git submodule at `integrations/gods-eye-view`:
https://github.com/bilawalsidhu/gods-eye-view/tree/505d2cb5861905c76a98465799a29e1fd71b869b

NOX launches it as a dedicated service instead of copying its code into the static
frontend. The upstream Vite middleware owns its own `/api/*` provider routes;
NOX FastAPI already owns that namespace, so a separate origin avoids collisions.
The NOX workspace is a launcher/status surface, not a screenshot or fake globe.
The native globe and its data-layer controls run in the upstream application.

## Deploy on Render

1. Open the existing NOX service's Render Blueprint and sync/apply the updated
   `render.yaml`. This adds `nox-gods-eye-view` as a separate Docker web service.
2. Wait for its first build/deploy. The Dockerfile pins upstream commit
   `505d2cb5861905c76a98465799a29e1fd71b869b`, installs the lockfile with
   `npm ci`, and launches the upstream Docker entry point on Render's `PORT`.
3. The Blueprint sets `GODS_EYE_VIEW_URL=https://nox-gods-eye-view.onrender.com`
   on NOX. If Render assigns another hostname, update that environment variable
   and `GEV_ALLOWED_HOSTS` on the globe service to the exact hostname.
4. Redeploy NOX and open **God's Eye** in the top navigation. Use **Launch full
   workspace** to open the real upstream app in a new tab.

This Blueprint uses Render's free plan; free services may sleep when idle and
the first load may be slow. Cesium/WebGL performance depends on the device.
No paid plan is enabled automatically.

## Providers, costs and licensing

The upstream README documents keyless basemap and public-data fallbacks. Some
imagery, terrain, voice, geocoding and other providers may require optional keys,
quotas, provider approval or payment. Configure credentials only in the globe
service's private Render environment settings; never commit real keys. Respect
each provider's terms, attribution, refresh limits and license. The upstream
code is MIT-licensed, but some included datasets/assets have separate terms;
review upstream `LICENSE`, `DATA_SOURCES.md` and `THIRD_PARTY_NOTICES.md`
before redistributing or using the associated data commercially.

## Local run

```bash
git clone https://github.com/ayaanraza2008/nox-ai.git
cd nox-ai
git submodule update --init --recursive
cd integrations/gods-eye-view
npm ci
npm run doctor
npm run dev
```

Use Node.js 24.14.x (or the upstream-documented supported Node 26.x). Open the
local URL printed by Vite. Do not expose a local development server publicly
without appropriate access controls.

## Verification checklist

After deployment, verify the globe service URL in a browser, then test camera
rotation, zoom and pan. Enable only the layers you intend to use and verify their
in-app source/timestamp/status; a configured launch URL is not proof that the
service or a live data provider is healthy. Run the upstream `npm run doctor`,
`npm test`, `npm run build`, `npm run test:track` and relevant `npm run qa:*`
scripts in a local checkout where prerequisites are available. NOX CI checks do
not prove the separate Render service is live. Cross-window remote layer control
from NOX chat is not connected; NOX must not claim a layer changed unless a
future authenticated bridge confirms the action.
