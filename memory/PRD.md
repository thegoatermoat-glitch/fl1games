# fl1nt g4m3s — PRD / State

## Product
Leetspeak-censored "unbl0ked g4m3s" site (fl1nt g4m3s). React + FastAPI + MongoDB.
Serves self-contained HTML5 games via backend proxy, plus a Cl0ud Gaming row backed by
cloud Android (GeeLark) and a self-hosted OVH noVNC option.

## Cl0ud Gaming tiles (category "Cl0ud Gaming")
- **Cl0ud Ph0n3** (slug `roblox-cloud`, type `cloudphone`): generic GeeLark phone, no auto-launch.
- **Minecraft** (`minecraft-cloud`, `cloudphone`): auto installs+launches team app `com.mojang.minecraftpe`.
- **Terraria** (`terraria-cloud`, `cloudphone`): auto installs+launches `com.and.games505.TerrariaPaid`.
- **Roblox (Cl0ud Ph0n3)** (`roblox-phone`, type `ovh`): per-user self-hosted redroid phone
  via VPS orchestrator (OvhCloudPlayer). 12-slot queue, 25-min sessions, appetize-style viewer
  with touch/keyboard. Cover `/covers/roblox-tile.jpg`.

## Game types
- `embed` (default): proxied via `/api/games/{slug}/play`.
- `external`: direct iframe of `target` (e.g. Undertale, Amanda The Adventurer — hosted GitHub Pages builds).
- `cloud` / `appetize`: routed through wisp proxy in GamePlayer.
- `cloudphone`: GeeLark session (queue, 30-min, per-user phone) via CloudPhonePlayer.
- `ovh`: noVNC viewer of self-hosted VPS via OvhCloudPlayer.

## Key endpoints
- `GET /api/games`, `/api/categories`, `/api/games/{slug}`, `/api/games/{slug}/play`
- Cloudphone: `POST /api/cloudphone/session/{join,heartbeat,leave}`, `GET /api/cloudphone/session/stats`
- OVH VNC: `GET/POST /api/ovh/vnc` (static console URL, legacy).
- OVH pool: `POST /api/ovh/session/{join,heartbeat,leave}`, `GET /api/ovh/session/stats`
  (12 slots, 25 min, queue). `GET/POST /api/ovh/config` sets orchestrator URL+token
  (app_config, env fallback ORCHESTRATOR_URL/ORCHESTRATOR_TOKEN). Calls VPS orchestrator
  /allocate + /release per user.

## GeeLark app auto-launch (Minecraft/Terraria)
Background `_provision_app` in server.py: wait phone running → resolve uploaded team app via
`/app/installable/list` (getUploadApp) → `/app/install` → poll installStatus → `/app/start`.
appStatus surfaced to CloudPhonePlayer banner. Falls back to home screen on failure.

## Catalog
~430 games. 124 original mini-games added from GitHub (wangzifan396-wzf/mini-browser-games).

## Deploy artifacts
`/app/deploy/roblox-cloud/orchestrator/` — VPS-side redroid POOL orchestrator (FastAPI):
one redroid phone per user (max 12), installs merged Roblox APK from split-to-single link,
ws-scrcpy browser stream, /allocate + /release + /health. setup.sh + nginx.sample.conf.
`/app/deploy/roblox-cloud/` also has a single-phone smoke-test (orchestrate.sh + compose).
Roblox anti-cheat (Byfron) likely blocks launch/login; Minecraft/Terraria fine.

## Implemented (2026-06)
- Renamed Roblox→Cl0ud Ph0n3; added Minecraft/Terraria/Roblox cloud tiles with user logos.
- 124 new games added w/ dedup.
- Undertale + Amanda The Adventurer as `external` tiles.
- Minecraft/Terraria GeeLark team-app auto install+launch.
- Roblox tile switched to OVH noVNC client (OvhCloudPlayer) with touch/keyboard + editable link.

## Backlog (P1/P2)
- Queue ETA on cloud tiles.
- Proxy/slot exhaustion UI warning.
- Remaining-minutes badge on tiles.
- Auto-scale noVNC to fill viewer (resize=scale relies on full noVNC client).
- Point OVH tile at Android display once VPS runs redroid + GUI.
