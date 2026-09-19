from fastapi import FastAPI, APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import json
import logging
import asyncio
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="fl1nt g4m3s API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# shared async http client for proxying game html
http_client: Optional[httpx.AsyncClient] = None

# ---------- GeeLark cloud-phone config ----------
GEELARK_BASE = "https://openapi.geelark.com/open/v1"
GEELARK_TOKEN = os.environ.get("GEELARK_API_TOKEN", "").strip()
GEELARK_APP_ID = os.environ.get("GEELARK_APP_ID", "").strip()
GEELARK_PHONE_ID = os.environ.get("GEELARK_PHONE_ID", "").strip()
GEELARK_ROBLOX_PKG = os.environ.get("GEELARK_ROBLOX_PKG", "").strip()
CLOUDPHONE_BRIDGE_URL = os.environ.get("CLOUDPHONE_BRIDGE_URL", "").strip().rstrip("/")


async def geelark_post(path: str, body: dict) -> dict:
    """Call a GeeLark OpenAPI endpoint using key-based signature auth."""
    if not GEELARK_TOKEN or not GEELARK_APP_ID:
        raise HTTPException(status_code=503, detail="GeeLark appId/apiKey not configured")
    assert http_client is not None
    import uuid as _uuid, time as _time, hashlib as _hashlib
    ts = str(int(_time.time() * 1000))
    nonce = _uuid.uuid4().hex[:6]
    trace = _uuid.uuid4().hex
    sign = _hashlib.sha256(f"{GEELARK_APP_ID}{trace}{ts}{nonce}{GEELARK_TOKEN}".encode()).hexdigest().upper()
    headers = {
        "Content-Type": "application/json",
        "appId": GEELARK_APP_ID,
        "traceId": trace,
        "ts": ts,
        "nonce": nonce,
        "sign": sign,
    }
    resp = await http_client.post(f"{GEELARK_BASE}{path}", json=body, headers=headers)
    try:
        data = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail=f"GeeLark bad response ({resp.status_code})")
    if isinstance(data, dict) and data.get("code") not in (0, None):
        logger.warning(f"GeeLark {path} code={data.get('code')} msg={data.get('msg')}")
    return data


class Game(BaseModel):
    slug: str
    name: str
    category: str
    colorA: str
    colorB: str
    monogram: str
    image: Optional[str] = None
    type: str = "embed"
    target: Optional[str] = None
    provider: Optional[str] = None
    appPackage: Optional[str] = None
    appName: Optional[str] = None


class GameListResponse(BaseModel):
    total: int
    games: List[Game]


@api_router.get("/")
async def root():
    return {"message": "fl1nt g4m3s api online"}


@api_router.get("/games", response_model=GameListResponse)
async def list_games(
    q: Optional[str] = None,
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(default=60, le=400),
):
    query: dict = {}
    if q:
        query["name"] = {"$regex": q.strip(), "$options": "i"}
    if category and category.lower() != "all":
        query["category"] = category
    total = await db.games.count_documents(query)
    cursor = db.games.find(query, {"_id": 0}).sort("name", 1).skip(skip).limit(limit)
    games = await cursor.to_list(length=limit)
    return {"total": total, "games": games}


@api_router.get("/categories")
async def get_categories():
    cats = await db.games.distinct("category")
    counts = []
    for c in sorted(cats):
        n = await db.games.count_documents({"category": c})
        counts.append({"name": c, "count": n})
    total = await db.games.count_documents({})
    return {"total": total, "categories": counts}


@api_router.get("/games/{slug}", response_model=Game)
async def get_game(slug: str):
    game = await db.games.find_one({"slug": slug}, {"_id": 0})
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


