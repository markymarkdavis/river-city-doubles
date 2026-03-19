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
      B: "Frank Devenoge",
      C: "Dave Shepardson",
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

  // Parse "X & Y vs Z & W" -> { team1: [X,Y], team2: [Z,W] }
  function parseMatchup(matchup) {
    const m = matchup.match(/^([A-F]) & ([A-F]) vs ([A-F]) & ([A-F])$/);
    if (!m) return { team1: [], team2: [] };
    return { team1: [m[1], m[2]], team2: [m[3], m[4]] };
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

  // Get player totals for a box, sorted by total descending.
  function getBoxPlayerTotals(team) {
    const rows = getFullBoxRows(team);
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
    const players = BOX_PLAYERS && BOX_PLAYERS[team];
    return ["A", "B", "C", "D", "E", "F"]
      .map((letter) => ({
        letter,
        name: (players && players[letter]) || "",
        total: playerTotals[letter],
      }))
      .sort((a, b) => b.total - a.total);
  }

  // Build full 15 rows for a box, merging canonical matchups with recorded scores.
  function getFullBoxRows(team) {
    const recorded = (BOX_SCHEDULES[team] || []).reduce((acc, r) => {
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
        dates: m.dates,
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

  function fillTeamDropdowns(level) {
    const teams = getTeamsForLevel(level);
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

  const YEAR_SELECT_IDS = ["year-schedule", "year-input", "year-standings"];
  const TAB_TO_YEAR_SELECT = { schedule: "year-schedule", input: "year-input", standings: "year-standings" };

  function setYearForTab(tabId, value) {
    const selectId = TAB_TO_YEAR_SELECT[tabId];
    if (!selectId || value === undefined) return;
    const year = typeof value === "string" ? parseInt(value.split("-")[0], 10) : value;
    const select = document.getElementById(selectId);
    if (select && !Number.isNaN(year)) select.value = String(year);
  }

  function fillYearOptions(years) {
    if (!Array.isArray(years) || years.length === 0) return;
    const latest = Math.max.apply(null, years);
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
      select.value = String(latest);
    });

    const panelIds = ["nav-schedule-panel", "nav-input-panel", "nav-standings-panel"];
    const tabIds = ["schedule", "input", "standings"];
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

    const mobileListIds = ["mobile-menu-schedule", "mobile-menu-input", "mobile-menu-standings"];
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

  async function initYearDropdowns() {
    fillYearOptions([2025]); // default to 2025-2026 season until API responds
    try {
      const years = await fetchYears();
      if (Array.isArray(years) && years.length > 0) {
        fillYearOptions(years);
      }
    } catch (err) {
      console.error("Failed to load years:", err);
    }
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
    if (tabId === "standings") renderStandings();
    if (tabId === "schedule") renderSchedule();
    if (tabId === "rules") updateRulesContent();
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
      // Box league schedule is static, per-team, not from the API
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

  function switchScheduleTab(level) {
    document.querySelectorAll(".schedule-tab").forEach((t) => {
      t.classList.toggle("active", t.dataset.scheduleLevel === level);
    });
    document.querySelectorAll(".schedule-panel").forEach((p) => {
      const id = p.id.replace("schedule-panel-", "");
      p.classList.toggle("active", id === level);
      p.hidden = id !== level;
    });
    if (level === "box") {
      renderBoxSchedule();
    } else {
      renderScheduleTable(level);
    }
  }

  async function renderScheduleTable(level) {
    const tbody = document.getElementById(`schedule-tbody-${level}`);
    const emptyEl = document.getElementById(`empty-schedule-${level}`);
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

  function renderSchedule() {
    renderScheduleTable("open");
    renderScheduleTable("main");
    renderBoxSchedule();
  }

  function renderBoxSchedule() {
    const tbody = document.getElementById("schedule-tbody-box");
    if (!tbody) return;
    const activeTab = document.querySelector(".box-tab.active");
    const team = activeTab ? activeTab.dataset.boxTeam : "Foo Fighters";
    const rows = getFullBoxRows(team);
    tbody.innerHTML = "";

    // Update player headers (A..F = name) to match this box.
    const headerCells = document.querySelectorAll(".box-player-header");
    const players = BOX_PLAYERS && BOX_PLAYERS[team];
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
      tr.innerHTML = `
        <td>${escapeHtml(row.matchup)}</td>
        <td>${escapeHtml(row.dates)}</td>
        <td>${row.team1}</td>
        <td>${row.team2}</td>
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
      renderBoxStandings();
    } else {
      renderStandingsTable(standingsId);
    }
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function renderBoxStandings() {
    const tbody = document.getElementById("tbody-standings-box");
    if (!tbody) return;
    const activeTab = document.querySelector(".standings-box-tabs .box-tab.active");
    const team = activeTab ? activeTab.dataset.standingsBox : "Foo Fighters";
    const rows = getBoxPlayerTotals(team);
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

  function renderStandings() {
    renderStandingsTable("handicap-open");
    renderStandingsTable("handicap-main");
    renderBoxStandings();
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

  document.querySelectorAll("#schedule-panel-box .box-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#schedule-panel-box .box-tab").forEach((t) => {
        t.classList.toggle("active", t === btn);
      });
      renderBoxSchedule();
    });
  });

  document.querySelectorAll(".standings-box-tabs .box-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".standings-box-tabs .box-tab").forEach((t) => {
        t.classList.toggle("active", t === btn);
      });
      renderBoxStandings();
    });
  });

  document.getElementById("level").addEventListener("change", () => {
    const level = document.getElementById("level").value;
    fillTeamDropdowns(level);
  });

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
      fillTeamDropdowns(level);
      switchTab("standings");
    } catch (err) {
      alert(err.message || "Failed to submit score");
    }
  });

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
