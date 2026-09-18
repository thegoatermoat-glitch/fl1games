# ws-scrcpy streaming server (NetrisTV/ws-scrcpy) + adb
FROM node:18-bullseye

RUN apt-get update && apt-get install -y android-tools-adb git && rm -rf /var/lib/apt/lists/*

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
