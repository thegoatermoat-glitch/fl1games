# ws-scrcpy streaming server (NetrisTV/ws-scrcpy) + adb
FROM node:18-bullseye

# Install git + build tools, and Google's official platform-tools (adb) directly
# (the distro adb package name differs across Debian/Ubuntu, so we fetch it from Google)
RUN apt-get update && apt-get install -y git python3 build-essential curl unzip \
 && curl -Lo /tmp/pt.zip https://dl.google.com/android/repository/platform-tools-latest-linux.zip \
 && unzip -q /tmp/pt.zip -d /opt \
 && ln -s /opt/platform-tools/adb /usr/local/bin/adb \
 && rm -f /tmp/pt.zip \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
# ws-scrcpy streaming server (listens on 8000)
RUN git clone --depth 1 https://github.com/NetrisTV/ws-scrcpy.git \
 && cd ws-scrcpy && npm install && npm run dist

# our bridge wrapper (listens on 8080, proxies to 8000, adds /connect)
WORKDIR /opt/bridge
COPY package.json ./
RUN npm install
COPY bridge-server.js ./

EXPOSE 8080
# start adb server, ws-scrcpy, then the bridge wrapper
CMD adb start-server \
 && (cd /opt/ws-scrcpy && node dist/index.js &) \
 && node bridge-server.js
