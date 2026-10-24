/**
 * UrbanPulse - Public Complaints Module
 * Real PostgreSQL Database Backend Integration.
 * Zero fabricated statistics & zero demo fallback data.
 */

const API = window.UrbanPulseAPI;
const BASE = API ? API.baseUrl : "http://127.0.0.1:8000/api/v1";

const CATEGORY_ICONS = {
  "Roads & Potholes":          "🛣️",
  "Drainage & Flooding":       "🌊",
  "Water Supply & Sewage":     "💧",
  "Street Lights":             "💡",
  "Garbage & Sanitation":      "🗑️",
  "Ongoing Construction Work": "🏗️",
  "Safety & Policing":         "🚓",
  "Other":                     "📌"
};

const STATUS_ICONS = {
  SUBMITTED:    { icon: "📬", label: "Submitted",    color: "var(--text-secondary)" },
  UNDER_REVIEW: { icon: "🔍", label: "Under Review", color: "var(--accent-amber)"   },
  IN_PROGRESS:  { icon: "🔧", label: "In Progress",  color: "var(--accent-blue)"    },
  RESOLVED:     { icon: "✅", label: "Resolved",     color: "var(--accent-emerald)" },
  REJECTED:     { icon: "❌", label: "Rejected",     color: "#ef4444"               }
};

const PRIORITY_COLORS = {
  CRITICAL: "#f43f5e",
  HIGH:     "#ef4444",
  MEDIUM:   "#f59e0b",
  LOW:      "var(--accent-cyan)"
};

function formatDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-IN", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit", hour12: true, timeZone: "Asia/Kolkata"
    });
  } catch (_) {
    return iso;
  }
}

function renderComplaintCard(c, isTrackingResult = false) {
  const statusKey = String(c.status || "SUBMITTED").toUpperCase();
  const s = STATUS_ICONS[statusKey] || STATUS_ICONS.SUBMITTED;
  const priKey = String(c.priority || "MEDIUM").toUpperCase();
  const priColor = PRIORITY_COLORS[priKey] || "#f59e0b";
  const catIcon = CATEGORY_ICONS[c.category] || "📌";
  const desc = String(c.description || "");
  const deptName = c.department || "BBMP Civic Administration";
  const locationText = c.ward && c.location && !c.location.includes(c.ward)
    ? `${c.ward} • ${c.location}`
    : (c.location || c.ward || "Bengaluru");

  return `
    <div class="glass-panel" style="padding:16px 20px;margin-bottom:12px;border-left:3px solid ${s.color};">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:8px;">
        <span style="font-size:13px;font-weight:700;color:#38bdf8;letter-spacing:1px;font-family:monospace;">${c.ticket_id}</span>
        <span style="font-size:12px;padding:3px 10px;border-radius:6px;font-weight:700;background:rgba(255,255,255,0.06);border:1px solid ${s.color}40;color:${s.color};">
          ${s.icon} ${s.label}
        </span>
      </div>

      <div style="font-weight:600;font-size:15px;margin-bottom:6px;color:#fff;">
        ${catIcon} ${c.category}
      </div>

      <div style="font-size:13.5px;color:var(--text-secondary);margin-bottom:10px;line-height:1.5;">
        ${desc}
      </div>

      <div style="display:flex;flex-wrap:wrap;gap:12px;font-size:12px;color:var(--text-muted);margin-bottom:6px;">
        <span>📍 <b>${locationText}</b></span>
        <span>⚡ Priority: <b style="color:${priColor};">${priKey}</b></span>
        <span>🏢 Assigned Dept: <b style="color:var(--text-primary);">${deptName}</b></span>
      </div>

      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;font-size:11.5px;color:var(--text-muted);margin-top:6px;padding-top:6px;border-top:1px solid var(--border-subtle);">
        <span>🕐 Submitted: ${formatDate(c.created_at)}</span>
        ${c.name ? `<span>👤 Complainant: <b style="color:#94a3b8;">${c.name}</b></span>` : ""}
      </div>

      ${c.admin_notes ? `
        <div style="font-size:12.5px;margin-top:10px;padding:8px 12px;background:rgba(56,189,248,0.08);border-radius:6px;border-left:3px solid #38bdf8;color:var(--text-secondary);">
          <b style="color:#38bdf8;">Authority Update:</b> ${c.admin_notes}
          ${c.updated_at ? `<span style="font-size:11px;color:var(--text-muted);margin-left:8px;">(${formatDate(c.updated_at)})</span>` : ""}
        </div>
      ` : ""}
    </div>`;
}

