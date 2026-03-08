# Hosting

## GitHub Pages (frontend) + Flask host (backend)

GitHub Pages can only host static files. This repo is set up to:

- host the frontend from `static/` via GitHub Pages
- host the Flask API (`/api/*`) on a separate Flask-capable host (e.g. Render)

### Frontend (GitHub Pages)

1. Push to `main`
2. In GitHub repo settings:
   - Settings → Pages → Source: **GitHub Actions**
3. Set your API base URL in `static/config.js`:

```js
window.RCD_API_BASE = "https://your-flask-service.onrender.com";
```

### Backend (Flask host, e.g. Render)

- Start command: `gunicorn app:app`
- CORS: set `RCD_CORS_ORIGINS` (comma-separated) to your GitHub Pages origin, e.g.

`RCD_CORS_ORIGINS=https://<your-user>.github.io`

If you’re using SQLite and need persistence, configure a persistent disk and set `RCD_DB` to that mounted path.

# River City Doubles

Richmond doubles squash league: box league and handicap league (open & main).

## Run the app

**Backend (Python/Flask):**

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open [http://localhost:5000](http://localhost:5000). The Flask app serves the UI and stores scores in a SQLite database (`scores.db` in the project root, or path in `RCD_DB`).

**Syncing with the hosted site:** Local and hosted each have their own database. To copy hosted data to local, run `python pull_from_hosted.py --host https://river-city-doubles.onrender.com`. To push your local score/schedule updates to the hosted site, run `python push_to_hosted.py --host https://river-city-doubles.onrender.com`.

**Why aren’t scores updated (on the hosted site)?** Common causes: (1) **Different databases** — local and hosted don’t share data; push with `push_to_hosted.py` after local changes. (2) **Hosted DB is ephemeral** — On Render’s free tier the app filesystem (and `scores.db`) is usually wiped on every deploy or service restart, so pushed data can disappear. To keep scores on the hosted site, configure a [persistent disk](https://render.com/docs/disks) on Render and set `RCD_DB` to the mounted path (e.g. `/data/scores.db`). Then push again after any restart.

## Features

- **Home** — Short description of the league (box vs handicap).
- **Input Score** — Submit a match: league (box/handicap), level (open/main), week, optional handicap, both team names, and games won (best of 5). Submitting sends you to Rankings.
- **Rankings** — Handicap Open and Handicap Main. Points: 1 for playing, 1 for winning the match, 1 per game won. Data is stored in SQLite.

## API

- `POST /api/scores` — Submit a score (JSON: league, level, week, team1, team2, games1, games2; optional handicap).
- `GET /api/rankings/<league>/<level>` — Get rankings (e.g. `/api/rankings/handicap/open`).
