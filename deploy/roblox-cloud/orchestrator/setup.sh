#!/usr/bin/env bash
# One-time setup + run for the redroid pool orchestrator on an OVH Ubuntu 22.04 VPS.
# Run as root:  sudo ./setup.sh
set -euo pipefail

log(){ echo -e "\n\033[1;36m[setup]\033[0m $*"; }
[ "$(id -u)" = "0" ] || { echo "run as root"; exit 1; }

# ---- host deps ----
log "Installing docker, node, adb, python, kernel modules..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl unzip jq git android-tools-adb \
  python3-pip python3-venv "linux-modules-extra-$(uname -r)" || true
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh
command -v node   >/dev/null || { curl -fsSL https://deb.nodesource.com/setup_20.x | bash -; apt-get install -y nodejs; }

# ---- kernel binder/ashmem (required by redroid) ----
log "Loading binder/ashmem..."
modprobe binder_linux devices="binder,hwbinder,vndbinder" || true
modprobe ashmem_linux || echo "  (ashmem missing on 5.18+ = usually fine, uses memfd)"
printf "binder_linux\nashmem_linux\n" > /etc/modules-load.d/redroid.conf

# ---- get Roblox splits from the .apkm (real, stable direct URL) ----
log "Preparing Roblox splits from .apkm..."
mkdir -p /opt/roblox
APKM=/opt/roblox/roblox.apkm
SPLITS=/opt/roblox/splits
APKM_URL="${ROBLOX_APKM_URL:-https://customer-assets-rejwkqb3.emergentagent.net/job_fl1nt-arcade/artifacts/uz0krpuc_com.roblox.client_2.739.691-3120_3arch_1feat_435c261897f97c1b525693b6140973f6_apkmirror.com%20%282%29.apkm}"
if [ ! -s "$APKM" ]; then
  echo "  downloading $APKM_URL"
  curl -fL "$APKM_URL" -o "$APKM"
fi
unzip -tq "$APKM" >/dev/null 2>&1 || die "the .apkm is not a valid archive. Put a valid .apkm at $APKM (or set ROBLOX_APKM_URL) and re-run."
rm -rf "$SPLITS"; mkdir -p "$SPLITS"
unzip -o "$APKM" -d "$SPLITS" >/dev/null
echo "  splits:"; ls -1 "$SPLITS"/*.apk

# ---- in-phone VNC stream: noVNC + websockify (token proxy) on host :8000 ----
log "Setting up noVNC + websockify (browser stream) on host :8000..."
apt-get install -y novnc websockify || pip3 install websockify
# locate the noVNC web root (varies by distro)
NOVNC_WEB=/usr/share/novnc
[ -d "$NOVNC_WEB" ] || NOVNC_WEB=/usr/share/webapps/novnc
mkdir -p /opt/tokens
# download the in-phone VNC server (droidVNC-NG) that each phone will run
if [ ! -s /opt/roblox/droidvnc.apk ]; then
  DV_URL="$(curl -fsSL https://api.github.com/repos/bk138/droidVNC-NG/releases/latest | jq -r '.assets[]?.browser_download_url' | grep -Ei '\.apk$' | head -1)"
  [ -n "$DV_URL" ] && curl -fL "$DV_URL" -o /opt/roblox/droidvnc.apk || echo "  WARN: could not fetch droidVNC-NG apk; set DROIDVNC_APK manually"
fi
pkill -f "ws-scrcpy" 2>/dev/null || true
pkill -f "websockify" 2>/dev/null || true
fuser -k 8000/tcp 2>/dev/null || true
sleep 1
nohup websockify --web="$NOVNC_WEB" --token-plugin=TokenFile --token-source=/opt/tokens 8000 \
  >/var/log/novnc.log 2>&1 &

# ---- proxy gateway image (only needed if PHONE_PROXY is set) ----
if [ -n "${PHONE_PROXY:-}" ]; then
  log "Building proxy gateway image (routes each phone through PHONE_PROXY)..."
  docker build -t fl1nt-proxy-gw "$(dirname "$0")/proxy-gateway"
  echo "  phones will tunnel through: ${PHONE_PROXY%%@*}@***"
fi

# ---- orchestrator (python) ----
# ---- HTTPS for the browser stream (Let's Encrypt on the OVH hostname) ----
DOMAIN="${DOMAIN:-vps-12149520.vps.ovh.ca}"
if [ -n "${ENABLE_HTTPS:-}" ]; then
  log "Setting up nginx + Let's Encrypt TLS for $DOMAIN (stream)..."
  apt-get install -y nginx certbot python3-certbot-nginx
  cat >/etc/nginx/sites-available/fl1nt <<EOF
server {
  listen 80;
  server_name $DOMAIN;
  location / {
    proxy_pass http://127.0.0.1:8000/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host \$host;
    proxy_read_timeout 86400;
  }
}
EOF
  ln -sf /etc/nginx/sites-available/fl1nt /etc/nginx/sites-enabled/fl1nt
  rm -f /etc/nginx/sites-enabled/default
  nginx -t && systemctl restart nginx
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "${EMAIL:-admin@$DOMAIN}" --redirect || \
    echo "  certbot failed (check ports 80/443 open + DNS). Stream will stay http until fixed."
  STREAM_BASE="https://$DOMAIN"
fi

log "Starting orchestrator API on :9000..."
cd "$(dirname "$0")"
python3 -m venv .venv && . .venv/bin/activate
pip install -q -r requirements.txt
export MAX_PHONES="${MAX_PHONES:-12}"
export ROBLOX_APK_URL
export PHONE_PROXY="${PHONE_PROXY:-}"
export STREAM_BASE="${STREAM_BASE:-http://$(hostname -I | awk '{print $1}'):8000}"
export ORCHESTRATOR_TOKEN="${ORCHESTRATOR_TOKEN:-}"
pkill -f "uvicorn orchestrator:app" 2>/dev/null || true
nohup .venv/bin/uvicorn orchestrator:app --host 0.0.0.0 --port 9000 >/var/log/orchestrator.log 2>&1 &

sleep 2
echo -e "\n\033[1;32m========================================================"
echo    " orchestrator  -> http://$(hostname -I | awk '{print $1}'):9000/health"
echo    " ws-scrcpy     -> host :8000 (put behind nginx TLS at /stream)"
echo    " Next: set STREAM_BASE to your public https URL and re-run,"
echo    " then paste the orchestrator URL/token into the site (Server button)."
echo -e "========================================================\033[0m\n"
