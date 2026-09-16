# Deploying fl1nt g4m3s to Render

This app has three parts:
- **Backend** – FastAPI service that serves the games API and proxies each game's HTML.
- **Frontend** – React static site (the fl1nt g4m3s UI + the `/cloud/` proxy launcher).
- **MongoDB** – stores the 300+ game catalogue (Render has no managed Mongo, use **MongoDB Atlas** free tier).

## 1. Create a MongoDB (Atlas)
1. Create a free cluster at https://www.mongodb.com/atlas .
2. Add a database user and allow network access from `0.0.0.0/0`.
3. Copy the connection string, e.g. `mongodb+srv://user:pass@cluster.xxxx.mongodb.net/?retryWrites=true&w=majority`.

## 2. Deploy with the Blueprint
1. Push this repo to GitHub.
2. In Render: **New +** -> **Blueprint** -> select the repo. Render reads `render.yaml`.
3. It creates two services: `fl1nt-games-api` and `fl1nt-games-web`.

## 3. Set environment variables
**fl1nt-games-api**
- `MONGO_URL` = your Atlas connection string
- `DB_NAME` = `fl1nt_games` (already defaulted)
- `CORS_ORIGINS` = `*` (or your web URL)

On first boot the backend auto-seeds all games from `backend/games_seed.json`.

**fl1nt-games-web**
- `REACT_APP_BACKEND_URL` = the public URL of `fl1nt-games-api` (e.g. `https://fl1nt-games-api.onrender.com`)

After setting `REACT_APP_BACKEND_URL`, trigger a redeploy of the web service (React bakes env vars at build time).

## 4. Verify
- `https://<api>.onrender.com/api/games` returns the catalogue.
- The website loads the grid, search works, and games open in the modal.

## Notes
- The `/cloud/` folder (Scramjet proxy + Wisp transport) is served as static files. Cloud gaming (Roblox / Fortnite) tunnels through the Emergent Wisp servers; those external platforms may require a login and may not fully stream through a proxy.
- Render free web services sleep after inactivity; the first request after idle can be slow.
