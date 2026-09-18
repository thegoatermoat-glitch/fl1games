# ws-scrcpy streaming server (NetrisTV/ws-scrcpy) + adb
# node:20-bookworm already ships git + curl, so we only add build tools + unzip + adb.
FROM node:20-bookworm

RUN apt-get update && apt-get install -y python3 build-essential unzip \
 && curl -Lo /tmp/pt.zip https://dl.google.com/android/repository/platform-tools-latest-linux.zip \
 && unzip -q /tmp/pt.zip -d /opt \
 && ln -s /opt/platform-tools/adb /usr/local/bin/adb \
 && rm -f /tmp/pt.zip \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone --depth 1 https://github.com/NetrisTV/ws-scrcpy.git \
 && cd ws-scrcpy && npm install && npm run dist

WORKDIR /opt/bridge
COPY package.json ./
RUN npm install
COPY bridge-server.js ./

EXPOSE 8080
CMD adb start-server \
 && (cd /opt/ws-scrcpy && node dist/index.js &) \
 && node bridge-server.js
