# fl1nt g4m3s — PRD / State

## Product
Leetspeak-censored "unbl0ked g4m3s" site (fl1nt g4m3s). React + FastAPI + MongoDB.
Serves self-contained HTML5 games via backend proxy, plus a Cl0ud Gaming row backed by
cloud Android (GeeLark) and a self-hosted OVH noVNC option.

## Cl0ud Gaming tiles (category "Cl0ud Gaming")
- **Cl0ud Ph0n3** (slug `roblox-cloud`, type `cloudphone`): generic GeeLark phone, no auto-launch.
- **Minecraft** (`minecraft-cloud`, `cloudphone`): auto installs+launches team app `com.mojang.minecraftpe`.
- **Terraria** (`terraria-cloud`, `cloudphone`): auto installs+launches `com.and.games505.TerrariaPaid`.
- **Roblox (Cl0ud Ph0n3)** (`roblox-phone`, type `ovh`): streams a self-hosted OVH VPS via noVNC
  (OvhCloudPlayer). Mouse/touch/keyboard via noVNC. Cover `/covers/roblox-tile.jpg`.

## Game types
- `embed` (default): proxied via `/api/games/{slug}/play`.
- `external`: direct iframe of `target` (e.g. Undertale, Amanda The Adventurer — hosted GitHub Pages builds).
- `cloud` / `appetize`: routed through wisp proxy in GamePlayer.
- `cloudphone`: GeeLark session (queue, 30-min, per-user phone) via CloudPhonePlayer.
- `ovh`: noVNC viewer of self-hosted VPS via OvhCloudPlayer.

## Key endpoints
- `GET /api/games`, `/api/categories`, `/api/games/{slug}`, `/api/games/{slug}/play`
- Cloudphone: `POST /api/cloudphone/session/{join,heartbeat,leave}`, `GET /api/cloudphone/session/stats`
- OVH VNC: `GET /api/ovh/vnc` (returns configured URL), `POST /api/ovh/vnc {url}` (runtime-editable,
  stored in `app_config` collection, env fallback `OVH_VNC_URL`). Token rotation without redeploy.

## GeeLark app auto-launch (Minecraft/Terraria)
Background `_provision_app` in server.py: wait phone running → resolve uploaded team app via
`/app/installable/list` (getUploadApp) → `/app/install` → poll installStatus → `/app/start`.
appStatus surfaced to CloudPhonePlayer banner. Falls back to home screen on failure.

## Catalog
~430 games. 124 original mini-games added from GitHub (wangzifan396-wzf/mini-browser-games).

## Deploy artifacts
`/app/deploy/roblox-cloud/` — orchestrator to self-host redroid + browser stream on an OVH VPS
(orchestrate.sh, docker-compose.yml, wsscrcpy.Dockerfile, README.md). Roblox anti-cheat (Byfron)
likely blocks redroid; Minecraft/Terraria fine.

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
