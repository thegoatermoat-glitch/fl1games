#!/bin/bash
# Routes ALL traffic of this container (and any container sharing its netns, i.e. the
# redroid phone) through PROXY via a TUN device. Supports socks5:// and http:// proxies.
set -e
: "${PROXY:?set PROXY, e.g. socks5://user:pass@host:port}"

IFACE="$(ip route | awk '/^default/{print $5; exit}')"
ORIG_GW="$(ip route | awk '/^default/{print $3; exit}')"

# Resolve the proxy host so we can keep a direct route to it via the real gateway.
PROXY_HOSTPORT="${PROXY#*://}"          # strip scheme
PROXY_HOSTPORT="${PROXY_HOSTPORT##*@}"  # strip user:pass@
PROXY_HOST="${PROXY_HOSTPORT%%:*}"      # host
PROXY_IP="$(getent hosts "$PROXY_HOST" | awk '{print $1; exit}')"
[ -z "$PROXY_IP" ] && PROXY_IP="$PROXY_HOST"

echo "[gw] iface=$IFACE orig_gw=$ORIG_GW proxy_ip=$PROXY_IP"

# Keep a direct (non-tunnelled) route to the proxy endpoint.
ip route add "$PROXY_IP/32" via "$ORIG_GW" dev "$IFACE" 2>/dev/null || true

# Create TUN.
mkdir -p /dev/net
[ -e /dev/net/tun ] || mknod /dev/net/tun c 10 200
ip tuntap add mode tun dev tun0
ip addr add 198.18.0.1/15 dev tun0
ip link set tun0 up

# Start the tunnel (binds its own dialer to $IFACE to reach the proxy).
tun2socks -device tun0 -proxy "$PROXY" -interface "$IFACE" &
T2S=$!
sleep 2

# Send everything else through the tunnel.
ip route del default 2>/dev/null || true
ip route add default via 198.18.0.1 dev tun0

echo "[gw] tunnel up; all traffic -> $PROXY"
wait "$T2S"
