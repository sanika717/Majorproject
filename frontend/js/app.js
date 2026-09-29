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

  // 3. Update Live Clock
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
});