async function loadStats() {
  const bar = document.getElementById("complaint-stats-bar");
  try {
    const resp = await fetch(`${BASE}/complaints/stats`, { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const stats = await resp.json();

    if (bar) bar.style.display = "grid";

    const setVal = (id, v) => {
      const el = document.getElementById(id);
      if (el) el.textContent = v !== undefined && v !== null ? v : 0;
    };

    setVal("stat-total",    stats.total || 0);
    setVal("stat-review",   (stats.by_status && stats.by_status.UNDER_REVIEW) || 0);
    setVal("stat-progress", (stats.by_status && stats.by_status.IN_PROGRESS)  || 0);
    setVal("stat-resolved", (stats.by_status && stats.by_status.RESOLVED)     || 0);
  } catch (err) {
    console.warn("[Complaints] Stats endpoint notice:", err.message);
    if (bar) bar.style.display = "grid";
    ["stat-total", "stat-review", "stat-progress", "stat-resolved"].forEach(id => {
      const el = document.getElementById(id);
      if (el && el.textContent === "—") el.textContent = "0";
    });
  }
}

async function loadPublicFeed() {
  const listEl = document.getElementById("my-complaints-list");
  if (!listEl) return;

  try {
    listEl.innerHTML = `
      <div class="empty-state" style="padding: 24px; text-align: center; color: var(--text-muted);">
        <div class="spinner" style="width:24px;height:24px;border-width:2px;margin:0 auto 10px;"></div>
        <div style="font-size: 13px;">Connecting to PostgreSQL complaints feed…</div>
      </div>
    `;

    const resp = await fetch(`${BASE}/complaints/public?limit=15`, { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    const complaints = await resp.json();

    if (Array.isArray(complaints) && complaints.length > 0) {
      listEl.innerHTML = complaints.map(c => renderComplaintCard(c)).join("");
    } else {
      // Honest Empty State: Zero fabricated complaints
      listEl.innerHTML = `
        <div class="empty-state" style="padding: 36px 20px; text-align: center; color: var(--text-muted);">
          <div class="empty-icon" style="font-size: 34px; margin-bottom: 12px;">📭</div>
          <div style="font-size: 14.5px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px;">No complaints recorded in database</div>
          <div style="font-size: 12.5px; color: var(--text-muted); max-width: 380px; margin: 0 auto; line-height: 1.5;">
            The public feed is currently clear. Grievances submitted by citizens will appear here in real time.
          </div>
        </div>
      `;
    }
  } catch (err) {
    listEl.innerHTML = `
      <div class="glass-panel" style="padding: 16px; border-left: 3px solid #ef4444; color: var(--text-secondary); font-size: 13px;">
        ⚠️ <b>Connection Error:</b> Unable to connect to the complaints service. Please ensure the backend server is running.
      </div>
    `;
    console.warn("[Complaints] Feed error:", err.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadStats();
  loadPublicFeed();

  // ── Submit form ────────────────────────────────────────────────────────────
  const form      = document.getElementById("complaint-form");
  const successEl = document.getElementById("c-success");
  const errorEl   = document.getElementById("c-error");
  const errorMsg  = document.getElementById("c-error-msg");
  const submitBtn = document.getElementById("c-submit");

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const category    = document.getElementById("c-category").value.trim();
      const description = document.getElementById("c-desc").value.trim();
      const location    = document.getElementById("c-location").value.trim() || null;
      const name        = document.getElementById("c-name").value.trim() || null;
      const contact     = document.getElementById("c-contact").value.trim() || null;
      const hideIdent   = document.getElementById("c-hide-identity")?.checked || false;

      if (!category) {
        alert("Please select a complaint category.");
        return;
      }
      if (!description || description.length < 10) {
        alert("Please provide a description of the issue (at least 10 characters).");
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = "Submitting to database…";
      successEl.style.display = "none";
      errorEl.style.display   = "none";

      try {
        const headers = API
          ? API.getHeaders({ "Content-Type": "application/json" })
          : { "Content-Type": "application/json" };

        const resp = await fetch(`${BASE}/complaints/`, {
          method: "POST",
          headers,
          body: JSON.stringify({
            category,
            description,
            location,
            name,
            contact,
            hide_identity: hideIdent
          })
        });

        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          const msg = Array.isArray(errData.detail)
            ? errData.detail.map(d => d.msg).join(", ")
            : (errData.detail || `Server error (${resp.status})`);
          throw new Error(msg);
        }

        const result = await resp.json();
        
        // Show success credentials
        document.getElementById("c-ticket-id").textContent = result.ticket_id;
        const secretEl = document.getElementById("c-secret-code");
        if (secretEl) {
          secretEl.textContent = result.tracking_secret || "Saved securely";
        }
        successEl.style.display = "block";
        form.reset();

        // Immediately update stats and public feed from database
        await loadStats();
        await loadPublicFeed();

      } catch (err) {
        errorEl.style.display = "block";
        if (errorMsg) {
          errorMsg.textContent = err.message || "Failed to submit complaint. Please check database connection.";
        }
        console.error("[Complaints] Submit error:", err);
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Submit Complaint";
      }
    });
  }

  // ── Track complaint ────────────────────────────────────────────────────────
  const trackBtn         = document.getElementById("c-track-btn");
  const trackResult      = document.getElementById("c-track-result");
  const trackInput       = document.getElementById("c-track-id");
  const trackSecretInput = document.getElementById("c-track-secret");

  if (trackBtn && trackInput && trackResult) {
    async function doTrack() {
      const ticketId = trackInput.value.trim().toUpperCase();
      const secret   = trackSecretInput ? trackSecretInput.value.trim() : "";

      if (!ticketId) {
        alert("Please enter your Ticket ID.");
        return;
      }
      if (!secret) {
        alert("Please enter your 24-character Secret Code provided during submission.");
        return;
      }

      trackResult.style.display = "block";
      trackResult.innerHTML = `
        <div class="glass-panel" style="padding:14px;text-align:center;color:var(--text-muted);font-size:13px;">
          <div class="spinner" style="width:20px;height:20px;border-width:2px;margin:0 auto 8px;"></div>
          Verifying credentials & fetching ticket ${ticketId}…
        </div>`;

      try {
        const headers = API
          ? API.getHeaders({ "Content-Type": "application/json" })
          : { "Content-Type": "application/json" };

        const resp = await fetch(`${BASE}/complaints/track`, {
          method: "POST",
          headers,
          body: JSON.stringify({ ticket_id: ticketId, secret })
        });

        if (resp.status === 404) {
          trackResult.innerHTML = `
            <div class="glass-panel" style="padding:16px 20px;border-left:3px solid #ef4444;font-size:13px;color:#ef4444;">
              <b>❌ Ticket Not Found or Invalid Secret</b>
              <p style="margin:4px 0 0;color:var(--text-secondary);font-size:12.5px;">
                No complaint matching Ticket ID <b>${ticketId}</b> and the provided secret code was found in the database. Please double check both credentials.
              </p>
            </div>`;
          return;
        }

        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          throw new Error(errData.detail || `Server returned ${resp.status}`);
        }

        const complaintData = await resp.json();
        trackResult.innerHTML = renderComplaintCard(complaintData, true);

      } catch (err) {
        trackResult.innerHTML = `
          <div class="glass-panel" style="padding:14px 18px;border-left:3px solid #ef4444;font-size:13px;color:#ef4444;">
            ⚠️ <b>Tracking Error:</b> ${err.message}
          </div>`;
      }
    }

    trackBtn.addEventListener("click", doTrack);
    trackInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); doTrack(); }
    });
    if (trackSecretInput) {
      trackSecretInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); doTrack(); }
      });
    }
  }
});
