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

## Features

- **Home** — Short description of the league (box vs handicap).
- **Input Score** — Submit a match: league (box/handicap), level (open/main), week, optional handicap, both team names, and games won (best of 5). Submitting sends you to Rankings.
- **Rankings** — Handicap Open and Handicap Main. Points: 1 for playing, 1 for winning the match, 1 per game won. Data is stored in SQLite.

## API

- `POST /api/scores` — Submit a score (JSON: league, level, week, team1, team2, games1, games2; optional handicap).
- `GET /api/rankings/<league>/<level>` — Get rankings (e.g. `/api/rankings/handicap/open`).
