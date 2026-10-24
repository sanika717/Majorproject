/**
 * UrbanPulse - Supabase Authentication & Role Management Module
 * Production-ready integration for Supabase Auth with FastAPI backend verification.
 * 
 * Features:
 * - Public Citizen & Administrator pathways
 * - Robust session persistence & auto-refresh
 * - Strict role validation against server-side PostgreSQL / trusted claims
 * - Password recovery & update workflows
 * - Route guards and UI header synchronization
 */

const UrbanPulseAuth = (function() {
  let _supabase = null;
  let _initPromise = null;

  /**
   * Initializes the Supabase client
   */
  async function init() {
    if (_supabase) return _supabase;
    if (_initPromise) return _initPromise;

    _initPromise = (async () => {
      // 1. Ensure configuration is loaded (fetches /api/v1/auth/config if empty)
      if (typeof window.ensureEnvConfig === "function") {
        await window.ensureEnvConfig();
      }

      const supabaseUrl = window.ENV_CONFIG && window.ENV_CONFIG.SUPABASE_URL;
      const supabaseKey = window.ENV_CONFIG && window.ENV_CONFIG.SUPABASE_ANON_KEY;

      if (!supabaseUrl || !supabaseKey) {
        console.warn("[UrbanPulseAuth] Supabase URL or Anon Key is missing. Check config.js or backend .env.");
        return null;
      }

      if (typeof window.supabase === "undefined" || !window.supabase.createClient) {
        console.error("[UrbanPulseAuth] Supabase JS library (@supabase/supabase-js) is not loaded.");
        return null;
      }

      _supabase = window.supabase.createClient(supabaseUrl, supabaseKey, {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
          detectSessionInUrl: true,
          storage: window.localStorage
        }
      });

      // Synchronize initial session with UrbanPulseAPI
      const { data: { session } } = await _supabase.auth.getSession();
      if (session) {
        _syncSessionWithAPI(session);
      }

      // Listen for auth state changes
      _supabase.auth.onAuthStateChange(async (event, session) => {
        _syncSessionWithAPI(session);

        if (event === "SIGNED_IN" && session) {
          try {
            await syncUserWithBackend(session.access_token);
          } catch (e) {
            console.debug("[UrbanPulseAuth] User sync notice:", e.message);
          }
        } else if (event === "SIGNED_OUT") {
          if (window.UrbanPulseAPI) {
            window.UrbanPulseAPI.clearSession();
          }
        }

        // Notify other components & UI
        window.dispatchEvent(new CustomEvent("up-auth-state-change", { detail: { event, session } }));
      });

      return _supabase;
    })();

    return _initPromise;
  }

  function _syncSessionWithAPI(session) {
    if (window.UrbanPulseAPI) {
      if (session && session.access_token) {
        window.UrbanPulseAPI.setSession(session.access_token, session.user);
      } else {
        window.UrbanPulseAPI.clearSession();
      }
    }
  }

  /**
   * Syncs the authenticated Supabase user into the backend PostgreSQL database
   */
  async function syncUserWithBackend(accessToken) {
    if (!accessToken && window.UrbanPulseAPI) {
      accessToken = window.UrbanPulseAPI.getToken();
    }
    if (!accessToken) return null;

    try {
      const isHttp = window.location.protocol.startsWith("http");
      const host = window.location.hostname || "127.0.0.1";
      const port = window.location.port;
      const apiBase = isHttp && port === "8000" ? "/api/v1" : `http://${host}:8000/api/v1`;

      const res = await fetch(`${apiBase}/auth/sync`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${accessToken}`,
          "Content-Type": "application/json"
        }
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn("[UrbanPulseAuth] Backend sync failed:", err.message);
    }
    return null;
  }

  /**
   * Register a new account with email, password, and full name
   */
  async function signUp({ email, password, fullName }) {
    const client = await init();
    if (!client) {
      throw new Error("Supabase is not configured yet. Please configure SUPABASE_URL and SUPABASE_ANON_KEY.");
    }

    if (!email || !password) {
      throw new Error("Email and password are required.");
    }
    if (password.length < 8) {
      throw new Error("Password must be at least 8 characters long.");
    }

    const { data, error } = await client.auth.signUp({
      email: email.trim().toLowerCase(),
      password,
      options: {
        data: {
          full_name: fullName ? fullName.trim() : ""
        }
      }
    });

    if (error) {
      throw error;
    }

    if (data.session) {
      _syncSessionWithAPI(data.session);
      await syncUserWithBackend(data.session.access_token);
    }

    return data;
  }

  /**
   * Log in a user with email and password, handling public vs administrator pathway
   */
  async function signIn({ email, password, loginType = "public" }) {
    const client = await init();
    if (!email || !password) {
      throw new Error("Email and password are required.");
    }

    // Try Supabase Auth first if configured
    if (client) {
      try {
        const { data, error } = await client.auth.signInWithPassword({
          email: email.trim().toLowerCase(),
          password
        });
        if (!error && data && data.session) {
          const session = data.session;
          const user = data.user;
          _syncSessionWithAPI(session);

          if (loginType === "admin") {
            const adminCheck = await verifyAdminRole(session.access_token);
            if (!adminCheck || !adminCheck.is_admin) {
              await client.auth.signOut();
              _syncSessionWithAPI(null);
              throw new Error("Access Denied: Your account does not possess verified civic administrator credentials.");
            }
          }
          return { data, user, session };
        }
      } catch (sbErr) {
        if (sbErr.message && sbErr.message.includes("Access Denied")) {
          throw sbErr;
        }
        // If Supabase failed or is unconfigured, continue to backend direct auth
      }
    }

    // Direct FastAPI Authentication Fallback (Database-backed)
    if (window.UrbanPulseAPI && typeof window.UrbanPulseAPI.login === "function") {
      const loginRes = await window.UrbanPulseAPI.login(email.trim().toLowerCase(), password);
      if (loginRes && loginRes.access_token) {
        const user = loginRes.user || {};
        const role = (user.role || "").toLowerCase();
        if (loginType === "admin" && role !== "admin") {
          window.UrbanPulseAPI.clearSession();
          throw new Error("Access Denied: Your account does not possess verified civic administrator credentials.");
        }
        const sessionObj = {
          access_token: loginRes.access_token,
          user: user
        };
        _syncSessionWithAPI(sessionObj);
        window.dispatchEvent(new CustomEvent("up-auth-state-change", { detail: { event: "SIGNED_IN", session: sessionObj } }));
        return { data: loginRes, user: user, session: sessionObj };
      }
    }

    throw new Error("Invalid login credentials. Please check your username/email and password.");
  }

  /**
   * Verifies if the token belongs to an administrator using FastAPI backend endpoint
   */
  async function verifyAdminRole(accessToken) {
    if (!accessToken) {
      if (window.UrbanPulseAPI && window.UrbanPulseAPI.getToken()) {
        accessToken = window.UrbanPulseAPI.getToken();
      } else {
        const session = await getSession();
        accessToken = session ? session.access_token : null;
      }
    }
    if (!accessToken) {
      return { is_admin: false, detail: "No authenticated session" };
    }

    const isHttp = window.location.protocol.startsWith("http");
    const host = window.location.hostname || "127.0.0.1";
    const port = window.location.port;
    const apiBase = isHttp && port === "8000" ? "/api/v1" : `http://${host}:8000/api/v1`;

    const res = await fetch(`${apiBase}/auth/admin-check`, {
      headers: {
        "Authorization": `Bearer ${accessToken}`,
        "Accept": "application/json"
      }
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return {
        is_admin: false,
        detail: err.detail || `Server returned ${res.status}`
      };
    }

    const data = await res.json();
    return {
      is_admin: Boolean(data.is_admin),
      role: data.role,
      user: data.user
    };
  }

  /**
   * Request password reset email through Supabase Auth
   */
  async function resetPasswordForEmail(email, customRedirectUrl = null) {
    const client = await init();
    if (!client) {
      throw new Error("Supabase is not configured yet. Please configure SUPABASE_URL and SUPABASE_ANON_KEY.");
    }

    if (!email) {
      throw new Error("Email address is required.");
    }

    // Default redirect to reset-password.html on the same host
    const origin = window.location.origin;
    const pathname = window.location.pathname;
    let redirectUrl = customRedirectUrl;
    if (!redirectUrl) {
      const basePath = pathname.substring(0, pathname.lastIndexOf("/"));
      redirectUrl = `${origin}${basePath}/reset-password.html`;
    }

    const { data, error } = await client.auth.resetPasswordForEmail(email.trim().toLowerCase(), {
      redirectTo: redirectUrl
    });

    if (error) {
      throw error;
    }

    return data;
  }

  /**
   * Update password (used on reset-password page after clicking recovery link)
   */
  async function updateUserPassword(newPassword) {
    const client = await init();
    if (!client) {
      throw new Error("Supabase is not configured yet.");
    }

    if (!newPassword || newPassword.length < 8) {
      throw new Error("New password must be at least 8 characters long.");
    }

    const { data, error } = await client.auth.updateUser({
      password: newPassword
    });

    if (error) {
      throw error;
    }

    return data;
  }

  /**
   * Log out of Supabase session
   */
  async function signOut(redirectUrl = "login.html") {
    const client = await init();
    if (client) {
      try {
        await client.auth.signOut();
      } catch (e) {
        console.warn("[UrbanPulseAuth] SignOut warning:", e);
      }
    }
    _syncSessionWithAPI(null);

    if (redirectUrl) {
      window.location.href = redirectUrl;
    }
  }

  /**
   * Returns current active session
   */
  async function getSession() {
    const client = await init();
    if (client) {
      try {
        const { data: { session } } = await client.auth.getSession();
        if (session) return session;
      } catch (_) {}
    }
    if (window.UrbanPulseAPI && window.UrbanPulseAPI.getToken()) {
      return {
        access_token: window.UrbanPulseAPI.getToken(),
        user: window.UrbanPulseAPI.getUser() || { email: "admin@urbanpulse.org", role: "admin" }
      };
    }
    return null;
  }

  /**
   * Returns current authenticated user
   */
  async function getUser() {
    const session = await getSession();
    return session ? session.user : null;
  }

  /**
   * Checks if user has admin privileges
   */
  async function isAdmin() {
    const check = await verifyAdminRole();
    return Boolean(check && check.is_admin);
  }

  /**
   * Synchronizes the UI header across public pages with authentication status
   */
  async function updateHeaderUI() {
    const headerInner = document.querySelector(".header-inner") || document.querySelector(".app-header .container");
    if (!headerInner) return;

    let userArea = document.getElementById("up-header-user-area");
    if (!userArea) {
      userArea = document.createElement("div");
      userArea.id = "up-header-user-area";
      userArea.style.display = "flex";
      userArea.style.alignItems = "center";
      userArea.style.gap = "10px";
      userArea.style.marginLeft = "auto";
      userArea.style.marginRight = "16px";

      // Insert before header-status if present, otherwise append
      const statusEl = headerInner.querySelector(".header-status");
      if (statusEl) {
        headerInner.insertBefore(userArea, statusEl);
      } else {
        headerInner.appendChild(userArea);
      }
    }

    const session = await getSession();
    if (!session || !session.user) {
      userArea.innerHTML = `
        <a href="login.html" class="btn btn-sm btn-outline" style="padding: 6px 14px; font-size: 13px; font-weight: 600; text-decoration: none; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); color: var(--text-primary); background: rgba(255,255,255,0.05); display: inline-flex; align-items: center; gap: 6px; transition: var(--transition-fast);">
          <span>🔑</span> Sign In
        </a>
      `;
      return;
    }

    const user = session.user;
    const email = user.email || "";
    const fullName = (user.user_metadata && user.user_metadata.full_name) || email.split("@")[0] || "User";
    
    // Check if admin
    let isAdminRole = false;
    try {
      const check = await verifyAdminRole(session.access_token);
      isAdminRole = Boolean(check && check.is_admin);
    } catch (_) {}

    const roleBadge = isAdminRole
      ? `<span style="background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); font-size: 10px; padding: 2px 7px; border-radius: 999px; font-weight: 700; letter-spacing: 0.5px;">ADMIN</span>`
      : `<span style="background: rgba(56, 189, 248, 0.15); color: var(--accent-cyan); border: 1px solid rgba(56, 189, 248, 0.3); font-size: 10px; padding: 2px 7px; border-radius: 999px; font-weight: 700; letter-spacing: 0.5px;">CITIZEN</span>`;

    const adminLink = isAdminRole
      ? `<a href="admin.html" title="Access Administrator Portal" style="font-size: 12px; color: #fca5a5; font-weight: 600; text-decoration: none; padding: 4px 8px; border-radius: 6px; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.2); display: inline-flex; align-items: center; gap: 4px;">
           🛡️ Admin Portal
         </a>`
      : "";

    userArea.innerHTML = `
      <div style="display: flex; align-items: center; gap: 8px; background: rgba(17, 24, 39, 0.7); border: 1px solid var(--border-subtle); padding: 5px 10px; border-radius: 999px;">
        <span style="font-size: 13px; font-weight: 600; color: var(--text-primary); max-width: 130px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
          👤 ${fullName}
        </span>
        ${roleBadge}
      </div>
      ${adminLink}
      <button id="up-signout-btn" class="btn btn-sm" style="background: rgba(255,255,255,0.06); border: 1px solid var(--border-subtle); color: var(--text-muted); cursor: pointer; padding: 5px 10px; font-size: 12px; font-weight: 600; border-radius: var(--radius-sm); transition: var(--transition-fast);">
        Sign Out
      </button>
    `;

    const signoutBtn = document.getElementById("up-signout-btn");
    if (signoutBtn) {
      signoutBtn.onclick = () => signOut("login.html");
      signoutBtn.onmouseenter = () => { signoutBtn.style.color = "#f43f5e"; signoutBtn.style.borderColor = "rgba(244, 63, 94, 0.3)"; };
      signoutBtn.onmouseleave = () => { signoutBtn.style.color = "var(--text-muted)"; signoutBtn.style.borderColor = "var(--border-subtle)"; };
    }
  }

  // Auto-initialize header UI when DOM is ready
  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", () => {
      // Don't inject into login or auth pages
      if (!window.location.pathname.includes("login.html") &&
          !window.location.pathname.includes("signup.html") &&
          !window.location.pathname.includes("forgot-password.html") &&
          !window.location.pathname.includes("reset-password.html") &&
          !window.location.pathname.includes("admin.html")) {
        init().then(() => updateHeaderUI());
      }
    });

    window.addEventListener("up-auth-state-change", () => {
      if (!window.location.pathname.includes("login.html") &&
          !window.location.pathname.includes("signup.html") &&
          !window.location.pathname.includes("forgot-password.html") &&
          !window.location.pathname.includes("reset-password.html") &&
          !window.location.pathname.includes("admin.html")) {
        updateHeaderUI();
      }
    });
  }

  return {
    init,
    signUp,
    signIn,
    signOut,
    resetPasswordForEmail,
    updateUserPassword,
    getSession,
    getUser,
    isAdmin,
    verifyAdminRole,
    syncUserWithBackend,
    updateHeaderUI
  };
})();

// Attach globally
window.UrbanPulseAuth = UrbanPulseAuth;
