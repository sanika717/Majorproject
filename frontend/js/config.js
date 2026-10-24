/**
 * UrbanPulse Frontend Supabase Configuration
 * Public configuration values for Supabase client & authentication.
 * 
 * You can set SUPABASE_URL and SUPABASE_ANON_KEY either:
 * 1. Directly in this file or via window.__SUPABASE_URL / window.__SUPABASE_ANON_KEY
 * 2. In your backend .env file (SUPABASE_URL and SUPABASE_ANON_KEY), and
 *    ensureEnvConfig() will automatically load them via /api/v1/auth/config.
 * 
 * Note: Keep SUPABASE_JWT_SECRET and SUPABASE_SERVICE_ROLE_KEY private on the backend.
 * Only the public anon key is exposed here.
 */

window.ENV_CONFIG = {
  // Fill with your Supabase Project URL and public anon key
  SUPABASE_URL: window.__SUPABASE_URL || localStorage.getItem("up_supabase_url") || "",
  SUPABASE_ANON_KEY: window.__SUPABASE_ANON_KEY || localStorage.getItem("up_supabase_anon_key") || ""
};

/**
 * Ensures configuration is loaded, querying backend /api/v1/auth/config if needed.
 */
window.ensureEnvConfig = async function() {
  if (window.ENV_CONFIG.SUPABASE_URL && window.ENV_CONFIG.SUPABASE_ANON_KEY) {
    return window.ENV_CONFIG;
  }

  try {
    const isHttp = window.location.protocol.startsWith("http");
    const host = window.location.hostname || "127.0.0.1";
    const port = window.location.port;
    const apiBase = isHttp && port === "8000" ? "/api/v1" : `http://${host}:8000/api/v1`;

    const res = await fetch(`${apiBase}/auth/config`);
    if (res.ok) {
      const data = await res.json();
      if (data.supabase_url && !window.ENV_CONFIG.SUPABASE_URL) {
        window.ENV_CONFIG.SUPABASE_URL = data.supabase_url;
      }
      if (data.supabase_anon_key && !window.ENV_CONFIG.SUPABASE_ANON_KEY) {
        window.ENV_CONFIG.SUPABASE_ANON_KEY = data.supabase_anon_key;
      }
    }
  } catch (err) {
    // API not reachable or offline; fall back to static config
    console.debug("[UrbanPulse Config] Backend config fetch note:", err.message);
  }

  return window.ENV_CONFIG;
};

// Export for ES modules or standard script tag access
if (typeof module !== "undefined" && module.exports) {
  module.exports = window.ENV_CONFIG;
}
