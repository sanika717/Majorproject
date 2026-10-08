/**
 * UrbanPulse - Frontend API Client
 * Connects frontend to the FastAPI + PostgreSQL backend.
 * Provides data fetching for Dashboard, Analytics, Complaints, and ESG.
 * Sends the Supabase access token as a Bearer header.
 * Tokens are kept in memory (closure/sessionStorage) rather than persisting long-term in localStorage.
 */

const UrbanPulseAPI = (function() {
  // In-memory token storage (preferred over localStorage to mitigate persistent XSS extraction)
  let _accessToken = null;
  let _currentUser = null;

  // Attempt to read from sessionStorage (cleared on tab close) if available
  try {
    _accessToken = sessionStorage.getItem("up_access_token") || null;
  } catch (e) {
    _accessToken = null;
  }

  // Determine API base URL dynamically
  const isHttp = window.location.protocol.startsWith("http");
  const host = window.location.hostname || "127.0.0.1";
  const port = window.location.port;
  
  // If served directly from FastAPI (port 8000), use relative path; otherwise localhost:8000
  const API_BASE = isHttp && port === "8000"
    ? "/api/v1"
    : `http://${host}:8000/api/v1`;

  function getHeaders(customHeaders = {}) {
    const headers = {
      "Accept": "application/json",
      ...customHeaders
    };
    if (_accessToken) {
      headers["Authorization"] = `Bearer ${_accessToken}`;
    }
    return headers;
  }

  async function get(endpoint, params = {}) {
    const url = new URL(`${API_BASE}${endpoint}`, window.location.origin);
    Object.keys(params).forEach(key => {
      if (params[key] !== undefined && params[key] !== null) {
        url.searchParams.append(key, params[key]);
      }
    });

    try {
      const response = await fetch(url.toString(), {
        headers: getHeaders()
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

  async function post(endpoint, data = {}) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(data)
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }
    return await response.json();
  }

  return {
    baseUrl: API_BASE,

    setSession(token, user = null) {
      _accessToken = token;
      _currentUser = user;
      try {
        if (token) {
          sessionStorage.setItem("up_access_token", token);
        } else {
          sessionStorage.removeItem("up_access_token");
        }
      } catch (e) {}
    },

    clearSession() {
      _accessToken = null;
      _currentUser = null;
      try {
        sessionStorage.removeItem("up_access_token");
      } catch (e) {}
    },

    getToken() {
      return _accessToken;
    },

    getUser() {
      return _currentUser;
    },

    getHeaders,

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

    // Complaints
    async submitComplaint(data) {
      return await post("/complaints/", data);
    },

    async trackComplaint(ticket_id, secret) {
      return await post("/complaints/track", { ticket_id, secret });
    },

    async getMyComplaints() {
      return await get("/complaints/my");
    },

    // Auth
    async getRoles() {
      return await get("/auth/roles");
    },

    async login(username_or_email, password) {
      try {
        const data = await post("/auth/login", { username_or_email, password });
        if (data.access_token) {
          this.setSession(data.access_token, data.user);
        }
        return data;
      } catch (err) {
        console.error("[UrbanPulseAPI] Login failed:", err);
        throw err;
      }
    }
  };
})();

// Attach globally
window.UrbanPulseAPI = UrbanPulseAPI;
