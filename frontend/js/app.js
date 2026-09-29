/**
 * UrbanPulse - Main Application Controller
 * Each page loads only the scripts it needs; this controller initializes whatever
 * modules are present on the current page.
 */

document.addEventListener("DOMContentLoaded", () => {
  // 1. Smart City Map (Dashboard page only)
  if (document.getElementById("urbanpulse-map") && typeof window.initUrbanPulseMap === "function") {
    window.initUrbanPulseMap();
  }

  // 2. Crime Analytics (Analytics page only)
  if (document.getElementById("crime-trend-chart") && typeof window.initUrbanPulseCrimeAnalytics === "function") {
    window.initUrbanPulseCrimeAnalytics();
  }

  // 2b. Construction Analytics (Analytics page only)
  if (document.getElementById("construction-investment-chart") && typeof window.initUrbanPulseConstructionAnalytics === "function") {
    window.initUrbanPulseConstructionAnalytics();
  }

  // 3. Update Live Clock (all pages)
  function updateClock() {
    const clockEl = document.getElementById("live-time-display");
    if (clockEl) {
      const now = new Date();
      clockEl.textContent = now.toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true
      }) + " IST";
    }
  }
  updateClock();
  setInterval(updateClock, 1000);

  // 4. API status indicator
  async function checkAPIStatus() {
    const pill = document.querySelector(".status-pill");
    const pillText = pill ? pill.querySelector("span:last-child") : null;
    const dot = pill ? pill.querySelector(".pulse-dot") : null;

    if (!pill) return;

    try {
      if (!window.UrbanPulseAPI) return;
      const health = await fetch(`${window.UrbanPulseAPI.baseUrl}/health`).then(r => r.json()).catch(() => null);
      if (health && health.status === "healthy") {
        if (pillText) pillText.textContent = "Live · API Connected";
        if (dot) dot.style.background = "var(--accent-emerald, #10b981)";
        pill.title = `UrbanPulse FastAPI backend running · PostgreSQL connected`;
      } else {
        if (pillText) pillText.textContent = "Bengaluru Live Intelligence";
        if (dot) dot.style.background = "";
      }
    } catch (_) {
      if (pillText) pillText.textContent = "Bengaluru Live Intelligence";
    }
  }
  checkAPIStatus();
});
