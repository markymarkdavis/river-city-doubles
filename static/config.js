// Set this when hosting the UI on GitHub Pages. If not set, the app will throw when
// loading Schedule/Standings/Input and dropdown selections may seem to do nothing.
// When opened from localhost, use the same origin (local Flask) so you see local data.
(function () {
  var isLocal = typeof window !== "undefined" && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1");
  window.RCD_API_BASE = window.RCD_API_BASE ?? (isLocal ? "" : "https://river-city-doubles.onrender.com");
})();

