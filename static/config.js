// Set this when hosting the UI on GitHub Pages. If not set, the app will throw when
// loading Schedule/Standings/Input and dropdown selections may seem to do nothing.
// When opened from localhost or from the Render app itself, use same origin so API requests work.
(function () {
  if (typeof window === "undefined") return;
  var host = window.location.hostname || "";
  var isLocal = host === "localhost" || host === "127.0.0.1";
  var isOnRender = host === "river-city-doubles.onrender.com";
  window.RCD_API_BASE = window.RCD_API_BASE ?? (isLocal || isOnRender ? "" : "https://river-city-doubles.onrender.com");
})();

