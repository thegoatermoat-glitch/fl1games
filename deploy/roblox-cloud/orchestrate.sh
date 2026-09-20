#!/usr/bin/env bash
# End-to-end redroid + browser-stream orchestrator for an OVH Ubuntu 22.04 VPS.
# Run as root:  sudo ./orchestrate.sh /path/to/Roblox.apkm
set -euo pipefail

APKM="${1:-$(ls ./*.apkm 2>/dev/null | head -1 || true)}"
WORK="$(pwd)/roblox-workspace"
SPLITS="$WORK/splits"
PORT_WEB=8080
PKG="com.roblox.client"

log(){ echo -e "\n\033[1;36m[orchestrate]\033[0m $*"; }
die(){ echo -e "\n\033[1;31m[fatal]\033[0m $*" >&2; exit 1; }

[ "$(id -u)" = "0" ] || die "run as root (sudo)."
[ -n "$APKM" ] && [ -f "$APKM" ] || die "no .apkm found. Pass it: sudo ./orchestrate.sh /path/Roblox.apkm"

# ---------------------------------------------------------------- 0. host deps
log "Installing host dependencies (docker, adb, unzip, jq, kernel modules)..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl unzip jq android-tools-adb \
  "linux-modules-extra-$(uname -r)" || true
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
docker compose version >/dev/null 2>&1 || apt-get install -y docker-compose-plugin

# ------------------------------------------------------ 1. kernel binder/ashmem
log "Loading Android kernel modules (binder/ashmem)..."
modprobe binder_linux devices="binder,hwbinder,vndbinder" || true
modprobe ashmem_linux || echo "  ashmem_linux not present (kernel 5.18+ uses memfd - usually fine)"
printf "binder_linux\nashmem_linux\n" > /etc/modules-load.d/redroid.conf
dmesg -T 2>/dev/null | grep -i binder | tail -2 || true

# --------------------------------------------------------- 2. architecture pick
ARCH="$(uname -m)"
if [ "$ARCH" = "x86_64" ] || [ "$ARCH" = "amd64" ]; then
  REDROID_IMAGE="jj9011/redroid:11.0.0-houdini"   # ARM translation for Roblox on Intel/AMD
  log "x86_64 host -> using $REDROID_IMAGE (houdini ARM translation)"
elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
  REDROID_IMAGE="redroid/redroid:11.0.0-latest"   # native ARM
  log "arm64 host -> using $REDROID_IMAGE (native ARM)"
else
  die "unsupported host arch: $ARCH"
fi
export REDROID_IMAGE

# ------------------------------------------------ 3. recode .apkm -> split apks
log "Recoding bundle: $APKM"
rm -rf "$WORK"; mkdir -p "$SPLITS"
APKS="$WORK/roblox.apks"

# Try to fetch a linux/amd64 'unapkm' release asset; fall back to plain unzip
# (.apkm is a zip; many are not encrypted and unzip directly into split apks).
UNAPKM_URL="$(curl -fsSL https://api.github.com/repos/MuntashirAkon/unapkm/releases/latest \
  | jq -r '.assets[]?.browser_download_url' \
  | grep -Ei 'linux.*(amd64|x86_64|x64)' | head -1 || true)"

if [ -n "$UNAPKM_URL" ]; then
  log "Downloading unapkm: $UNAPKM_URL"
  curl -fsSL "$UNAPKM_URL" -o "$WORK/unapkm" && chmod +x "$WORK/unapkm"
  log "Decrypting .apkm -> .apks"
  "$WORK/unapkm" "$APKM" "$APKS" 2>/dev/null || "$WORK/unapkm" -o "$APKS" "$APKM" || cp "$APKM" "$APKS"
else
  echo "  no linux unapkm binary published; treating .apkm as a plain zip"
  cp "$APKM" "$APKS"
fi

log "Unzipping split apks into $SPLITS"
unzip -o "$APKS" -d "$SPLITS" >/dev/null || unzip -o "$APKM" -d "$SPLITS" >/dev/null
find "$SPLITS" -maxdepth 3 -name '*.apk' -exec cp {} "$SPLITS/" \; 2>/dev/null || true
ls "$SPLITS"/*.apk >/dev/null 2>&1 || die "no .apk splits found after unzip (bundle may be encrypted; a working unapkm build is required)"
echo "  splits:"; ls -1 "$SPLITS"/*.apk

# -------------------------------------------------------- 4. bring up the stack
log "Starting redroid + web stream (docker compose)..."
docker compose -f "$(dirname "$0")/docker-compose.yml" up -d --build

log "Waiting for Android to finish booting (this can take 1-3 min)..."
adb kill-server >/dev/null 2>&1 || true
for i in $(seq 1 60); do
  adb connect 127.0.0.1:5555 >/dev/null 2>&1 || true
  BOOT="$(adb -s 127.0.0.1:5555 shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
  [ "$BOOT" = "1" ] && break
  sleep 5
done
[ "${BOOT:-0}" = "1" ] || die "Android did not boot; check: docker logs redroid"

# --------------------------------------------------- 5. adb multi-install Roblox
log "Sideloading Roblox via adb install-multiple..."
adb -s 127.0.0.1:5555 install-multiple -r -g "$SPLITS"/*.apk

# ---------------------------------------------------------------- 6. verify + URL
log "Verifying package registry..."
if adb -s 127.0.0.1:5555 shell pm list packages 2>/dev/null | grep -q "$PKG"; then
  IP="$(curl -fsS ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
  echo -e "\n\033[1;32m========================================================"
  echo    " ✅ $PKG installed. Open your browser and play:"
  echo    "     http://$IP:$PORT_WEB"
  echo -e "========================================================\033[0m\n"
else
  die "$PKG not found in registry after install."
fi
