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

# ---- cache the merged Roblox APK ----
log "Downloading merged Roblox APK..."
mkdir -p /opt/roblox
ROBLOX_APK_URL="${ROBLOX_APK_URL:-https://split-to-single.preview.emergentagent.com/api/download/roblox_final.apk}"
curl -fL "$ROBLOX_APK_URL" -o /opt/roblox/roblox_final.apk
ls -lh /opt/roblox/roblox_final.apk

# ---- ws-scrcpy on the HOST (shares host adb with the orchestrator) ----
log "Setting up ws-scrcpy (browser stream) on host :8000..."
if [ ! -d /opt/ws-scrcpy ]; then
  git clone --depth=1 https://github.com/NetrisTV/ws-scrcpy.git /opt/ws-scrcpy
  ( cd /opt/ws-scrcpy && npm install && npm run dist )
fi
pkill -f "ws-scrcpy" 2>/dev/null || true
( cd /opt/ws-scrcpy && nohup npm start >/var/log/ws-scrcpy.log 2>&1 & )

# ---- proxy gateway image (only needed if PHONE_PROXY is set) ----
if [ -n "${PHONE_PROXY:-}" ]; then
  log "Building proxy gateway image (routes each phone through PHONE_PROXY)..."
  docker build -t fl1nt-proxy-gw "$(dirname "$0")/proxy-gateway"
  echo "  phones will tunnel through: ${PHONE_PROXY%%@*}@***"
fi

# ---- orchestrator (python) ----
log "Starting orchestrator API on :9000..."
cd "$(dirname "$0")"
python3 -m venv .venv && . .venv/bin/activate
pip install -q -r requirements.txt
export MAX_PHONES="${MAX_PHONES:-12}"
export ROBLOX_APK_URL
export PHONE_PROXY="${PHONE_PROXY:-}"
export STREAM_BASE="${STREAM_BASE:-https://YOUR_VPS_DOMAIN/stream}"
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
