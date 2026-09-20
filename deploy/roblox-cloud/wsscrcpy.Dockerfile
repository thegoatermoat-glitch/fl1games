# Browser streaming client for redroid (ws-scrcpy: H.264 over WebSocket + touch input).
# NOTE: ws-scrcpy streams via WebSocket/WebCodecs, which is the practical, working
# browser client for redroid. A pure-WebRTC path would need an extra SFU/gateway.
FROM node:20-bullseye

RUN apt-get update && apt-get install -y android-tools-adb git && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone --depth=1 https://github.com/NetrisTV/ws-scrcpy.git
WORKDIR /opt/ws-scrcpy
RUN npm install && npm run dist

# Connect to the redroid container over ADB, then serve the web client on :8000
CMD bash -lc 'adb start-server && \
  until adb connect ${REDROID_ADB:-redroid:5555} | grep -q connected; do sleep 3; done && \
  npm start'
