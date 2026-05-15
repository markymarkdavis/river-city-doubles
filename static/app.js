(function () {
  function getApiBase() {
    const fromWindow =
      typeof window !== "undefined" && window.RCD_API_BASE ? String(window.RCD_API_BASE) : "";
    const url = new URL(window.location.href);
    const fromQuery = url.searchParams.get("api") || "";
    const base = (fromQuery || fromWindow || "").trim().replace(/\/+$/, "");
    return base;
  }

  const API_BASE = getApiBase();

  function apiUrl(path) {
    if (!path.startsWith("/")) throw new Error("apiUrl expects an absolute path");
    if (API_BASE) return API_BASE + path;
    const isGitHubPages = window.location.hostname.endsWith("github.io");
    if (isGitHubPages) {
      throw new Error(
        "Backend API not configured for GitHub Pages. Set window.RCD_API_BASE in static/config.js (or use ?api=https://your-backend) and reload."
      );
    }
    return path; // same-origin (local Flask or Render)
  }

  const RCD_BUILD_TOKEN_KEY = "rcd_build_token";

  async function bustCachesAndServiceWorkers() {
    if ("caches" in window) {
      const keys = await caches.keys();
      await Promise.all(keys.map((n) => caches.delete(n)));
    }
    if ("serviceWorker" in navigator) {
      const regs = await navigator.serviceWorker.getRegistrations();
      await Promise.all(regs.map((r) => r.unregister()));
    }
  }

  /** When asset_version or reload_bump changes vs localStorage, clear SW + caches and reload once. */
  void (async function ensureFreshClientAfterDeploy() {
    try {
      let url;
      try {
        url = apiUrl("/api/build-info");
      } catch {
        return;
      }
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      const asset = String(data.asset_version || "");
      const bump = String(data.reload_bump || "");
      const token = bump ? `${asset}|${bump}` : asset;
      if (!token) return;
      const prev = localStorage.getItem(RCD_BUILD_TOKEN_KEY);
      if (prev === token) return;
      if (prev != null && prev !== token) {
        await bustCachesAndServiceWorkers();
      }
      localStorage.setItem(RCD_BUILD_TOKEN_KEY, token);
      if (prev != null && prev !== token) {
        window.location.reload();
      }
    } catch {
      /* offline or API blocked */
    }
  })();

  const FETCH_TIMEOUT_MS = 90000; // free-tier cold start can take 1–2 min
  function fetchWithTimeout(url, options) {
    const ctrl = new AbortController();
    const id = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
    return fetch(url, { ...options, signal: ctrl.signal }).finally(() => clearTimeout(id));
  }

  const TEAMS_OPEN = [
    "Even Older and Grumpier",
    "All the right Angles",
    "El Mustachios",
    "Mack Attack",
    "Old and in the way",
    "Team Nitro",
    "Fatty and Friends",
  ];
  const TEAMS_MAIN = [
    "The Double Troubles",
    "The Boast Beasts",
    "Drop Shotz",
    "Tin and Tonic",
  ];

  const TEAMS_EXCLUDED = new Set(["A", "B"]);

  // Box league player names per sheet (A–F columns in each tab).
  const BOX_PLAYERS = {
    "Foo Fighters": {
      A: "Mark Davis",
      B: "Josh Wishnack",
      C: "Scott Harrison",
      D: "John Street",
      E: "Rob Long",
      F: "Robert Angle",
    },
    "Pink Floyd": {
      A: "Sanjay Hinduja",
      B: "Ros Bowers",
      C: "Tommy Richards",
      D: "Shelton Horsley",
      E: "Grant Stevens",
      F: "Jon Rasich",
    },
    "Dire Straits": {
      A: "Jimmy Meadows",
      B: "Jim Bonbright",
      C: "Spencer Williamson",
      D: "Teddy Damgard",
      E: "Jack Hager",
      F: "Alan Burke",
    },
    Metallica: {
      A: "Jim Maxwell",
      B: "Alan Stone",
      C: "Moses Maxfield",
      D: "Robert Gentil",
      E: "Nick Farrell",
      F: "Deesh Bhattal",
    },
    Nirvana: {
      A: "Matt Rho",
      B: "Tom Mitchell",
      C: "Billy Miller",
      D: "Mukul Paithane",
      E: "Austin Brockenbough",
      F: "Peter Thacker",
    },
    "Fleetwood Mac": {
      A: "Bob Reynolds",
      B: "BT Thornton",
      C: "Nitin Sethi",
      D: "Heidi Stevenson",
      E: "Skylyr Phillips",
      F: "Trey Packard",
    },
    "Guns N' Roses": {
      A: "Jimmy Cooke",
      B: "Frank De Venoge",
      C: "David Shepardson",
      D: "Dean King",
      E: "Matt Chriss",
      F: "Berkeley Edmunds",
    },
    "Pearl Jam": {
      A: "Andy Mack",
      B: "Eddie O'Leary",
      C: "Jim Davis",
      D: "Monty Geho",
      E: "Charles Kempe",
      F: "Manoli Loupassi",
    },
    "Deep Purple": {
      A: "George Stephenson",
      B: "Rand Robins",
      C: "Michael Jarvis",
      D: "Jeff Clarke",
      E: "Michael Halloran",
      F: "Ned Sinnott",
    },
  };
  const BOX_TEAMS = Object.keys(BOX_PLAYERS || {});

  // Full 15 matchups from the Schedule tab (all boxes follow this order).
  const FULL_BOX_MATCHUPS = [
    { matchup: "A & D vs B & C", dates: "Nov 2–8" },
    { matchup: "A & F vs D & E", dates: "Nov 9–15" },
    { matchup: "B & E vs C & F", dates: "Nov 16–29" },
    { matchup: "A & B vs D & F", dates: "Nov 30–Dec 6" },
    { matchup: "B & E vs C & D", dates: "Dec 7–13" },
    { matchup: "A & C vs D & F", dates: "Dec 14–27" },
    { matchup: "A & E vs B & F", dates: "Dec 28–Jan 3" },
    { matchup: "A & B vs C & E", dates: "Jan 4–10" },
    { matchup: "B & D vs C & F", dates: "Jan 11–17" },
    { matchup: "A & E vs C & F", dates: "Jan 18–24" },
    { matchup: "A & C vs B & D", dates: "Jan 25–31" },
    { matchup: "B & D vs E & F", dates: "Feb 1–7" },
    { matchup: "A & D vs C & E", dates: "Feb 8–14" },
    { matchup: "A & F vs B & E", dates: "Feb 15–21" },
    { matchup: "C & E vs D & F", dates: "Feb 22–28" },
  ];
  const HANDICAP_WEEK_OPTIONS = [
    { value: "1", label: "1 — Jan 18–Jan 24" },
    { value: "2", label: "2 — Jan 25–Jan 31" },
    { value: "3", label: "3 — Feb 1–Feb 7" },
    { value: "4", label: "4 — Feb 8–Feb 14" },
    { value: "5", label: "5 — Feb 15–Feb 21" },
    { value: "6", label: "6 — Feb 22–Feb 28" },
    { value: "7", label: "7 — Mar 1–Mar 7" },
  ];

  // Parse "X & Y vs Z & W" -> { team1: [X,Y], team2: [Z,W] }
  function parseMatchup(matchup) {
    const m = matchup.match(/^([A-F]) & ([A-F]) vs ([A-F]) & ([A-F])$/);
    if (!m) return { team1: [], team2: [] };
    return { team1: [m[1], m[2]], team2: [m[3], m[4]] };
  }

  // Expand matchup letters to player names for the active box, by side.
  function getMatchupPlayerNamesBySide(team, matchup, year) {
    const { team1: t1, team2: t2 } = parseMatchup(matchup);
    const p = getBoxPlayersForYear(team, year);
    if (!p || t1.length !== 2 || t2.length !== 2) {
      return { team1: "", team2: "" };
    }
    const side = (letters) =>
      letters.map((L) => escapeHtml(p[L] || L)).join(" & ");
    return { team1: side(t1), team2: side(t2) };
  }

  // Derive per-player scores from matchup and team totals. Sitting players get "X".
  function getPlayerScoresForMatchup(matchup, team1, team2) {
    const { team1: t1, team2: t2 } = parseMatchup(matchup);
    const scores = { A: "X", B: "X", C: "X", D: "X", E: "X", F: "X" };
    const t1Val = team1 != null && team1 !== "" ? Number(team1) : null;
    const t2Val = team2 != null && team2 !== "" ? Number(team2) : null;
    t1.forEach((p) => { scores[p] = t1Val != null ? t1Val : ""; });
    t2.forEach((p) => { scores[p] = t2Val != null ? t2Val : ""; });
    return scores;
  }

  // Box league schedules per team, from the Google Sheets tabs.
  // Each entry: { matchup, dates, team1, team2 } where team1/team2 are game totals.
  const BOX_SCHEDULES = {
    "Foo Fighters": [
      { matchup: "A & D vs B & C", dates: "Nov 2–8", team1: 3, team2: 1 },
      { matchup: "A & F vs D & E", dates: "Nov 9–15", team1: 3, team2: 1 },
      { matchup: "B & E vs C & F", dates: "Nov 16–29", team1: 3, team2: 0 },
      { matchup: "A & B vs D & F", dates: "Nov 30–Dec 6", team1: 3, team2: 0 },
      { matchup: "B & E vs C & D", dates: "Dec 7–13", team1: 2, team2: 3 },
      { matchup: "A & C vs D & F", dates: "Dec 14–27", team1: 3, team2: 1 },
      { matchup: "B & D vs C & F", dates: "Jan 11–17", team1: 3, team2: 2 },
    ],
    "Pink Floyd": [
      { matchup: "A & D vs B & C", dates: "Nov 2–8", team1: 3, team2: 1 },
      { matchup: "A & F vs D & E", dates: "Nov 9–15", team1: 3, team2: 1 },
      { matchup: "B & E vs C & F", dates: "Nov 16–29", team1: 3, team2: 0 },
      { matchup: "A & B vs D & F", dates: "Nov 30–Dec 6", team1: 3, team2: 0 },
      { matchup: "B & E vs C & D", dates: "Dec 7–13", team1: 2, team2: 3 },
      { matchup: "A & C vs D & F", dates: "Dec 14–27", team1: 3, team2: 1 },
      { matchup: "B & D vs C & F", dates: "Jan 11–17", team1: 3, team2: 2 },
      { matchup: "A & C vs B & D", dates: "Jan 25–31", team1: 3, team2: 2 },
      { matchup: "A & F vs B & E", dates: "Feb 15–21", team1: 0, team2: 3 },
    ],
    "Dire Straits": [
      { matchup: "A & D vs B & C", dates: "Nov 2–8", team1: 3, team2: 0 },
      { matchup: "B & E vs C & F", dates: "Nov 16–29", team1: 3, team2: 1 },
      { matchup: "A & B vs D & F", dates: "Nov 30–Dec 6", team1: 3, team2: 1 },
      { matchup: "B & E vs C & D", dates: "Dec 7–13", team1: 3, team2: 1 },
      { matchup: "A & E vs B & F", dates: "Dec 28–Jan 3", team1: 2, team2: 3 },
      { matchup: "A & C vs B & D", dates: "Jan 25–31", team1: 3, team2: 2 },
    ],
    Metallica: [
      { matchup: "A & D vs B & C", dates: "Nov 2–8", team1: 0, team2: 3 },
      { matchup: "A & F vs D & E", dates: "Nov 9–15", team1: 0, team2: 3 },
      { matchup: "B & E vs C & F", dates: "Nov 16–29", team1: 3, team2: 2 },
      { matchup: "A & B vs D & F", dates: "Nov 30–Dec 6", team1: 1, team2: 3 },
      { matchup: "B & E vs C & D", dates: "Dec 7–13", team1: 3, team2: 2 },
      { matchup: "A & C vs D & F", dates: "Dec 14–27", team1: 0, team2: 3 },
      { matchup: "A & E vs B & F", dates: "Dec 28–Jan 3", team1: 1, team2: 3 },
      { matchup: "A & B vs C & E", dates: "Jan 4–10", team1: 3, team2: 1 },
      { matchup: "B & D vs C & F", dates: "Jan 11–17", team1: 3, team2: 1 },
      { matchup: "A & C vs B & D", dates: "Jan 25–31", team1: 0, team2: 3 },
      { matchup: "B & D vs E & F", dates: "Feb 1–7", team1: 3, team2: 1 },
    ],
    Nirvana: [
      { matchup: "A & D vs B & C", dates: "Nov 2–8", team1: 1, team2: 3 },
      { matchup: "A & F vs D & E", dates: "Nov 9–15", team1: 1, team2: 3 },
      { matchup: "B & E vs C & D", dates: "Dec 7–13", team1: 0, team2: 3 },
      { matchup: "A & C vs D & F", dates: "Dec 14–27", team1: 3, team2: 0 },
      { matchup: "B & D vs C & F", dates: "Jan 11–17", team1: 0, team2: 3 },
      { matchup: "B & D vs E & F", dates: "Feb 1–7", team1: 1, team2: 3 },
    ],
    "Fleetwood Mac": [
      { matchup: "A & D vs B & C", dates: "Nov 2–8", team1: 1, team2: 3 },
      { matchup: "A & F vs D & E", dates: "Nov 9–15", team1: 1, team2: 3 },
      { matchup: "B & E vs C & F", dates: "Nov 16–29", team1: 2, team2: 3 },
      { matchup: "A & B vs D & F", dates: "Nov 30–Dec 6", team1: 3, team2: 1 },
      { matchup: "B & E vs C & D", dates: "Dec 7–13", team1: 0, team2: 3 },
      { matchup: "A & C vs D & F", dates: "Dec 14–27", team1: 3, team2: 0 },
      { matchup: "A & E vs B & F", dates: "Dec 28–Jan 3", team1: 2, team2: 3 },
      { matchup: "A & B vs C & E", dates: "Jan 4–10", team1: 3, team2: 1 },
      { matchup: "B & D vs C & F", dates: "Jan 11–17", team1: 3, team2: 2 },
      { matchup: "A & E vs C & F", dates: "Jan 18–24", team1: 1, team2: 3 },
      { matchup: "A & C vs B & D", dates: "Jan 25–31", team1: 3, team2: 1 },
      { matchup: "B & D vs E & F", dates: "Feb 1–7", team1: 3, team2: 1 },
      { matchup: "A & D vs C & E", dates: "Feb 8–14", team1: 1, team2: 3 },
      { matchup: "A & F vs B & E", dates: "Feb 15–21", team1: 3, team2: 0 },
    ],
    "Guns N' Roses": [
      { matchup: "A & D vs B & C", dates: "Nov 2–8", team1: 1, team2: 3 },
      { matchup: "A & F vs D & E", dates: "Nov 9–15", team1: 1, team2: 3 },
      { matchup: "B & E vs C & D", dates: "Dec 7–13", team1: 0, team2: 3 },
      { matchup: "A & C vs D & F", dates: "Dec 14–27", team1: 3, team2: 0 },
      { matchup: "B & D vs C & F", dates: "Jan 11–17", team1: 0, team2: 3 },
      { matchup: "A & E vs C & F", dates: "Jan 18–24", team1: 1, team2: 3 },
    ],
    "Pearl Jam": [
      { matchup: "A & D vs B & C", dates: "Nov 2–8", team1: 0, team2: 3 },
      { matchup: "A & F vs D & E", dates: "Nov 9–15", team1: 3, team2: 2 },
    ],
    "Deep Purple": [
      { matchup: "A & D vs B & C", dates: "Nov 2–8", team1: 1, team2: 3 },
      { matchup: "A & F vs D & E", dates: "Nov 9–15", team1: 1, team2: 3 },
      { matchup: "B & E vs C & F", dates: "Nov 16–29", team1: 2, team2: 3 },
      { matchup: "A & B vs D & F", dates: "Nov 30–Dec 6", team1: 3, team2: 1 },
      { matchup: "B & E vs C & D", dates: "Dec 7–13", team1: 0, team2: 3 },
      { matchup: "A & C vs D & F", dates: "Dec 14–27", team1: 3, team2: 0 },
      { matchup: "A & E vs C & F", dates: "Jan 18–24", team1: 3, team2: 1 },
    ],
  };

  // 2026–2027 season (year select value 2026): overrides per box when present.
  const BOX_PLAYERS_2026 = {
    "Foo Fighters": {
      A: "Mark Davis",
      B: "Jim Davis",
      C: "Sanjay Hinduja",
      D: "Grant Stevens",
      E: "Andy Mack",
      F: "Eddie O'Leary",
    },
  };

  const BOX_SCHEDULES_2026 = {
    "Foo Fighters": [
      { matchup: "A & D vs B & C", dates: "May 12, 2026", team1: "", team2: "" },
      { matchup: "A & F vs D & E", dates: "May 13, 2026", team1: "", team2: "" },
      { matchup: "B & E vs C & F", dates: "May 14, 2026", team1: "", team2: "" },
      { matchup: "A & B vs D & F", dates: "May 15, 2026", team1: "", team2: "" },
      { matchup: "B & E vs C & D", dates: "May 16, 2026", team1: "", team2: "" },
      { matchup: "A & C vs D & F", dates: "May 17, 2026", team1: "", team2: "" },
      { matchup: "A & E vs B & F", dates: "May 18, 2026", team1: "", team2: "" },
      { matchup: "A & B vs C & E", dates: "May 19, 2026", team1: "", team2: "" },
      { matchup: "B & D vs C & F", dates: "May 20, 2026", team1: "", team2: "" },
    ],
  };

  /** When a year is listed here, only boxes with both roster + schedule rows appear for that season. */
  const BOX_PLAYERS_BY_YEAR = {
    2026: BOX_PLAYERS_2026,
  };

  const BOX_SCHEDULES_BY_YEAR = {
    2026: BOX_SCHEDULES_2026,
  };

  function seasonBoxYear(year) {
    const y = Number(year);
    return Number.isNaN(y) ? 2025 : y;
  }

  function yearUsesExplicitBoxList(y) {
    const yNum = Number(y);
    if (Number.isNaN(yNum)) return false;
    return (
      Object.prototype.hasOwnProperty.call(BOX_PLAYERS_BY_YEAR, yNum) ||
      Object.prototype.hasOwnProperty.call(BOX_SCHEDULES_BY_YEAR, yNum)
    );
  }

  /** Box names shown for this season: all legacy boxes, or only teams configured for an explicit year. */
  function getBoxTeamsForYear(year) {
    const y = seasonBoxYear(year);
    if (!yearUsesExplicitBoxList(y)) return BOX_TEAMS.slice();
    const pm = BOX_PLAYERS_BY_YEAR[y];
    const sm = BOX_SCHEDULES_BY_YEAR[y];
    const names = new Set([...(pm ? Object.keys(pm) : []), ...(sm ? Object.keys(sm) : [])]);
    return [...names]
      .filter((team) => {
        const p = pm && pm[team];
        const s = sm && sm[team];
        const hasPlayers = p && typeof p === "object" && Object.keys(p).length > 0;
        const hasSchedule = Array.isArray(s) && s.length > 0;
        return hasPlayers && hasSchedule;
      })
      .sort((a, b) => a.localeCompare(b));
  }

  function syncBoxTabButtonsForYear(year) {
    const teams = getBoxTeamsForYear(year);
    const schedTabs = document.querySelector("#schedule-panel-box .box-tabs");
    const statTabs = document.querySelector("#standings-box .standings-box-tabs");
    const prevSched = document.querySelector("#schedule-panel-box .box-tab.active")?.dataset?.boxTeam;
    const prevStat = document.querySelector("#standings-box .standings-box-tabs .box-tab.active")?.dataset?.standingsBox;
    const pick = (prev) => (prev && teams.includes(prev) ? prev : teams[0] || "");
    const schedActive = pick(prevSched);
    const statActive = pick(prevStat);
    const appendTabs = (container, dataAttr, activeTeam) => {
      if (!container) return;
      container.innerHTML = "";
      teams.forEach((team) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "box-tab" + (team === activeTeam ? " active" : "");
        btn.dataset[dataAttr] = team;
        btn.textContent = team;
        container.appendChild(btn);
      });
    };
    appendTabs(schedTabs, "boxTeam", schedActive);
    appendTabs(statTabs, "standingsBox", statActive);
  }

  function getBoxPlayersForYear(team, year) {
    const y = seasonBoxYear(year);
    if (yearUsesExplicitBoxList(y)) {
      const p = (BOX_PLAYERS_BY_YEAR[y] || {})[team];
      return p && typeof p === "object" ? p : {};
    }
    return BOX_PLAYERS[team] || {};
  }

  /** Built-in sheet rows (dates / demo scores) before merging API scores. */
  function getStaticBoxScheduleRowsForYear(team, year) {
    const y = seasonBoxYear(year);
    if (yearUsesExplicitBoxList(y)) {
      return (BOX_SCHEDULES_BY_YEAR[y] || {})[team] || [];
    }
    return BOX_SCHEDULES[team] || [];
  }

  const boxScheduleMergeCache = new Map();

  function buildMergedBoxScheduleRowList(team, year, apiRows) {
    const staticList = getStaticBoxScheduleRowsForYear(team, year);
    const staticByMatchup = {};
    staticList.forEach((r) => {
      staticByMatchup[r.matchup] = r;
    });
    const byWeek = new Map();
    (apiRows || []).forEach((r) => {
      byWeek.set(Number(r.week), r);
    });
    return FULL_BOX_MATCHUPS.map((m, idx) => {
      const week = idx + 1;
      const db = byWeek.get(week);
      const staticRec = staticByMatchup[m.matchup];
      const dates = (staticRec && staticRec.dates) || m.dates;
      if (db != null) {
        return {
          matchup: m.matchup,
          dates,
          team1: Number(db.games1),
          team2: Number(db.games2),
        };
      }
      if (staticRec) {
        return {
          matchup: m.matchup,
          dates,
          team1: staticRec.team1,
          team2: staticRec.team2,
        };
      }
      return { matchup: m.matchup, dates, team1: "", team2: "" };
    });
  }

  function getBoxScheduleRowsForYear(team, year) {
    const key = `${team}|${seasonBoxYear(year)}`;
    if (boxScheduleMergeCache.has(key)) {
      return boxScheduleMergeCache.get(key);
    }
    return buildMergedBoxScheduleRowList(team, year, []);
  }

  async function refreshBoxScoresMergeCache(team, year) {
    const key = `${team}|${seasonBoxYear(year)}`;
    const url = `${apiUrl("/api/box/scores")}?team=${encodeURIComponent(team)}&year=${encodeURIComponent(String(seasonBoxYear(year)))}`;
    const res = await fetchWithTimeout(url).catch(() => null);
    if (!res || !res.ok) {
      boxScheduleMergeCache.set(key, buildMergedBoxScheduleRowList(team, year, []));
      return;
    }
    const data = await res.json().catch(() => []);
    const rows = Array.isArray(data) ? data : [];
    boxScheduleMergeCache.set(key, buildMergedBoxScheduleRowList(team, year, rows));
  }

  // Get player totals for a box, sorted by total descending.
  function getBoxPlayerTotals(team, year) {
    const rows = getFullBoxRows(team, year);
    const playerTotals = { A: 0, B: 0, C: 0, D: 0, E: 0, F: 0 };
    rows.forEach((row) => {
      ["a", "b", "c", "d", "e", "f"].forEach((key) => {
        const letter = key.toUpperCase();
        const val = row[key];
        if (val !== "X" && val !== "" && val != null) {
          playerTotals[letter] += Number(val) || 0;
        }
      });
    });
    const players = getBoxPlayersForYear(team, year);
    return ["A", "B", "C", "D", "E", "F"]
      .map((letter) => ({
        letter,
        name: (players && players[letter]) || "",
        total: playerTotals[letter],
      }))
      .sort((a, b) => b.total - a.total);
  }

  // Build full 15 rows for a box, merging canonical matchups with recorded scores.
  function getFullBoxRows(team, year) {
    const scheduleRows = getBoxScheduleRowsForYear(team, year);
    const recorded = scheduleRows.reduce((acc, r) => {
      acc[r.matchup] = r;
      return acc;
    }, {});
    return FULL_BOX_MATCHUPS.map((m) => {
      const r = recorded[m.matchup];
      const team1 = r ? r.team1 : "";
      const team2 = r ? r.team2 : "";
      const scores = getPlayerScoresForMatchup(m.matchup, team1, team2);
      return {
        matchup: m.matchup,
        dates: r && r.dates ? r.dates : m.dates,
        team1,
        team2,
        a: scores.A,
        b: scores.B,
        c: scores.C,
        d: scores.D,
        e: scores.E,
        f: scores.F,
      };
    });
  }

  function getTeamsForLevel(level) {
    const list = level === "open" ? TEAMS_OPEN : level === "main" ? TEAMS_MAIN : [];
    return list.filter((t) => !TEAMS_EXCLUDED.has(t));
  }

  function fillTeamDropdownOptions(teams) {
    const option = (value, label) => {
      const o = document.createElement("option");
      o.value = value;
      o.textContent = label || value;
      return o;
    };
    const team1 = document.getElementById("team1");
    const team2 = document.getElementById("team2");
    team1.innerHTML = "";
    team2.innerHTML = "";
    team1.appendChild(option("", "Select team"));
    team2.appendChild(option("", "Select team"));
    teams.forEach((name) => {
      team1.appendChild(option(name, name));
      team2.appendChild(option(name, name));
    });
  }

  function fillLevelOptionsForLeague(league) {
    const levelEl = document.getElementById("level");
    if (!levelEl) return;
    levelEl.innerHTML = "";
    const add = (v, txt) => {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = txt;
      levelEl.appendChild(o);
    };
    if (league === "box") {
      add("", "Select box");
      const boxTeams = getBoxTeamsForYear(getYearFrom("year-input"));
      boxTeams.forEach((b) => add(b, b));
      const cur = levelEl.value;
      if (cur && !boxTeams.includes(cur)) {
        levelEl.value = "";
      }
    } else {
      add("", "Select level");
      add("open", "Open");
      add("main", "Main");
    }
  }

  function fillSingleTeamSideOptions(team1Text, team2Text) {
    const option = (value, label) => {
      const o = document.createElement("option");
      o.value = value;
      o.textContent = label || value;
      return o;
    };
    const team1 = document.getElementById("team1");
    const team2 = document.getElementById("team2");
    team1.innerHTML = "";
    team2.innerHTML = "";
    team1.appendChild(option(team1Text, team1Text));
    team2.appendChild(option(team2Text, team2Text));
  }

  function fillWeekOptions(league) {
    const weekEl = document.getElementById("week");
    if (!weekEl) return;
    weekEl.innerHTML = "";
    const addOpt = (v, txt) => {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = txt;
      weekEl.appendChild(o);
    };
    addOpt("", "Select week");
    if (league === "box") {
      const form = document.getElementById("score-form");
      const box = form && form.level ? form.level.value : "";
      const year = getYearFrom("year-input");
      const rec = getBoxScheduleRowsForYear(box, year).reduce((acc, row) => {
        acc[row.matchup] = row;
        return acc;
      }, {});
      FULL_BOX_MATCHUPS.forEach((m, idx) => {
        const row = rec[m.matchup];
        const dateLabel = row && row.dates ? row.dates : m.dates;
        addOpt(String(idx + 1), `${idx + 1} — ${dateLabel}`);
      });
    } else {
      HANDICAP_WEEK_OPTIONS.forEach((w) => addOpt(w.value, w.label));
    }
  }

  function fillTeamDropdowns(level) {
    fillTeamDropdownOptions(getTeamsForLevel(level));
  }

  function fillBoxTeamDropdowns() {
    fillTeamDropdownOptions(getBoxTeamsForYear(getYearFrom("year-input")));
  }

  function clearScoreFormPlayers() {
    const form = document.getElementById("score-form");
    if (!form) return;
    form.team1_player1.value = "";
    form.team1_player2.value = "";
    form.team2_player1.value = "";
    form.team2_player2.value = "";
  }

  function updateHandicapFieldsVisibility() {
    const form = document.getElementById("score-form");
    if (!form) return;
    const isBox = form.league.value === "box";
    const h1 = document.getElementById("handicap_team1");
    const h2 = document.getElementById("handicap_team2");
    const row1 = document.getElementById("handicap-row-team1");
    const row2 = document.getElementById("handicap-row-team2");
    if (!h1 || !h2) return;
    [h1, h2].forEach((el) => {
      el.disabled = isBox;
      if (isBox) el.value = "";
    });
    if (row1) row1.style.display = isBox ? "none" : "";
    if (row2) row2.style.display = isBox ? "none" : "";
  }

  function autoPopulateBoxPlayersInForm() {
    const form = document.getElementById("score-form");
    if (!form) return;
    if (form.league.value !== "box") return;
    const weekNum = parseInt(form.week.value, 10);
    const matchup = Number.isNaN(weekNum) ? null : FULL_BOX_MATCHUPS[weekNum - 1];
    const box = form.level.value;
    if (!matchup || !box) {
      clearScoreFormPlayers();
      return;
    }
    const parsed = parseMatchup(matchup.matchup);
    const year = getYearFrom("year-input");
    const p1 = getBoxPlayersForYear(box, year);
    const p2 = getBoxPlayersForYear(box, year);
    fillSingleTeamSideOptions(`${parsed.team1[0]} & ${parsed.team1[1]}`, `${parsed.team2[0]} & ${parsed.team2[1]}`);
    form.team1_player1.value = parsed.team1[0] ? (p1[parsed.team1[0]] || "") : "";
    form.team1_player2.value = parsed.team1[1] ? (p1[parsed.team1[1]] || "") : "";
    form.team2_player1.value = parsed.team2[0] ? (p2[parsed.team2[0]] || "") : "";
    form.team2_player2.value = parsed.team2[1] ? (p2[parsed.team2[1]] || "") : "";
  }

  function updateScoreFormTeamsFromLeagueAndLevel() {
    const form = document.getElementById("score-form");
    if (!form) return;
    const levelLabel = document.getElementById("level-label");
    if (form.league.value === "box") {
      if (levelLabel) levelLabel.textContent = "Box";
      fillWeekOptions("box");
      form.level.disabled = false;
      form.level.required = true;
      form.team1.disabled = true;
      form.team2.disabled = true;
      autoPopulateBoxPlayersInForm();
      return;
    }
    if (levelLabel) levelLabel.textContent = "Level";
    fillWeekOptions("handicap");
    form.level.disabled = false;
    form.level.required = true;
    form.team1.disabled = false;
    form.team2.disabled = false;
    fillTeamDropdowns(form.level.value);
  }

  async function postScore(entry) {
    const res = await fetch(apiUrl("/api/scores"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        league: entry.league,
        level: entry.level,
        week: Number(entry.week),
        year: getYearFrom("year-input"),
        handicap_team1: entry.handicap_team1 || undefined,
        handicap_team2: entry.handicap_team2 || undefined,
        team1: entry.team1,
        team2: entry.team2,
        games1: entry.games1,
        games2: entry.games2,
        team1_players: entry.team1_players || undefined,
        team2_players: entry.team2_players || undefined,
      }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || "Failed to submit score");
    }
  }

  async function saveNotificationSubscription(entry) {
    const res = await fetchWithTimeout(apiUrl("/api/notifications/subscriptions"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: entry.name,
        email: entry.email,
        notify_handicap: entry.notifyHandicap,
        notify_box: entry.notifyBox,
      }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || "Failed to save notification settings");
    }
    return res.json();
  }

  async function removeNotificationSubscription(email) {
    // Use query string — many stacks drop or ignore JSON bodies on DELETE.
    const q = encodeURIComponent(email);
    const res = await fetchWithTimeout(`${apiUrl("/api/notifications/subscriptions")}?email=${q}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || "Failed to remove email");
    }
    return res.json();
  }

  async function fetchNotificationEmailStatus() {
    const res = await fetchWithTimeout(apiUrl("/api/notifications/status")).catch(() => null);
    if (!res || !res.ok) return null;
    return res.json();
  }

  async function refreshNotificationsServerHint() {
    const el = document.getElementById("notifications-server-hint");
    if (!el) return;
    const data = await fetchNotificationEmailStatus();
    if (!data) {
      el.textContent = "";
      el.classList.remove("notifications-server-hint--warn");
      return;
    }
    if (!data.email_transport_configured) {
      el.textContent =
        "Your preferences are saved here. This site has not been given a mail provider yet, so no messages will be delivered until the host configures that.";
      el.classList.add("notifications-server-hint--warn");
      return;
    }
    el.classList.remove("notifications-server-hint--warn");
    el.textContent =
      "The server can send email. Handicap reminders and week-complete standings run when scores are submitted; a daily cron is optional for an extra pass.";
  }

  async function fetchStandings(league, level) {
    const year = getYearFrom("year-standings");
    const url = `${apiUrl(`/api/standings/${encodeURIComponent(league)}/${encodeURIComponent(level)}`)}?year=${year}`;
    const res = await fetchWithTimeout(url).catch((e) => {
      if (e.name === "AbortError") throw new Error("Request timed out. The server may be waking up; try again in a minute.");
      throw e;
    });
    if (!res.ok) throw new Error("Failed to load standings");
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  }

  function getYearFrom(selectId) {
    const el = document.getElementById(selectId);
    if (!el) return 2025;
    const v = parseInt(el.value, 10);
    return Number.isNaN(v) ? 2025 : v;
  }

  async function fetchYears() {
    const res = await fetchWithTimeout(apiUrl("/api/years")).catch(() => null);
    if (!res || !res.ok) throw new Error("Failed to load seasons");
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  }

  const YEAR_SELECT_IDS = ["year-schedule", "year-input", "year-standings", "year-players"];
  let rcdYearSelectListenersAttached = false;

  async function refreshUiForSeasonYear() {
    syncBoxTabButtonsForYear(getYearFrom("year-schedule"));
    void renderScheduleTable("open");
    void renderScheduleTable("main");
    await renderBoxSchedule();
    void renderStandingsTable("handicap-open");
    void renderStandingsTable("handicap-main");
    await renderBoxStandings();
    const form = document.getElementById("score-form");
    if (form && form.league.value === "box") {
      fillLevelOptionsForLeague("box");
      fillWeekOptions("box");
      autoPopulateBoxPlayersInForm();
    }
    void renderPlayersTable();
  }

  function setYearForTab(tabId, value) {
    if (value === undefined) return;
    const year = typeof value === "string" ? parseInt(value.split("-")[0], 10) : value;
    if (Number.isNaN(year)) return;
    YEAR_SELECT_IDS.forEach((sid) => {
      const s = document.getElementById(sid);
      if (s) s.value = String(year);
    });
    void refreshUiForSeasonYear();
  }

  function fillYearOptions(years) {
    if (!Array.isArray(years) || years.length === 0) return;
    const defaultYear = years.includes(2025) ? 2025 : Math.max.apply(null, years);
    const label = (y) => `${y}-${y + 1}`;

    YEAR_SELECT_IDS.forEach((id) => {
      let select = document.getElementById(id);
      if (!select) {
        select = document.createElement("select");
        select.id = id;
        select.setAttribute("aria-hidden", "true");
        select.hidden = true;
        document.body.appendChild(select);
      }
      select.innerHTML = "";
      years.forEach((y) => {
        const option = document.createElement("option");
        option.value = String(y);
        option.textContent = label(y);
        select.appendChild(option);
      });
      select.value = String(defaultYear);
    });

    const panelIds = ["nav-schedules-panel", "nav-input-panel", "nav-standings-panel", "nav-players-panel"];
    const tabIds = ["schedules", "input", "standings", "players"];
    panelIds.forEach((panelId, i) => {
      const panel = document.getElementById(panelId);
      const tabId = tabIds[i];
      if (!panel || !tabId) return;
      panel.innerHTML = "";
      years.forEach((y) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "tab-dropdown-option";
        btn.setAttribute("data-tab", tabId);
        btn.setAttribute("data-value", label(y));
        btn.textContent = label(y);
        panel.appendChild(btn);
      });
    });

    const mobileListIds = ["mobile-menu-schedules", "mobile-menu-input", "mobile-menu-standings", "mobile-menu-players"];
    mobileListIds.forEach((listId, i) => {
      const ul = document.getElementById(listId);
      const tabId = tabIds[i];
      if (!ul || !tabId) return;
      ul.innerHTML = "";
      years.forEach((y) => {
        const li = document.createElement("li");
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "mobile-menu-item";
        btn.setAttribute("data-tab", tabId);
        btn.setAttribute("data-value", String(y));
        btn.textContent = label(y);
        li.appendChild(btn);
        ul.appendChild(li);
      });
    });
  }

  // Shown immediately and if /api/years fails (offline, wrong api base, timeout).
  const FALLBACK_SEASON_YEARS = [2025, 2026];

  async function initYearDropdowns() {
    fillYearOptions(FALLBACK_SEASON_YEARS);
    try {
      const years = await fetchYears();
      if (Array.isArray(years) && years.length > 0) {
        fillYearOptions(years);
      }
    } catch (err) {
      console.error("Failed to load years:", err);
      fillYearOptions(FALLBACK_SEASON_YEARS);
    }
    if (!rcdYearSelectListenersAttached) {
      rcdYearSelectListenersAttached = true;
      function onSeasonYearChange(ev) {
        const v = ev.target.value;
        YEAR_SELECT_IDS.forEach((sid) => {
          const s = document.getElementById(sid);
          if (s) s.value = v;
        });
        void refreshUiForSeasonYear();
      }
      YEAR_SELECT_IDS.forEach((id) => {
        const sel = document.getElementById(id);
        if (!sel) return;
        sel.addEventListener("change", onSeasonYearChange);
      });
    }
    void refreshUiForSeasonYear();
  }

  function switchTab(tabId) {
    document.querySelectorAll(".tab").forEach((t) => {
      t.classList.remove("active");
      t.setAttribute("aria-selected", "false");
    });
    document.querySelectorAll(".panel").forEach((p) => {
      p.classList.remove("active");
      p.hidden = true;
    });
    const tab = document.querySelector(`[data-tab="${tabId}"]`);
    const panel = document.getElementById(`panel-${tabId}`);
    if (tab) {
      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
    }
    if (panel) {
      panel.classList.add("active");
      panel.hidden = false;
    }
    if (tabId === "standings") void renderStandings();
    if (tabId === "schedules") {
      syncBoxTabButtonsForYear(getYearFrom("year-schedule"));
      switchSchedulesBranch("box");
      void renderSchedule();
    }
    if (tabId === "players") void renderPlayersTable();
    if (tabId === "rules") updateRulesContent();
    if (tabId === "notifications") refreshNotificationsServerHint();
  }

  let currentRulesView = "doubles";

  function updateRulesContent() {
    const doublesEl = document.getElementById("rules-content-doubles");
    const handicapEl = document.getElementById("rules-content-handicap");
    if (!doublesEl || !handicapEl) return;
    doublesEl.hidden = currentRulesView !== "doubles";
    handicapEl.hidden = currentRulesView !== "handicap";
  }

  async function fetchSchedule(level) {
    if (level === "box") {
      // Box schedule is rendered by renderBoxSchedule (static sheet merged with /api/box/scores).
      return null;
    }
    const year = getYearFrom("year-schedule");
    const url = `${apiUrl("/api/schedule")}?level=${encodeURIComponent(level)}&year=${year}`;
    const res = await fetchWithTimeout(url).catch((e) => {
      if (e.name === "AbortError") throw new Error("Request timed out. The server may be waking up; try again in a minute.");
      throw e;
    });
    if (!res.ok) throw new Error("Failed to load schedule");
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  }

  function switchSchedulesBranch(branch) {
    document.querySelectorAll(".schedules-tab").forEach((t) => {
      const on = t.dataset.schedulesBranch === branch;
      t.classList.toggle("active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    const boxBranch = document.getElementById("schedules-branch-box");
    const hcBranch = document.getElementById("schedules-branch-handicap");
    if (!boxBranch || !hcBranch) return;
    if (branch === "box") {
      boxBranch.classList.add("active");
      boxBranch.hidden = false;
      hcBranch.classList.remove("active");
      hcBranch.hidden = true;
      void renderBoxSchedule();
    } else {
      hcBranch.classList.add("active");
      hcBranch.hidden = false;
      boxBranch.classList.remove("active");
      boxBranch.hidden = true;
      const activeSt = document.querySelector("#schedules-branch-handicap .schedule-tab.active");
      const lvl = activeSt ? activeSt.dataset.scheduleLevel : "open";
      switchScheduleTab(lvl);
    }
  }

  function switchScheduleTab(level) {
    document.querySelectorAll("#schedules-branch-handicap .schedule-tab").forEach((t) => {
      t.classList.toggle("active", t.dataset.scheduleLevel === level);
    });
    document.querySelectorAll("#schedules-branch-handicap .schedule-panel").forEach((p) => {
      const id = p.id.replace("schedule-panel-", "");
      p.classList.toggle("active", id === level);
      p.hidden = id !== level;
    });
    void renderScheduleTable(level);
  }

  async function renderScheduleTable(level) {
    const tbody = document.getElementById(`schedule-tbody-${level}`);
    const emptyEl = document.getElementById(`empty-schedule-${level}`);
    if (!tbody || !emptyEl) return;
    tbody.innerHTML = "";
    try {
      const rows = await fetchSchedule(level);
      if (!rows || rows.length === 0) {
        emptyEl.hidden = false;
        return;
      }
      emptyEl.hidden = true;
      rows.forEach((row) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${escapeHtml(String(row.week))}</td>
          <td>${escapeHtml(row.date_range)}</td>
          <td>${escapeHtml(row.team1)}</td>
          <td>${escapeHtml(row.team2)}</td>
          <td>${escapeHtml(row.bye)}</td>
          <td>${escapeHtml(row.team1_players)}</td>
          <td>${escapeHtml(row.team2_players)}</td>
          <td>${escapeHtml(row.handicap)}</td>
          <td>${escapeHtml(row.score)}</td>
          <td>${escapeHtml(row.winner)}</td>
        `;
        tbody.appendChild(tr);
      });
    } catch (err) {
      emptyEl.textContent = err && err.message ? err.message : "Unable to load schedule. Is the server running?";
      emptyEl.hidden = false;
    }
  }

  async function renderSchedule() {
    void renderScheduleTable("open");
    void renderScheduleTable("main");
    await renderBoxSchedule();
  }

  async function renderBoxSchedule() {
    const tbody = document.getElementById("schedule-tbody-box");
    if (!tbody) return;
    const year = getYearFrom("year-schedule");
    const teamsList = getBoxTeamsForYear(year);
    if (teamsList.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="12" class="empty-state">No box leagues configured for this season.</td></tr>';
      document.querySelectorAll("#schedule-panel-box .box-player-header").forEach((th) => {
        const letter = th.dataset.letter;
        th.textContent = letter || "";
      });
      return;
    }
    const activeTab = document.querySelector("#schedule-panel-box .box-tab.active");
    const team = (activeTab && activeTab.dataset.boxTeam) || teamsList[0];
    try {
      await refreshBoxScoresMergeCache(team, year);
    } catch (err) {
      boxScheduleMergeCache.set(
        `${team}|${seasonBoxYear(year)}`,
        buildMergedBoxScheduleRowList(team, year, [])
      );
    }
    const rows = getFullBoxRows(team, year);
    tbody.innerHTML = "";

    // Update player headers (A..F = name) to match this box.
    const headerCells = document.querySelectorAll(".box-player-header");
    const players = getBoxPlayersForYear(team, year);
    if (players) {
      headerCells.forEach((th) => {
        const letter = th.dataset.letter;
        const name = players[letter] || "";
        th.textContent = `${letter}=${name}`;
      });
    }

    let total1 = 0;
    let total2 = 0;
    const playerTotals = { A: 0, B: 0, C: 0, D: 0, E: 0, F: 0 };
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      const a = escapeHtml(String(row.a ?? ""));
      const b = escapeHtml(String(row.b ?? ""));
      const c = escapeHtml(String(row.c ?? ""));
      const d = escapeHtml(String(row.d ?? ""));
      const e = escapeHtml(String(row.e ?? ""));
      const f = escapeHtml(String(row.f ?? ""));
      const sides = getMatchupPlayerNamesBySide(team, row.matchup, year);
      tr.innerHTML = `
        <td>${escapeHtml(row.matchup)}</td>
        <td>${escapeHtml(row.dates)}</td>
        <td>${row.team1}</td>
        <td>${row.team2}</td>
        <td class="box-schedule-team-players">${sides.team1}</td>
        <td class="box-schedule-team-players">${sides.team2}</td>
        <td>${a}</td>
        <td>${b}</td>
        <td>${c}</td>
        <td>${d}</td>
        <td>${e}</td>
        <td>${f}</td>
      `;
      tbody.appendChild(tr);
      total1 += Number(row.team1) || 0;
      total2 += Number(row.team2) || 0;
      ["a", "b", "c", "d", "e", "f"].forEach((key, i) => {
        const letter = key.toUpperCase();
        const val = row[key];
        if (val !== "X" && val !== "" && val != null) {
          playerTotals[letter] += Number(val) || 0;
        }
      });
    });

    const trTotal = document.createElement("tr");
    trTotal.className = "box-totals-row";
    trTotal.innerHTML = `
      <td><strong>Totals</strong></td>
      <td></td>
      <td><strong>${total1}</strong></td>
      <td><strong>${total2}</strong></td>
      <td></td>
      <td></td>
      <td><strong>${playerTotals.A}</strong></td>
      <td><strong>${playerTotals.B}</strong></td>
      <td><strong>${playerTotals.C}</strong></td>
      <td><strong>${playerTotals.D}</strong></td>
      <td><strong>${playerTotals.E}</strong></td>
      <td><strong>${playerTotals.F}</strong></td>
    `;
    tbody.appendChild(trTotal);
  }

  function switchStandingsTab(standingsId) {
    document.querySelectorAll(".standings-tab").forEach((t) => {
      t.classList.toggle("active", t.dataset.standings === standingsId);
    });
    document.querySelectorAll(".standings-panel").forEach((p) => {
      const id = p.id.replace("standings-", "");
      p.classList.toggle("active", id === standingsId);
      p.hidden = id !== standingsId;
    });
    if (standingsId === "box") {
      void renderBoxStandings();
    } else {
      renderStandingsTable(standingsId);
    }
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  async function renderBoxStandings() {
    const tbody = document.getElementById("tbody-standings-box");
    if (!tbody) return;
    const year = getYearFrom("year-standings");
    const teamsList = getBoxTeamsForYear(year);
    if (teamsList.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="3" class="empty-state">No box leagues configured for this season.</td></tr>';
      return;
    }
    const activeTab = document.querySelector("#standings-box .standings-box-tabs .box-tab.active");
    const team = (activeTab && activeTab.dataset.standingsBox) || teamsList[0];
    try {
      await refreshBoxScoresMergeCache(team, year);
    } catch (err) {
      boxScheduleMergeCache.set(
        `${team}|${seasonBoxYear(year)}`,
        buildMergedBoxScheduleRowList(team, year, [])
      );
    }
    const rows = getBoxPlayerTotals(team, year);
    tbody.innerHTML = "";
    rows.forEach((row, i) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${i + 1}</td>
        <td>${escapeHtml(row.name || row.letter)}</td>
        <td>${row.total}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  async function renderStandingsTable(standingsId) {
    const isOpen = standingsId === "handicap-open";
    const level = isOpen ? "open" : "main";
    const tbodyId = `tbody-handicap-${isOpen ? "open" : "main"}`;
    const tbody = document.getElementById(tbodyId);
    tbody.innerHTML = "";
    try {
      const rows = await fetchStandings("handicap", level);
      rows.forEach((row, i) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${i + 1}</td>
          <td>${escapeHtml(row.name)}</td>
          <td>${row.points}</td>
          <td>${row.matches}</td>
          <td>${row.record}</td>
          <td>${row.gamesWon}</td>
        `;
        tbody.appendChild(tr);
      });
    } catch (err) {
      const tr = document.createElement("tr");
      const msg = err && err.message ? err.message : "Unable to load standings. Is the server running?";
      tr.innerHTML = `<td colspan="6">${escapeHtml(msg)}</td>`;
      tbody.appendChild(tr);
    }
  }

  async function renderStandings() {
    void renderStandingsTable("handicap-open");
    void renderStandingsTable("handicap-main");
    await renderBoxStandings();
  }

  function splitSchedulePlayerCell(value) {
    if (!value || !String(value).trim()) return [];
    const cleaned = String(value).replace(/\//g, ",").replace(/&/g, ",").replace(/\s+and\s+/gi, ",");
    return cleaned
      .split(",")
      .map((p) => p.trim().replace(/\s+/g, " "))
      .filter(Boolean);
  }

  function firstNameSortKey(displayName) {
    const parts = String(displayName || "").trim().split(/\s+/);
    return (parts[0] || "").toLowerCase();
  }

  /** Schedule/box strings may use old spellings; merge rows and show preferred names. */
  const PLAYER_NAME_CANONICAL = new Map([
    ["dave shepardson", "David Shepardson"],
    ["frank devenoge", "Frank De Venoge"],
    ["skye phillips", "Skylyr Phillips"],
    ["skye philips", "Skylyr Phillips"],
  ]);

  function canonicalPlayerName(raw) {
    const t = String(raw || "").trim().replace(/\s+/g, " ");
    if (!t) return "";
    const k = t.toLowerCase();
    return PLAYER_NAME_CANONICAL.get(k) || t;
  }

  /**
   * Handicap division + schedule team for the Players tab. For these names, schedule
   * rows are ignored so each person shows exactly one division/team (keys: lowercase display name).
   */
  const PLAYER_HANDICAP_CANONICAL_ROSTER = new Map([
    [
      2025,
      new Map([
        ["alan burke", { division: "Main", team: "The Boast Beasts" }],
        ["bt thornton", { division: "Main", team: "Drop Shotz" }],
        ["grant stevens", { division: "Open", team: "Fatty and Friends" }],
        ["michael halloran", { division: "Open", team: "Mack Attack" }],
        ["teddy damgard", { division: "Open", team: "Team Nitro" }],
        ["dean king", { division: "Open", team: "Team Nitro" }],
        ["nitin sethi", { division: "Main", team: "The Boast Beasts" }],
        ["spencer williamson", { division: "Open", team: "Even Older and Grumpier" }],
      ]),
    ],
    [
      2026,
      new Map([
        ["alan burke", { division: "Main", team: "The Boast Beasts" }],
        ["bt thornton", { division: "Main", team: "Drop Shotz" }],
        ["grant stevens", { division: "Open", team: "Fatty and Friends" }],
        ["michael halloran", { division: "Open", team: "Mack Attack" }],
        ["teddy damgard", { division: "Open", team: "Team Nitro" }],
        ["dean king", { division: "Open", team: "Team Nitro" }],
        ["nitin sethi", { division: "Main", team: "The Boast Beasts" }],
        ["spencer williamson", { division: "Open", team: "Even Older and Grumpier" }],
      ]),
    ],
  ]);

  function sortedHandicapPairParts(hcPairs) {
    if (!hcPairs || hcPairs.size === 0) return [];
    const divRank = (d) => (d === "Open" ? 0 : d === "Main" ? 1 : 2);
    const parsed = [...hcPairs].map((s) => {
      const i = s.indexOf("\0");
      const lev = i >= 0 ? s.slice(0, i) : s;
      const team = i >= 0 ? s.slice(i + 1) : "—";
      return { lev: lev || "", team: team || "—" };
    });
    parsed.sort((a, b) => {
      const rd = divRank(a.lev) - divRank(b.lev);
      return rd !== 0 ? rd : a.team.localeCompare(b.team);
    });
    return parsed;
  }

  function formatHandicapDivisionColumn(parts) {
    if (!parts.length) return "N/A";
    return parts.map((p) => p.lev).join("; ");
  }

  function formatHandicapTeamColumn(parts) {
    if (!parts.length) return "N/A";
    return parts.map((p) => p.team).join("; ");
  }

  async function fetchHandicapScheduleRowsForPlayers(level, year) {
    const url = `${apiUrl("/api/schedule")}?level=${encodeURIComponent(level)}&year=${year}`;
    const res = await fetchWithTimeout(url).catch(() => null);
    if (!res || !res.ok) return [];
    const data = await res.json().catch(() => []);
    return Array.isArray(data) ? data : [];
  }

  async function buildPlayersDirectoryRows(year) {
    const y = seasonBoxYear(year);
    const byKey = new Map();
    function ensure(rawName) {
      const disp = canonicalPlayerName(rawName);
      if (!disp) return null;
      const key = disp.toLowerCase();
      if (!byKey.has(key)) {
        byKey.set(key, { displayName: disp, boxes: new Set(), hcPairs: new Set() });
      }
      return byKey.get(key);
    }
    for (const team of getBoxTeamsForYear(y)) {
      const roster = getBoxPlayersForYear(team, y);
      if (!roster || typeof roster !== "object") continue;
      Object.values(roster).forEach((name) => {
        const row = ensure(name);
        if (row) row.boxes.add(team);
      });
    }
    for (const level of ["open", "main"]) {
      const divLabel = level === "open" ? "Open" : "Main";
      const rows = await fetchHandicapScheduleRowsForPlayers(level, y);
      rows.forEach((r) => {
        const t1 = (r.team1 || "").trim() || "—";
        const t2 = (r.team2 || "").trim() || "—";
        splitSchedulePlayerCell(r.team1_players).forEach((n) => {
          const row = ensure(n);
          if (row) row.hcPairs.add(`${divLabel}\0${t1}`);
        });
        splitSchedulePlayerCell(r.team2_players).forEach((n) => {
          const row = ensure(n);
          if (row) row.hcPairs.add(`${divLabel}\0${t2}`);
        });
      });
    }
    const rosterFix = PLAYER_HANDICAP_CANONICAL_ROSTER.get(y);
    if (rosterFix) {
      for (const row of byKey.values()) {
        const fix = rosterFix.get(row.displayName.toLowerCase());
        if (fix) {
          row.hcPairs.clear();
          row.hcPairs.add(`${fix.division}\0${fix.team}`);
        }
      }
    }
    const out = [...byKey.values()].map((r) => {
      const hcParts = sortedHandicapPairParts(r.hcPairs);
      return {
        name: r.displayName,
        box: [...r.boxes].sort((a, b) => a.localeCompare(b)).join(", ") || "—",
        handicapDivision: formatHandicapDivisionColumn(hcParts),
        handicapTeam: formatHandicapTeamColumn(hcParts),
        fn: firstNameSortKey(r.displayName),
        fn2: r.displayName.toLowerCase(),
      };
    });
    out.sort((a, b) => {
      const c = a.fn.localeCompare(b.fn);
      return c !== 0 ? c : a.fn2.localeCompare(b.fn2);
    });
    return out;
  }

  async function renderPlayersTable() {
    const tbody = document.getElementById("tbody-players");
    if (!tbody) return;
    const year = getYearFrom("year-players");
    tbody.innerHTML = "<tr><td colspan=\"4\">Loading…</td></tr>";
    try {
      const rows = await buildPlayersDirectoryRows(year);
      tbody.innerHTML = "";
      if (rows.length === 0) {
        tbody.innerHTML =
          '<tr><td colspan="4" class="empty-state">No players found for this season.</td></tr>';
        return;
      }
      rows.forEach((row) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${escapeHtml(row.name)}</td><td>${escapeHtml(row.box)}</td><td>${escapeHtml(row.handicapDivision)}</td><td>${escapeHtml(row.handicapTeam)}</td>`;
        tbody.appendChild(tr);
      });
    } catch (err) {
      const msg = err && err.message ? err.message : "Unable to load players.";
      tbody.innerHTML = `<tr><td colspan="4">${escapeHtml(msg)}</td></tr>`;
    }
  }

  document.querySelectorAll(".tab").forEach((btn) => {
    if (btn.querySelector("select") || btn.querySelector(".tab-dropdown-panel") || btn.classList.contains("tab-dropdown-trigger")) return;
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  (function initMobileMenu() {
    const toggle = document.getElementById("menu-toggle");
    const menu = document.getElementById("mobile-menu");
    const wrap = toggle && toggle.closest(".mobile-menu-wrap");
    if (!toggle || !menu) return;

    function openMenu() {
      toggle.setAttribute("aria-expanded", "true");
      toggle.setAttribute("aria-label", "Close menu");
      menu.hidden = false;
      menu.classList.add("is-open");
    }
    function closeMenu() {
      toggle.setAttribute("aria-expanded", "false");
      toggle.setAttribute("aria-label", "Open menu");
      menu.hidden = true;
      menu.classList.remove("is-open");
    }

    toggle.addEventListener("click", (e) => {
      e.stopPropagation();
      if (toggle.getAttribute("aria-expanded") === "true") closeMenu();
      else openMenu();
    });
    document.addEventListener("click", (e) => {
      if (menu.classList.contains("is-open") && wrap && !wrap.contains(e.target)) closeMenu();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && menu.classList.contains("is-open")) closeMenu();
    });
    window.addEventListener("resize", () => {
      if (window.matchMedia("(min-width: 769px)").matches && menu.classList.contains("is-open")) closeMenu();
    });

    menu.addEventListener("click", (e) => {
      const btn = e.target.closest(".mobile-menu-item");
      if (!btn) return;
      const tabId = btn.dataset.tab;
      const value = btn.dataset.value;
      if (value && tabId) setYearForTab(tabId, value);
      if (tabId) switchTab(tabId);
      const rulesView = btn.dataset.rulesView;
      if (rulesView) {
        currentRulesView = rulesView;
        updateRulesContent();
      }
      closeMenu();
    });
  })();

  // Custom nav dropdowns (work in Cursor embedded browser and everywhere)
  function closeAllNavDropdowns() {
    document.querySelectorAll(".tab-dropdown-panel").forEach((p) => {
      p.hidden = true;
    });
    document.querySelectorAll(".tab-dropdown-trigger").forEach((b) => {
      b.setAttribute("aria-expanded", "false");
    });
    document.querySelectorAll(".tab-dropdown-wrap").forEach((w) => w.classList.remove("is-open"));
  }
  document.querySelectorAll(".tab-dropdown-trigger").forEach((trigger) => {
    trigger.addEventListener("click", (e) => {
      e.stopPropagation();
      const panel = document.getElementById(trigger.id.replace("-trigger", "-panel"));
      const wrap = trigger.closest(".tab-dropdown-wrap");
      const isOpen = panel && !panel.hidden;
      closeAllNavDropdowns();
      if (!isOpen && panel && wrap) {
        panel.hidden = false;
        trigger.setAttribute("aria-expanded", "true");
        wrap.classList.add("is-open");
      }
    });
  });
  document.addEventListener("click", (e) => {
    const option = e.target.closest(".tab-dropdown-option");
    if (option) {
      e.stopPropagation();
      const tabId = option.dataset.tab;
      const value = option.dataset.value;
      if (value && tabId) setYearForTab(tabId, value);
      if (tabId) switchTab(tabId);
      const rulesView = option.dataset.rulesView;
      if (rulesView) {
        currentRulesView = rulesView;
        updateRulesContent();
      }
      closeAllNavDropdowns();
    } else if (!e.target.closest(".tab-dropdown-trigger")) {
      closeAllNavDropdowns();
    }
  });

  document.querySelectorAll(".standings-tab").forEach((btn) => {
    btn.addEventListener("click", () => switchStandingsTab(btn.dataset.standings));
  });

  document.querySelectorAll(".schedule-tab").forEach((btn) => {
    btn.addEventListener("click", () =>
      switchScheduleTab(btn.dataset.scheduleLevel)
    );
  });

  document.querySelectorAll(".schedules-tab").forEach((btn) => {
    btn.addEventListener("click", () => switchSchedulesBranch(btn.dataset.schedulesBranch));
  });

  const scheduleBoxTabBar = document.querySelector("#schedule-panel-box .box-tabs");
  if (scheduleBoxTabBar) {
    scheduleBoxTabBar.addEventListener("click", (e) => {
      const btn = e.target.closest(".box-tab");
      if (!btn || !scheduleBoxTabBar.contains(btn)) return;
      scheduleBoxTabBar.querySelectorAll(".box-tab").forEach((t) => {
        t.classList.toggle("active", t === btn);
      });
      void renderBoxSchedule();
    });
  }

  const standingsBoxTabBar = document.querySelector("#standings-box .standings-box-tabs");
  if (standingsBoxTabBar) {
    standingsBoxTabBar.addEventListener("click", (e) => {
      const btn = e.target.closest(".box-tab");
      if (!btn || !standingsBoxTabBar.contains(btn)) return;
      standingsBoxTabBar.querySelectorAll(".box-tab").forEach((t) => {
        t.classList.toggle("active", t === btn);
      });
      void renderBoxStandings();
    });
  }

  document.getElementById("league").addEventListener("change", () => {
    const form = document.getElementById("score-form");
    if (!form) return;
    if (form.league.value === "box") {
      fillLevelOptionsForLeague("box");
      fillWeekOptions("box");
      fillSingleTeamSideOptions("", "");
      clearScoreFormPlayers();
    } else {
      fillLevelOptionsForLeague("handicap");
      fillWeekOptions("handicap");
      fillSingleTeamSideOptions("", "");
      clearScoreFormPlayers();
    }
    updateHandicapFieldsVisibility();
    updateScoreFormTeamsFromLeagueAndLevel();
  });

  document.getElementById("level").addEventListener("change", () => {
    const form = document.getElementById("score-form");
    if (!form) return;
    if (form.league.value === "box") {
      fillWeekOptions("box");
      autoPopulateBoxPlayersInForm();
      return;
    }
    updateScoreFormTeamsFromLeagueAndLevel();
  });

  document.getElementById("week").addEventListener("change", autoPopulateBoxPlayersInForm);
  document.getElementById("team1").addEventListener("change", autoPopulateBoxPlayersInForm);
  document.getElementById("team2").addEventListener("change", autoPopulateBoxPlayersInForm);

  document.getElementById("score-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const league = form.league.value;
    const level = form.level.value;
    const week = form.week.value;
    const handicap_team1 = form.handicap_team1.value.trim();
    const handicap_team2 = form.handicap_team2.value.trim();
    const team1 = form.team1.value.trim();
    const team2 = form.team2.value.trim();
    const team1Players = [
      form.team1_player1.value.trim(),
      form.team1_player2.value.trim(),
    ]
      .filter(Boolean)
      .join(", ");
    const team2Players = [
      form.team2_player1.value.trim(),
      form.team2_player2.value.trim(),
    ]
      .filter(Boolean)
      .join(", ");
    const games1 = parseInt(form.games1.value, 10) || 0;
    const games2 = parseInt(form.games2.value, 10) || 0;
    if (games1 > 3 || games2 > 3) {
      alert("No team can win more than 3 games.");
      return;
    }
    if (games1 + games2 > 5) {
      alert("Best of 5: total games won cannot exceed 5.");
      return;
    }
    if (team1 === team2) {
      alert("Team 1 and Team 2 must be different.");
      return;
    }
    try {
      await postScore({
        league,
        level,
        week,
        handicap_team1: handicap_team1 || undefined,
        handicap_team2: handicap_team2 || undefined,
        team1,
        team2,
        games1,
        games2,
        team1_players: team1Players || undefined,
        team2_players: team2Players || undefined,
      });
      if (league === "box") {
        boxScheduleMergeCache.clear();
        const yIn = getYearFrom("year-input");
        await refreshBoxScoresMergeCache(level, yIn);
        void renderBoxSchedule();
        void renderBoxStandings();
      }
      form.week.value = "";
      form.week.selectedIndex = 0;
      form.handicap_team1.value = "";
      form.handicap_team2.value = "";
      form.team1_player1.value = "";
      form.team1_player2.value = "";
      form.team2_player1.value = "";
      form.team2_player2.value = "";
      form.games1.value = 0;
      form.games2.value = 0;
      updateScoreFormTeamsFromLeagueAndLevel();
      switchTab("standings");
    } catch (err) {
      alert(err.message || "Failed to submit score");
    }
  });

  const notificationsForm = document.getElementById("notifications-form");
  const notificationsStatus = document.getElementById("notifications-status");
  const notificationsRemoveBtn = document.getElementById("notify-remove");
  if (notificationsForm && notificationsStatus && notificationsRemoveBtn) {
    function setNotificationsStatusUi(text, variant) {
      notificationsStatus.textContent = text;
      notificationsStatus.classList.remove(
        "notifications-status--success",
        "notifications-status--error"
      );
      if (variant === "success") notificationsStatus.classList.add("notifications-status--success");
      else if (variant === "error") notificationsStatus.classList.add("notifications-status--error");
    }

    notificationsForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = notificationsForm.notify_name.value.trim();
      const email = notificationsForm.notify_email.value.trim();
      const notifyHandicap = !!notificationsForm.notify_handicap.checked;
      const notifyBox = !!notificationsForm.notify_box.checked;
      if (!name || !email) {
        setNotificationsStatusUi("Please enter both name and email.", "error");
        return;
      }
      try {
        const data = await saveNotificationSubscription({
          name,
          email,
          notifyHandicap,
          notifyBox,
        });
        const parts = [];
        if (notifyHandicap) parts.push("handicap league");
        if (notifyBox) parts.push("box league");
        let msg;
        let variant = "success";
        if (parts.length > 0) {
          msg = `You're signed up for email notifications (${parts.join(" and ")}).`;
          if (data.welcome_email_sent) {
            msg += " We sent a short confirmation to your inbox.";
          } else {
            msg += " Your preferences are saved on the server.";
          }
        } else {
          msg =
            "Saved. No leagues selected — you won't receive emails until you check at least one.";
          variant = "neutral";
        }
        setNotificationsStatusUi(msg, variant);
        refreshNotificationsServerHint();
      } catch (err) {
        setNotificationsStatusUi(err.message || "Unable to save notification settings.", "error");
      }
    });

    notificationsRemoveBtn.addEventListener("click", async () => {
      const email = notificationsForm.notify_email.value.trim();
      if (!email) {
        setNotificationsStatusUi("Enter your email first, then click Remove.", "error");
        return;
      }
      try {
        await removeNotificationSubscription(email);
        notificationsForm.notify_handicap.checked = false;
        notificationsForm.notify_box.checked = false;
        notificationsForm.notify_name.value = "";
        notificationsForm.notify_email.value = "";
        setNotificationsStatusUi("Your email has been removed from notifications.", "success");
        refreshNotificationsServerHint();
      } catch (err) {
        setNotificationsStatusUi(err.message || "Unable to remove email.", "error");
      }
    });
  }

  // Initialize score-form selectors using current league/level selection.
  const initialForm = document.getElementById("score-form");
  if (initialForm && initialForm.league.value === "box") {
    fillLevelOptionsForLeague("box");
    fillWeekOptions("box");
  } else {
    fillLevelOptionsForLeague("handicap");
    fillWeekOptions("handicap");
  }
  updateHandicapFieldsVisibility();
  updateScoreFormTeamsFromLeagueAndLevel();

  // Initialize season dropdowns from backend SEASON_YEARS (after DOM ready so mobile menu uls exist)
  function runInitYearDropdowns() {
    initYearDropdowns();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", runInitYearDropdowns);
  } else {
    runInitYearDropdowns();
  }

  // Register service worker for PWA install and offline shell
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
  }
})();
