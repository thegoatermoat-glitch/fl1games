// fl1nt cl0ud phone bridge
// Wraps ws-scrcpy so the fl1nt backend can (a) tell it to `adb connect` a GeeLark
// phone and (b) the browser can stream that phone. Public HTTP(S) entrypoint.
//
// Routes:
//   POST /connect   { address: "host:port" }  -> runs `adb connect host:port`
//   everything else -> proxied to the internal ws-scrcpy server (incl. WebSocket)

const express = require('express');
const httpProxy = require('http-proxy');
const { exec } = require('child_process');

const PORT = process.env.PORT || 8080;
const WS_SCRCPY = process.env.WS_SCRCPY_URL || 'http://127.0.0.1:8000';
// Comma-separated list of origins allowed to call /connect (your fl1nt backend origin)
const ALLOW = (process.env.ALLOW_ORIGIN || '*');

const app = express();
app.use(express.json());

app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', ALLOW);
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  if (req.method === 'OPTIONS') return res.sendStatus(204);
  next();
});

function run(cmd) {
  return new Promise((resolve) => {
    exec(cmd, { timeout: 20000 }, (err, stdout, stderr) => {
      resolve({ ok: !err, out: (stdout || '') + (stderr || '') });
    });
  });
}

app.post('/connect', async (req, res) => {
  const address = (req.body && req.body.address || '').trim();
  if (!address) return res.status(400).json({ error: 'address required' });
  // sanitize: host:port only
  if (!/^[a-zA-Z0-9._-]+:\d+$/.test(address)) {
    return res.status(400).json({ error: 'invalid address' });
  }
  const r = await run(`adb connect ${address}`);
  const list = await run('adb devices');
  res.json({ ok: r.ok, connect: r.out.trim(), devices: list.out.trim(), udid: address });
});

app.get('/health', (req, res) => res.json({ ok: true }));

// Proxy everything else to ws-scrcpy (HTTP + WebSocket upgrade)
const proxy = httpProxy.createProxyServer({ target: WS_SCRCPY, ws: true, changeOrigin: true });
proxy.on('error', (e, req, res) => {
  try { res.writeHead(502); res.end('bridge proxy error: ' + e.message); } catch (_) {}
});
app.use((req, res) => proxy.web(req, res));

const server = app.listen(PORT, () => console.log(`cl0ud bridge on :${PORT} -> ${WS_SCRCPY}`));
server.on('upgrade', (req, socket, head) => proxy.ws(req, socket, head));
