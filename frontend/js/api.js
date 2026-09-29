/**
 * UrbanPulse - Frontend API Client
 * Connects frontend to the FastAPI + PostgreSQL backend.
 * Provides data fetching for Dashboard and Analytics pages with graceful fallback to cached verified EDA.
 */

const UrbanPulseAPI = (function() {
  // Determine API base URL dynamically
  const isHttp = window.location.protocol.startsWith("http");
  const host = window.location.hostname || "127.0.0.1";
  const port = window.location.port;
  
  // If served directly from FastAPI (port 8000), use relative path; otherwise localhost:8000
  const API_BASE = isHttp && port === "8000"
    ? "/api/v1"
    : `http://${host}:8000/api/v1`;

  async function get(endpoint, params = {}) {
    const url = new URL(`${API_BASE}${endpoint}`, window.location.origin);
    Object.keys(params).forEach(key => {
      if (params[key] !== undefined && params[key] !== null) {
        url.searchParams.append(key, params[key]);
      }
    });

    try {
      const response = await fetch(url.toString(), {
        headers: { "Accept": "application/json" }
      });
      if (!response.ok) {
        throw new Error(`API error ${response.status}: ${response.statusText}`);
      }
      return await response.json();
    } catch (err) {
      console.warn(`[UrbanPulseAPI] Request to ${endpoint} failed:`, err.message);
      return null;
    }
  }

  return {
    baseUrl: API_BASE,

    // Dashboard
    async getDashboardKPIs() {
      return await get("/dashboard/kpis");
    },

    // Construction
    async getConstructionOverview() {
      return await get("/construction/overview");
    },

    async getConstructionClustering() {
      return await get("/construction/clustering");
    },

    async getTopWards(by = "investment", limit = 15) {
      return await get("/construction/top-wards", { by, limit });
    },

    async getCategoryTags() {
      return await get("/construction/category-tags");
    },

    async getWardLevelData() {
      return await get("/construction/wards");
    },

    async getFullConstructionData() {
      return await get("/construction/full-data");
    },

    // Crime
    async getCrimeHistorical() {
      return await get("/crime/historical");
    },

    async getCrimeRiskFormula() {
      return await get("/crime/risk-formula");
    },

    async getCrimeAnalytics(category = "all", year = "2023") {
      return await get("/crime/analytics", { category, year });
    },

    async getFullCrimeData() {
      return await get("/crime/full-data");
    },

    // Police
    async getPoliceLocations(category = null) {
      return await get("/police/locations", category ? { category } : {});
    },

    async getPoliceSummary() {
      return await get("/police/summary");
    },

    // Auth
    async getRoles() {
      return await get("/auth/roles");
    },

    async login(username_or_email, password) {
      try {
        const response = await fetch(`${API_BASE}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username_or_email, password })
        });
        if (!response.ok) {
          const err = await response.json();
          throw new Error(err.detail || "Authentication failed");
        }
        return await response.json();
      } catch (err) {
        console.error("[UrbanPulseAPI] Login failed:", err);
        throw err;
      }
    }
  };
})();

// Attach globally
window.UrbanPulseAPI = UrbanPulseAPI;
