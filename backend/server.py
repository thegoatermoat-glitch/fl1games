from fastapi import FastAPI, APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import json
import logging
import httpx
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