@api_router.get("/games/{slug}/play")
async def play_game(slug: str):
    """Stream the game's self-contained HTML through our backend as text/html."""
    game = await db.games.find_one({"slug": slug})
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    raw_url = game["raw_url"]

    async def stream():
        assert http_client is not None
        async with http_client.stream("GET", raw_url) as resp:
            if resp.status_code != 200:
                yield b"<h1 style='font-family:sans-serif;color:#fff;background:#0d0d12'>G4m3 temporarily unavailable</h1>"
                return
            async for chunk in resp.aiter_bytes(chunk_size=65536):
                yield chunk

    return StreamingResponse(
        stream(),
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ---------- Cloud phone (GeeLark + ws-scrcpy bridge) ----------
class StartPhoneRequest(BaseModel):
    phoneId: Optional[str] = None


@api_router.get("/cloudphone/config")
async def cloudphone_config():
    return {
        "geelarkConfigured": bool(GEELARK_TOKEN and GEELARK_APP_ID),
        "apiKeyPresent": bool(GEELARK_TOKEN),
        "appIdPresent": bool(GEELARK_APP_ID),
        "bridgeConfigured": bool(CLOUDPHONE_BRIDGE_URL),
        "phoneIdConfigured": bool(GEELARK_PHONE_ID),
        "robloxPkg": GEELARK_ROBLOX_PKG or None,
    }


@api_router.post("/cloudphone/phones")
async def cloudphone_phones():
    """List GeeLark cloud phones so the correct phone id can be selected."""
    data = await geelark_post("/phone/list", {"page": 1, "pageSize": 100})
    items = (data.get("data") or {}).get("items") or []
    phones = [{"id": p.get("id"), "name": p.get("serialName") or p.get("name"),
               "openStatus": p.get("openStatus")} for p in items]
    return {"phones": phones, "raw_code": data.get("code"), "msg": data.get("msg")}


async def _resolve_phone_id(requested: Optional[str]) -> str:
    pid = (requested or GEELARK_PHONE_ID or "").strip()
    if pid:
        return pid
    data = await geelark_post("/phone/list", {"page": 1, "pageSize": 1})
    items = (data.get("data") or {}).get("items") or []
    if not items:
        raise HTTPException(status_code=400, detail="No GeeLark cloud phones found on this account")
    return items[0].get("id")


@api_router.post("/cloudphone/start")
async def cloudphone_start(req: StartPhoneRequest):
    phone_id = await _resolve_phone_id(req.phoneId)

    start = await geelark_post("/phone/start", {"ids": [phone_id]})
    details = (start.get("data") or {}).get("successDetails") or []
    if not details:
        raise HTTPException(status_code=502, detail=f"GeeLark could not start the phone: {start.get('msg')}")
    remote_url = details[0].get("url")

    # optionally auto-launch Roblox once the phone is up
    if GEELARK_ROBLOX_PKG:
        try:
            await geelark_post("/phone/app/start", {"id": phone_id, "packageName": GEELARK_ROBLOX_PKG})
        except Exception as e:
            logger.warning(f"roblox app start failed: {e}")

    return {
        "phoneId": phone_id,
        "streamUrl": remote_url,
        "remoteUrl": remote_url,
    }


@api_router.post("/cloudphone/stop")
async def cloudphone_stop(req: StartPhoneRequest):
    phone_id = await _resolve_phone_id(req.phoneId)
    await geelark_post("/phone/stop", {"ids": [phone_id]})
    return {"stopped": True, "phoneId": phone_id}


@api_router.get("/cloudphone/status")
async def cloudphone_status(phoneId: Optional[str] = None):
    phone_id = await _resolve_phone_id(phoneId)
    data = await geelark_post("/phone/status", {"ids": [phone_id]})
    return {"phoneId": phone_id, "data": data.get("data"), "code": data.get("code")}


# ---------- Cloud phone session manager (30-min sessions, 20 slots, queue) ----------
MAX_SLOTS = 20
SESSION_SECONDS = 30 * 60      # 30 minutes per session
HEARTBEAT_TIMEOUT = 45         # seconds without heartbeat -> session dropped

_cloud_lock = asyncio.Lock()
GEELARK_MOBILE_TYPE = os.environ.get("GEELARK_MOBILE_TYPE", "Android 12").strip()
PHONE_BOOT_TIMEOUT = 220        # seconds to wait for the phone to reach running state
APP_INSTALL_TIMEOUT = 420       # seconds to wait for a team app to finish installing
_proxy_cache = {"list": [], "idx": 0}


class SessionReq(BaseModel):
    clientId: str
    appPackage: Optional[str] = None
    appName: Optional[str] = None


async def _get_proxy_info():
    """Round-robin a proxy URL from the account's proxy list (required to create phones)."""
    if not _proxy_cache["list"]:
        r = await geelark_post("/proxy/list", {"page": 1, "pageSize": 50})
        _proxy_cache["list"] = (r.get("data") or {}).get("list") or []
    lst = _proxy_cache["list"]
    if not lst:
        return None
    p = lst[_proxy_cache["idx"] % len(lst)]
    _proxy_cache["idx"] += 1
    return f'{p["scheme"]}://{p["username"]}:{p["password"]}@{p["server"]}:{p["port"]}'


async def _create_and_start_phone(client_id: str):
    """Create a brand-new cloud phone for this user, start it, return (phoneId, viewerUrl)."""
    proxy = await _get_proxy_info()
    row = {"profileName": f"fl1nt-{client_id[:12]}"}
    if proxy:
        row["proxyInformation"] = proxy
    created = await geelark_post("/phone/addNew", {
        "mobileType": GEELARK_MOBILE_TYPE,
        "chargeMode": 0,
        "data": [row],
    })
    details = (created.get("data") or {}).get("details") or []
    if not details or not details[0].get("id"):
        emsg = details[0].get("msg") if details else created.get("msg")
        raise RuntimeError(f"addNew failed: {emsg}")
    phone_id = details[0]["id"]
    start = await geelark_post("/phone/start", {"ids": [phone_id]})
    sdetails = (start.get("data") or {}).get("successDetails") or []
    url = sdetails[0].get("url") if sdetails else None
    return phone_id, url


async def _destroy_phone(phone_id: str):
    if not phone_id:
        return
    try:
        await geelark_post("/phone/stop", {"ids": [phone_id]})
    except Exception as e:
        logger.warning(f"phone stop failed {phone_id}: {e}")
    try:
        await geelark_post("/phone/delete", {"ids": [phone_id]})
    except Exception as e:
        logger.warning(f"phone delete failed {phone_id}: {e}")


async def _resolve_upload_app(phone_id: str, app_package: str, app_name: Optional[str]):
    """Find a user-uploaded team app by packageName; return (appVersionId, installStatus)."""
    res = await geelark_post("/app/installable/list", {
        "name": app_name or "", "envId": phone_id, "getUploadApp": True, "page": 1, "pageSize": 100})
    items = (res.get("data") or {}).get("items") or []
    for it in items:
        if it.get("packageName") == app_package:
            vers = it.get("appVersionInfoList") or []
            if vers:
                return vers[0].get("id"), vers[0].get("installStatus")
    return None, None


async def _wait_phone_running(phone_id: str, timeout: int) -> bool:
    import time as _t
    deadline = _t.time() + timeout
    while _t.time() < deadline:
        stat = await geelark_post("/phone/status", {"ids": [phone_id]})
        sd = (stat.get("data") or {}).get("successDetails") or [{}]
        if sd[0].get("status") == 0:   # 0 = running
            return True
        await asyncio.sleep(5)
    return False


async def _set_app_status(client_id: str, status: str):
    await db.cloud_sessions.update_one({"clientId": client_id}, {"$set": {"appStatus": status}})


async def _provision_app(client_id: str, phone_id: str, app_package: str, app_name: Optional[str]):
    """Background: wait for boot, install the team app if needed, then launch it."""
    import time as _t
    try:
        await _set_app_status(client_id, "preparing")
        if not await _wait_phone_running(phone_id, PHONE_BOOT_TIMEOUT):
            await _set_app_status(client_id, "failed")
            return
        version_id, install_status = await _resolve_upload_app(phone_id, app_package, app_name)
        if not version_id:
            logger.warning(f"team app not found for {app_package}")
            await _set_app_status(client_id, "failed")
            return
        if install_status != 1:   # 1 = installed
            await _set_app_status(client_id, "installing")
            await geelark_post("/app/install", {"envId": phone_id, "appVersionId": version_id})
            deadline = _t.time() + APP_INSTALL_TIMEOUT
            installed = False
            while _t.time() < deadline:
                await asyncio.sleep(6)
                _, st = await _resolve_upload_app(phone_id, app_package, app_name)
                if st == 1:
                    installed = True
                    break
                if st == 2:   # install failed
                    break
            if not installed:
                await _set_app_status(client_id, "failed")
                return
        await _set_app_status(client_id, "launching")
        await geelark_post("/app/start", {"envId": phone_id, "packageName": app_package})
        await _set_app_status(client_id, "ready")
    except Exception as e:
        logger.warning(f"provision app failed for {client_id}: {e}")
        try:
            await _set_app_status(client_id, "failed")
        except Exception:
            pass


async def _drop_sessions(query: dict):
    """Delete session docs matching query, tearing down each user's dedicated phone."""
    docs = await db.cloud_sessions.find(query).to_list(1000)
    for d in docs:
        if d.get("phoneId"):
            await _destroy_phone(d["phoneId"])
    if docs:
        await db.cloud_sessions.delete_many({"clientId": {"$in": [d["clientId"] for d in docs]}})


async def _reconcile():
    now = datetime.utcnow()
    hb_cutoff = now - timedelta(seconds=HEARTBEAT_TIMEOUT)
    exp_cutoff = now - timedelta(seconds=SESSION_SECONDS)
    # tear down abandoned (no recent heartbeat) and expired active sessions (+ their phones)
    await _drop_sessions({"lastSeen": {"$lt": hb_cutoff}})
    await _drop_sessions({"status": "active", "startedAt": {"$lt": exp_cutoff}})
    # promote queued -> active while slots are free (FIFO); phone is created lazily in _status_for
    active = await db.cloud_sessions.count_documents({"status": "active"})
    if active < MAX_SLOTS:
        need = MAX_SLOTS - active
        queued = await db.cloud_sessions.find({"status": "queued"}).sort("joinedAt", 1).limit(need).to_list(need)
        for q in queued:
            await db.cloud_sessions.update_one(
                {"clientId": q["clientId"]},
                {"$set": {"status": "active", "startedAt": now, "urlIssued": False}})


async def _status_for(client_id: str) -> dict:
    sess = await db.cloud_sessions.find_one({"clientId": client_id})
    if not sess:
        return {"status": "none", "maxSlots": MAX_SLOTS}
    if sess["status"] == "queued":
        pos = await db.cloud_sessions.count_documents(
            {"status": "queued", "joinedAt": {"$lt": sess["joinedAt"]}}) + 1
        active = await db.cloud_sessions.count_documents({"status": "active"})
        return {"status": "queued", "position": pos, "activeCount": active, "maxSlots": MAX_SLOTS}
    # active
    started = sess.get("startedAt") or datetime.utcnow()
    remaining = max(0, int(SESSION_SECONDS - (datetime.utcnow() - started).total_seconds()))
    resp = {"status": "active", "remainingSeconds": remaining, "maxSlots": MAX_SLOTS}
    if not sess.get("urlIssued"):
        try:
            phone_id, url = await _create_and_start_phone(client_id)
            set_fields = {"urlIssued": True, "phoneId": phone_id}
            if sess.get("appPackage"):
                set_fields["appStatus"] = "preparing"
            await db.cloud_sessions.update_one(
                {"clientId": client_id}, {"$set": set_fields})
            if url:
                resp["streamUrl"] = url
            if sess.get("appPackage"):
                asyncio.create_task(
                    _provision_app(client_id, phone_id, sess["appPackage"], sess.get("appName")))
        except Exception as e:
            logger.warning(f"create/start phone failed: {e}")
            resp["error"] = "Could not create a new cl0ud phone."
    if sess.get("appPackage"):
        resp["appName"] = sess.get("appName")
        resp["appStatus"] = resp.get("appStatus") or sess.get("appStatus") or "preparing"
    return resp


@api_router.post("/cloudphone/session/join")
async def session_join(req: SessionReq):
    async with _cloud_lock:
        now = datetime.utcnow()
        existing = await db.cloud_sessions.find_one({"clientId": req.clientId})
        if not existing:
            await db.cloud_sessions.insert_one(
                {"clientId": req.clientId, "status": "queued", "joinedAt": now, "lastSeen": now,
                 "appPackage": req.appPackage, "appName": req.appName})
        else:
            await db.cloud_sessions.update_one({"clientId": req.clientId}, {"$set": {"lastSeen": now}})
        await _reconcile()
        return await _status_for(req.clientId)


@api_router.post("/cloudphone/session/heartbeat")
async def session_heartbeat(req: SessionReq):
    async with _cloud_lock:
        await db.cloud_sessions.update_one({"clientId": req.clientId}, {"$set": {"lastSeen": datetime.utcnow()}})
        await _reconcile()
        return await _status_for(req.clientId)


@api_router.post("/cloudphone/session/leave")
async def session_leave(req: SessionReq):
    async with _cloud_lock:
        await _drop_sessions({"clientId": req.clientId})
        await _reconcile()
        return {"left": True}


@api_router.get("/cloudphone/session/stats")
async def session_stats():
    active = await db.cloud_sessions.count_documents({"status": "active"})
    queued = await db.cloud_sessions.count_documents({"status": "queued"})
    return {"active": active, "queued": queued, "maxSlots": MAX_SLOTS, "sessionSeconds": SESSION_SECONDS}




async def seed_games():
    seed_path = ROOT_DIR / "games_seed.json"
    if not seed_path.exists():
        logger.warning("games_seed.json not found; skipping seed")
        return
    with open(seed_path, "r") as f:
        seed = json.load(f)
    existing = await db.games.count_documents({})
    sample = await db.games.find_one({})
    if existing == len(seed) and sample and "type" in sample:
        logger.info(f"games already seeded ({existing})")
        return
    await db.games.delete_many({})
    if seed:
        await db.games.insert_many(seed)
    await db.games.create_index("slug", unique=True)
    await db.games.create_index("name")
    await db.games.create_index("category")
    logger.info(f"seeded {len(seed)} games")


@app.on_event("startup")
async def startup():
    global http_client
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0),
                                    follow_redirects=True)
    await seed_games()


@app.on_event("shutdown")
async def shutdown():
    if http_client:
        await http_client.aclose()
    client.close()


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
