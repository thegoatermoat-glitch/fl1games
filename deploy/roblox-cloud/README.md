# Self-hosted per-user Android cloud (OVH) — Roblox tile

Two paths live here:

## A) Multi-user pool orchestrator  ← use this (matches the site's Roblox tile)
`orchestrator/` spins up **one redroid Android phone per user** (max 12, 25 min each),
auto-installs the **merged** Roblox APK from your `split-to-single` link, launches it, and
streams each phone to the browser via ws-scrcpy. The website calls its HTTP API.

### Run on the OVH VPS (Ubuntu 22.04, KVM/dedicated, ports 9000 + 443 open)
```bash
scp -r orchestrator root@YOUR_OVH_IP:/root/
ssh root@YOUR_OVH_IP
cd /root/orchestrator
chmod +x setup.sh
sudo STREAM_BASE=https://YOUR_VPS_DOMAIN/stream ORCHESTRATOR_TOKEN=pickAsecret MAX_PHONES=12 ./setup.sh
```
Put nginx TLS in front (see `orchestrator/nginx.sample.conf`) so `/stream/` and `/orch/`
are HTTPS. Then in the site: open the **Roblox** tile → **Server** button → set
`URL=https://YOUR_VPS_DOMAIN/orch` and the token. Done — users now get their own phone.

### API contract (what the site expects)
- `POST /allocate {clientId}` → `{id, streamUrl}` (or `503` when the pool is full)
- `POST /release  {id}`       → `{ok:true}`
- `GET  /health`              → `{max, active, free}`

### Host arch
- x86_64 → `jj9011/redroid:11.0.0-houdini` (ARM translation)
- arm64  → `redroid/redroid:11.0.0-latest`

## B) Single-phone quick test
`orchestrate.sh`, `docker-compose.yml`, `wsscrcpy.Dockerfile` — boots ONE redroid + stream
and installs a bundle. Handy for a smoke test before running the pool.

## Reality check (Roblox)
Roblox's Hyperion/Byfron uses Play Integrity attestation. redroid is a container without
hardware attestation, so Roblox commonly **installs and boots but blocks launch/login**.
Minecraft/Terraria and most apps work fine on this same stack. The APK page itself notes
"anti-tamper checks may still block launch/login".
