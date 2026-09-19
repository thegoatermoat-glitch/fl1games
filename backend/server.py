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
_phone_started = {"on": False}


class SessionReq(BaseModel):
    clientId: str


async def _ensure_phone_started():
    phone_id = await _resolve_phone_id(None)
    start = await geelark_post("/phone/start", {"ids": [phone_id]})
    details = (start.get("data") or {}).get("successDetails") or []
    _phone_started["on"] = True
    return details[0].get("url") if details else None


async def _ensure_phone_stopped():
    if not _phone_started["on"]:
        return
    try:
        phone_id = await _resolve_phone_id(None)
        await geelark_post("/phone/stop", {"ids": [phone_id]})
    except Exception as e:
        logger.warning(f"phone stop failed: {e}")
    finally:
        _phone_started["on"] = False


async def _reconcile():
    now = datetime.utcnow()
    hb_cutoff = now - timedelta(seconds=HEARTBEAT_TIMEOUT)
    exp_cutoff = now - timedelta(seconds=SESSION_SECONDS)
    # drop abandoned (no recent heartbeat) and expired active sessions
    await db.cloud_sessions.delete_many({"lastSeen": {"$lt": hb_cutoff}})
    await db.cloud_sessions.delete_many({"status": "active", "startedAt": {"$lt": exp_cutoff}})
    # promote queued -> active while slots are free (FIFO)
    active = await db.cloud_sessions.count_documents({"status": "active"})
    if active < MAX_SLOTS:
        need = MAX_SLOTS - active
        queued = await db.cloud_sessions.find({"status": "queued"}).sort("joinedAt", 1).limit(need).to_list(need)
        for q in queued:
            await db.cloud_sessions.update_one(
                {"clientId": q["clientId"]},
                {"$set": {"status": "active", "startedAt": now, "urlIssued": False}})
        active = await db.cloud_sessions.count_documents({"status": "active"})
    # lifecycle: stop the shared phone when nobody is active
    if active == 0 and _phone_started["on"]:
        await _ensure_phone_stopped()


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
            url = await _ensure_phone_started()
            await db.cloud_sessions.update_one({"clientId": client_id}, {"$set": {"urlIssued": True}})
            if url:
                resp["streamUrl"] = url
        except Exception as e:
            logger.warning(f"issue url failed: {e}")
    return resp


@api_router.post("/cloudphone/session/join")
async def session_join(req: SessionReq):
    async with _cloud_lock:
        now = datetime.utcnow()
        existing = await db.cloud_sessions.find_one({"clientId": req.clientId})
        if not existing:
            await db.cloud_sessions.insert_one(
                {"clientId": req.clientId, "status": "queued", "joinedAt": now, "lastSeen": now})
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
        await db.cloud_sessions.delete_one({"clientId": req.clientId})
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
