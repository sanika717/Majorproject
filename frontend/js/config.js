/**
 * UrbanPulse Frontend Supabase Configuration
 * Public configuration values for Supabase client & authentication.
 * Note: Keep SUPABASE_JWT_SECRET private on the backend. Only public anon keys are exposed here.
 */

window.ENV_CONFIG = {
  // Replace with your project Supabase URL and public anon key from Supabase Dashboard -> Project Settings -> API
  SUPABASE_URL: window.__SUPABASE_URL || "",
  SUPABASE_ANON_KEY: window.__SUPABASE_ANON_KEY || ""
};

// Export for ES modules or standard script tag access
if (typeof module !== "undefined" && module.exports) {
  module.exports = window.ENV_CONFIG;
}
