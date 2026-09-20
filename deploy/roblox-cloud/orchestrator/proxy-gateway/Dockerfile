FROM alpine:3.19
RUN apk add --no-cache iproute2 iptables bash curl unzip bind-tools
ARG TUN2SOCKS_VER=v2.5.2
RUN set -eux; arch="$(uname -m)"; \
    case "$arch" in \
      x86_64)  f=linux-amd64 ;; \
      aarch64) f=linux-arm64 ;; \
      *) echo "unsupported arch $arch"; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/t2s.zip "https://github.com/xjasonlyu/tun2socks/releases/download/${TUN2SOCKS_VER}/tun2socks-${f}.zip"; \
    unzip /tmp/t2s.zip -d /tmp; \
    mv "/tmp/tun2socks-${f}" /usr/local/bin/tun2socks; \
    chmod +x /usr/local/bin/tun2socks; \
    rm -f /tmp/t2s.zip
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
