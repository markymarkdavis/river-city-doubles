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

- Start command on Render: `gunicorn --bind 0.0.0.0:$PORT app:app` (Render sets `PORT`). Locally, `python app.py` or `gunicorn app:app` is fine.
- CORS: set `RCD_CORS_ORIGINS` (comma-separated) to your GitHub Pages origin, e.g. `RCD_CORS_ORIGINS=https://<your-user>.github.io`

#### Persist database on Render (scores + email subscriptions)

SQLite lives in the file given by **`RCD_DB`** (default: `scores.db` next to `app.py`). On Render, the default app filesystem is **ephemeral** on the **Free** web tier (data can disappear on deploy or restart). To keep data across deploys:

1. **New deploy from this repo (recommended):** In the [Render Dashboard](https://dashboard.render.com), create a **Blueprint** from the repo and apply [`render.yaml`](render.yaml). It attaches a **persistent disk** at `/var/data`, sets **`RCD_DB=/var/data/scores.db`**, and uses the **Starter** plan (persistent disks are **not** offered on Free web services). Then set secrets such as `RCD_CORS_ORIGINS`, `RCD_RESEND_API_KEY`, and `RCD_CRON_SECRET` on that service.

2. **Existing web service:** Open the service → **Disks** → add a disk (e.g. 1 GB), mount path **`/var/data`** → **Environment** → add **`RCD_DB=/var/data/scores.db`** → upgrade off **Free** if the UI requires it for disks → **Manual Deploy**. Copy any existing data with `python push_to_hosted.py --host …` if the old instance still has the DB.

If you skip a disk and stay on Free, treat the hosted DB as **temporary** unless you use **Turso** (below).

3. **Turso (good for Render Free):** Create a database at [Turso](https://turso.tech/). Set **`TURSO_DATABASE_URL`** (the `libsql://…` URL from the dashboard) and **`TURSO_AUTH_TOKEN`** on your Render web service. The app uses the [`libsql`](https://pypi.org/project/libsql/) client and stores the same SQLite schema in Turso, so **deploys do not erase data**. The first HTTP request that touches the DB runs migrations; or run seed scripts locally with the same env vars—they call **`ensure_schema()`** / `init_db()` first so tables exist. Then: `python seed_schedule.py`, `python seed_main_schedule.py`, `python backfill_standings_from_schedule.py`.

   **Seeing your data:** Turso’s web UI is mostly connection strings, tokens, and metrics—not a full row browser. Open your database in the dashboard and use the **SQL console** (if your plan shows one), or use the CLI: `turso db shell <your-database-name>` then run `SELECT COUNT(*) FROM schedule;` and `SELECT COUNT(*) FROM scores;`. If counts are zero, confirm the URL/token in Render match this same database (easy to mix up two Turso DBs).

### Outbound email (notifications)

The app sends mail through **either** [Resend](https://resend.com) (HTTPS) **or** SMTP (e.g. SendGrid, Brevo). Set on the server:

| Variable | Purpose |
| -------- | ------- |
| `RCD_EMAIL_FROM` | **Recommended.** From address; Resend requires a verified domain/sender. If unset, a legacy default is used for SMTP only. |
| `RCD_RESEND_API_KEY` | If set, mail goes through Resend (no SMTP password needed). |
| `RCD_SMTP_PASS` | If Resend is not set, SMTP is used with this password. |
| `RCD_SMTP_HOST` | Optional; default `smtp.sendgrid.net`. |
| `RCD_SMTP_PORT` | Optional; default `587`. |
| `RCD_SMTP_USER` | Optional; default `apikey` (SendGrid). |
| `RCD_SMTP_SSL` | Set to `1` for implicit TLS (e.g. port 465). |

Optional: `RCD_NOTIFICATION_TEST_SECRET` — enables `POST /api/notifications/test-email` with JSON `{"secret":"…","to":"you@example.com"}` to verify delivery.

**Cron:** `RCD_CRON_SECRET` enables `POST /api/cron/notifications` (header `X-RCD-Cron` or JSON `secret`). The repo includes a GitHub Actions workflow that pings this daily; match reminders and standings also run when someone submits a handicap score.

**Render free tier: site “hangs” or times out**  
Free web services spin down after ~15 minutes of inactivity. The first request after that triggers a **cold start** (often 30–90 seconds), so the site can look like it’s hanging. Options:

1. **Wait it out** — Reload after 1–2 minutes; the instance will wake and then respond quickly.
2. **Keep the service awake** — Use a free uptime monitor (e.g. [UptimeRobot](https://uptimerobot.com)) to ping your site every 5–10 minutes. Add a monitor for `https://your-app.onrender.com/health`. The app exposes `/health` for this; it returns quickly and does no DB work. That way the service rarely sleeps and most visits are fast.

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

**Why aren’t scores updated (on the hosted site)?** Common causes: (1) **Different databases** — local and hosted don’t share data; push with `push_to_hosted.py` after local changes (that script targets the HTTP API, not Turso). (2) **Hosted DB is ephemeral** — On Render’s Free web tier the default SQLite file is wiped on deploy/restart; fix with a **persistent disk** + **`RCD_DB`**, or **`TURSO_DATABASE_URL`** + **`TURSO_AUTH_TOKEN`** (Turso), per **Persist database on Render** above.

## Features

- **Home** — Short description of the league (box vs handicap).
- **Input Score** — Submit a match: league (box/handicap), level (open/main), week, optional handicap, both team names, and games won (best of 5). Submitting sends you to Rankings.
- **Rankings** — Handicap Open and Handicap Main. Points: 1 for playing, 1 for winning the match, 1 per game won. Data is stored in SQLite.

## API

- `POST /api/scores` — Submit a score (JSON: league, level, week, team1, team2, games1, games2; optional handicap).
- `GET /api/rankings/<league>/<level>` — Get rankings (e.g. `/api/rankings/handicap/open`).
