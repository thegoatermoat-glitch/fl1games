# fl1nt cl0ud phone bridge (GeeLark + ws-scrcpy)

This is the **streaming bridge** you host yourself so the GeeLark virtual Android
phone shows inside fl1nt g4m3s. The fl1nt backend controls GeeLark (start/stop) and
asks this bridge to `adb connect` the phone; the browser streams it via ws-scrcpy.

```
Browser (fl1nt) ── iframe ──► BRIDGE (ws-scrcpy)  ── adb ──►  GeeLark cloud phone
        ▲                                                        ▲
        └──────── fl1nt backend (GeeLark start/stop, /connect) ──┘
```

## Requirements
- A small **Linux VPS** (1 vCPU / 1-2 GB is enough) with Docker.
- A public **HTTPS** URL in front of the bridge (fl1nt is https, so the bridge must be
  https/wss or the browser blocks it). Easiest: Cloudflare Tunnel, Caddy, or Nginx + Let's Encrypt.

## Deploy
```bash
git clone <this folder> cloudphone-bridge && cd cloudphone-bridge
docker compose up -d --build
# bridge now on http://SERVER_IP:8080  (health: /health)
```
Put HTTPS in front, e.g. with a Cloudflare Tunnel:
```bash
cloudflared tunnel --url http://localhost:8080
# gives you https://something.trycloudflare.com
```

## Tell fl1nt about the bridge
Set these in the fl1nt **backend** env (`/app/backend/.env`), then restart backend:
```
GEELARK_APP_ID="<your GeeLark appId>"
GEELARK_API_TOKEN="<your GeeLark apiKey>"   # already set
GEELARK_PHONE_ID="<optional: specific cloud phone id>"
GEELARK_ROBLOX_PKG="com.roblox.client"      # optional: auto-launch Roblox
CLOUDPHONE_BRIDGE_URL="https://something.trycloudflare.com"
```

## How it works at runtime
1. User opens the Roblox tile -> fl1nt backend `POST /open/v1/phone/start` (GeeLark).
2. Backend enables ADB, reads `adbAddress`/`debugPort`, and calls `POST BRIDGE/connect`.
3. Backend returns a `streamUrl` (ws-scrcpy) which the browser loads in the iframe.
4. The 2-hour/day cap and tab-close both trigger `POST /open/v1/phone/stop` (via the
   fl1nt backend / sendBeacon) so no phone keeps running.

## Notes
- GeeLark remote ADB must be reachable from the bridge host (GeeLark exposes it when the
  phone is started + ADB enabled).
- Uploading/running Roblox on a cloud phone is subject to Roblox's and GeeLark's terms
  — that's on the account you use.
- ws-scrcpy is GPL (NetrisTV/ws-scrcpy); it's cloned at build time, not bundled here.
