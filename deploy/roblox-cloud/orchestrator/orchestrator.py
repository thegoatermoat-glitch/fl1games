"""
fl1nt g4m3s - OVH redroid pool orchestrator.

Runs on your OVH VPS. Exposes a tiny HTTP API the website calls to allocate/free
one redroid Android phone per user (max MAX_PHONES). Each phone auto-installs the
merged Roblox APK and launches it; the browser stream is served by ws-scrcpy.

Endpoints:
  POST /allocate {clientId}   -> 200 {id, streamUrl}  | 503 if pool full
  POST /release  {id}         -> 200 {ok:true}
  GET  /health                -> {max, active, free}

Run: uvicorn orchestrator:app --host 0.0.0.0 --port 9000
"""
import os, subprocess, threading, time, platform
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

MAX_PHONES   = int(os.environ.get("MAX_PHONES", "12"))
ADB_BASE     = int(os.environ.get("ADB_BASE_PORT", "6000"))
ROBLOX_APK   = os.environ.get("ROBLOX_APK", "/opt/roblox/roblox_final.apk")
ROBLOX_URL   = os.environ.get("ROBLOX_APK_URL", "https://split-to-single.preview.emergentagent.com/api/download/roblox_final.apk")
ROBLOX_PKG   = os.environ.get("ROBLOX_PKG", "com.roblox.client")
STREAM_BASE  = os.environ.get("STREAM_BASE", "http://localhost:8000").rstrip("/")
TOKEN        = os.environ.get("ORCHESTRATOR_TOKEN", "")
DATA_ROOT    = os.environ.get("REDROID_DATA", "/root/redroid-pool")
SPLITS_DIR   = os.environ.get("ROBLOX_SPLITS_DIR", "/opt/roblox/splits")
PHONE_PROXY  = os.environ.get("PHONE_PROXY", "").strip()   # e.g. socks5://user:pass@host:port
GATEWAY_IMAGE = os.environ.get("GATEWAY_IMAGE", "fl1nt-proxy-gw")

def _image():
    env = os.environ.get("REDROID_IMAGE")
    if env:
        return env
    arch = platform.machine()
    if arch in ("x86_64", "amd64"):
        return "jj9011/redroid:11.0.0-houdini"     # ARM translation for Roblox on Intel/AMD
    return "redroid/redroid:11.0.0-latest"          # native ARM

IMAGE = _image()
app = FastAPI(title="fl1nt redroid orchestrator")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_lock = threading.Lock()
_slots = {}   # slot(int) -> {"id","clientId","adb","ready"}


class AllocReq(BaseModel):
    clientId: str

class ReleaseReq(BaseModel):
    id: str


def sh(*args, timeout=120):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def _adb(addr, *args, timeout=180):
    return sh("adb", "-s", addr, *args, timeout=timeout)


def _split_files():
    import platform
    arch = platform.machine()
    abi = "split_config.x86_64.apk" if arch in ("x86_64", "amd64") else "split_config.arm64_v8a.apk"
    files = []
    for name in ("base.apk", abi, "split_gmasdk.apk"):
        p = os.path.join(SPLITS_DIR, name)
        if os.path.exists(p):
            files.append(p)
    return files


def _provision(addr):
    """Wait for boot, install the Roblox splits, launch it. Runs in a thread."""
    deadline = time.time() + 240
    while time.time() < deadline:
        sh("adb", "connect", addr, timeout=20)
        r = _adb(addr, "shell", "getprop", "sys.boot_completed", timeout=20)
        if r.stdout.strip() == "1":
            break
        time.sleep(5)
    else:
        return
    splits = _split_files()
    if splits:
        _adb(addr, "install-multiple", "-r", "-g", *splits, timeout=400)
    _adb(addr, "shell", "monkey", "-p", ROBLOX_PKG, "-c", "android.intent.category.LAUNCHER", "1", timeout=30)


def _start_container(slot):
    name = f"fl1nt_phone_{slot}"
    gw = f"fl1nt_gw_{slot}"
    port = ADB_BASE + slot
    addr = f"127.0.0.1:{port}"
    sh("docker", "rm", "-f", name, timeout=60)
    sh("docker", "rm", "-f", gw, timeout=60)
    os.makedirs(f"{DATA_ROOT}/{slot}", exist_ok=True)

    redroid_net = []
    if PHONE_PROXY:
        # per-phone proxy gateway: tunnels ALL phone traffic (TCP+UDP) via the proxy.
        # redroid shares the gateway's netns, so the adb port is published on the gateway.
        sh("docker", "run", "-itd", "--rm", "--name", gw,
           "--cap-add", "NET_ADMIN", "--device", "/dev/net/tun",
           "-p", f"{addr}:5555",
           "-e", f"PROXY={PHONE_PROXY}",
           GATEWAY_IMAGE,
           timeout=120)
        time.sleep(3)  # let the tunnel come up
        redroid_net = ["--network", f"container:{gw}"]
    else:
        redroid_net = ["-p", f"{addr}:5555"]

    sh("docker", "run", "-itd", "--rm", "--privileged",
       "--name", name,
       *redroid_net,
       "-v", f"{DATA_ROOT}/{slot}:/data",
       IMAGE,
       "androidboot.redroid_width=720",
       "androidboot.redroid_height=1280",
       "androidboot.redroid_dpi=320",
       "androidboot.redroid_gpu_mode=guest",
       timeout=120)
    # wait until adb is reachable so ws-scrcpy can see the device
    for _ in range(24):
        sh("adb", "connect", addr, timeout=20)
        r = _adb(addr, "get-state", timeout=20)
        if "device" in r.stdout:
            break
        time.sleep(5)
    threading.Thread(target=_provision, args=(addr,), daemon=True).start()
    return name, addr


def _stream_url(addr):
    return f"{STREAM_BASE}/#!action=stream&udid={addr}&player=broadway"


def _auth(token):
    if TOKEN and token != TOKEN:
        raise HTTPException(status_code=401, detail="bad token")


@app.post("/allocate")
def allocate(req: AllocReq, x_orchestrator_token: str = Header(default="")):
    _auth(x_orchestrator_token)
    with _lock:
        # reuse if this client already holds a phone
        for slot, s in _slots.items():
            if s["clientId"] == req.clientId:
                return {"id": s["id"], "streamUrl": _stream_url(s["adb"])}
        free = next((i for i in range(MAX_PHONES) if i not in _slots), None)
        if free is None:
            raise HTTPException(status_code=503, detail="pool full")
        _slots[free] = {"id": f"fl1nt_phone_{free}", "clientId": req.clientId, "adb": "", "ready": False}
    name, addr = _start_container(free)
    with _lock:
        _slots[free]["adb"] = addr
        _slots[free]["ready"] = True
    return {"id": name, "streamUrl": _stream_url(addr)}


@app.post("/release")
def release(req: ReleaseReq, x_orchestrator_token: str = Header(default="")):
    _auth(x_orchestrator_token)
    with _lock:
        slot = next((i for i, s in _slots.items() if s["id"] == req.id), None)
        if slot is not None:
            _slots.pop(slot, None)
    sh("docker", "rm", "-f", req.id, timeout=60)
    if slot is not None:
        sh("docker", "rm", "-f", f"fl1nt_gw_{slot}", timeout=60)
    return {"ok": True}


@app.get("/health")
def health():
    with _lock:
        active = len(_slots)
    return {"max": MAX_PHONES, "active": active, "free": MAX_PHONES - active, "image": IMAGE}
