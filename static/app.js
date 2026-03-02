(function () {
  const API_BASE = "";

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
    const res = await fetch(API_BASE + "/api/scores", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        league: entry.league,
        level: entry.level,
        week: Number(entry.week),
        year: getSelectedYear(),
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
    const year = getSelectedYear();
    const res = await fetch(
      `${API_BASE}/api/standings/${encodeURIComponent(league)}/${encodeURIComponent(level)}?year=${year}`
    );
    if (!res.ok) throw new Error("Failed to load standings");
    return res.json();
  }

  function getSelectedYear() {
    const el = document.getElementById("year");
    return el ? parseInt(el.value, 10) : 2025;
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
  }

  async function fetchSchedule(level) {
    const year = getSelectedYear();
    const res = await fetch(
      `${API_BASE}/api/schedule?level=${encodeURIComponent(level)}&year=${year}`
    );
    if (!res.ok) throw new Error("Failed to load schedule");
    return res.json();
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
    renderScheduleTable(level);
  }

  async function renderScheduleTable(level) {
    const tbody = document.getElementById(`schedule-tbody-${level}`);
    const emptyEl = document.getElementById(`empty-schedule-${level}`);
    tbody.innerHTML = "";
    try {
      const rows = await fetchSchedule(level);
      if (rows.length === 0) {
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
    } catch {
      emptyEl.textContent = "Unable to load schedule. Is the server running?";
      emptyEl.hidden = false;
    }
  }

  function renderSchedule() {
    renderScheduleTable("open");
    renderScheduleTable("main");
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
    renderStandingsTable(standingsId);
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
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
    } catch {
      const tr = document.createElement("tr");
      tr.innerHTML = '<td colspan="6">Unable to load standings. Is the server running?</td>';
      tbody.appendChild(tr);
    }
  }

  function renderStandings() {
    renderStandingsTable("handicap-open");
    renderStandingsTable("handicap-main");
  }

  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  document.querySelectorAll(".standings-tab").forEach((btn) => {
    btn.addEventListener("click", () => switchStandingsTab(btn.dataset.standings));
  });

  document.querySelectorAll(".schedule-tab").forEach((btn) => {
    btn.addEventListener("click", () =>
      switchScheduleTab(btn.dataset.scheduleLevel)
    );
  });

  document.getElementById("year").addEventListener("change", () => {
    const tab = document.querySelector(".tab.active");
    if (tab && tab.dataset.tab === "standings") renderStandings();
    if (tab && tab.dataset.tab === "schedule") renderSchedule();
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
})();
