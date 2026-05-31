# MD Creator — Tasks

## Completed
- [x] FastAPI backend with markitdown conversion API
- [x] Upload UI with drag-and-drop, copy, and download
- [x] Zero-storage: in-memory conversion only, no disk/database

## Verified locally
- Health check and file conversion API working on port 8000

## Next (optional)
- [ ] Deploy to Render.com (connect GitHub repo, use render.yaml)
- [ ] Add URL input for YouTube links (markitdown supports this)
- [ ] Add rate limiting for production

## Deploy options

### Vercel (free, fast CDN — recommended for quick launch)
1. Push repo to GitHub
2. Go to [vercel.com/new](https://vercel.com/new) → Import repo
3. Framework preset: **Other** (Vercel auto-detects FastAPI via `main.py`)
4. Deploy — done. URL like `https://md-creator.vercel.app`

**Vercel limits:**
| Limit | Free tier |
|-------|-----------|
| Max upload | **4 MB** (Vercel hard cap ~4.5 MB) |
| Function timeout | 10s (Hobby) / 60s (Pro) |
| Cold start | ~3–8s first request (MarkItDown loads on demand) |
| Audio / Azure formats | Not included (lighter bundle) |

### Render.com (free, better for large files)
1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Blueprint → connect repo
3. Render reads `render.yaml` and deploys automatically
4. Free tier: 750 hrs/month, spins down after 15 min idle (~30s cold start)

### Option 2: Run locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Open http://localhost:8000

### Option 3: Docker
```bash
docker compose up --build
```
