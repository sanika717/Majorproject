/**
 * UrbanPulse - Public Complaints Module
 * Submits complaints to the FastAPI backend and tracks ticket status.
 * Feed shows recent public complaints (anonymised) with demo fallback.
 */

const API  = window.UrbanPulseAPI;
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

// Priority derived from category
const CATEGORY_PRIORITY = {
  "Roads & Potholes":          { priority: "High",   dept: "BBMP Roads Division" },
  "Drainage & Flooding":       { priority: "High",   dept: "BBMP Stormwater Drains" },
  "Water Supply & Sewage":     { priority: "High",   dept: "BWSSB" },
  "Street Lights":             { priority: "Medium", dept: "BESCOM" },
  "Garbage & Sanitation":      { priority: "Medium", dept: "BBMP Solid Waste Mgmt" },
  "Ongoing Construction Work": { priority: "Low",    dept: "BBMP Engineering" },
  "Safety & Policing":         { priority: "High",   dept: "Bengaluru City Police" },
  "Other":                     { priority: "Low",    dept: "BBMP General" }
};

const PRIORITY_COLORS = {
  High:   "#ef4444",
  Medium: "#f59e0b",
  Low:    "var(--accent-cyan)"
};

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: true, timeZone: "Asia/Kolkata"
  });
}

function renderComplaintCard(c) {
  const s   = STATUS_ICONS[c.status] || STATUS_ICONS.SUBMITTED;
  const cat = CATEGORY_PRIORITY[c.category] || { priority: "Medium", dept: "BBMP General" };
  const pri = cat.priority;
  const priColor = PRIORITY_COLORS[pri] || "var(--text-muted)";
  const catIcon  = CATEGORY_ICONS[c.category] || "📌";
  const desc     = String(c.description || "");
  const isDemo   = c._demo ? `<span style="font-size:10px;color:#f59e0b;font-weight:600;margin-left:6px">[DEMO]</span>` : "";
  return `
    <div class="glass-panel" style="padding:14px 18px;margin-bottom:10px;border-left:3px solid ${s.color};">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;flex-wrap:wrap;gap:6px;">
        <span style="font-size:12px;font-weight:700;color:#38bdf8;letter-spacing:1px;">${c.ticket_id}${isDemo}</span>
        <span style="font-size:12px;padding:2px 8px;border-radius:4px;font-weight:700;background:rgba(255,255,255,0.07);color:${s.color};">${s.icon} ${s.label}</span>
      </div>
      <div style="font-weight:600;font-size:14px;margin-bottom:4px;">${catIcon} ${c.category}</div>
      <div style="font-size:13px;color:var(--text-secondary);margin-bottom:6px;">${desc.substring(0, 160)}${desc.length > 160 ? "…" : ""}</div>
      <div style="display:flex;flex-wrap:wrap;gap:10px;font-size:11px;color:var(--text-muted);margin-bottom:4px;">
        ${c.location ? `<span>📍 ${c.location}</span>` : ""}
        <span>⚡ Priority: <b style="color:${priColor}">${pri}</b></span>
        <span>🏢 Dept: <b>${cat.dept}</b></span>
      </div>
      <div style="font-size:11px;color:var(--text-muted);">🕐 ${formatDate(c.created_at)}</div>
      ${c.admin_notes ? `<div style="font-size:12px;margin-top:8px;padding:6px 10px;background:rgba(56,189,248,0.08);border-radius:6px;border-left:2px solid #38bdf8;color:var(--text-secondary);"><b style="color:#38bdf8;">Admin Update:</b> ${c.admin_notes}</div>` : ""}
    </div>`;
}

// ── Demo fallback complaints (shown when no backend / no DB records) ──────────
const DEMO_COMPLAINTS = [
  {
    ticket_id: "UP-2026-DEMO01", _demo: true,
    category: "Roads & Potholes", status: "UNDER_REVIEW",
    description: "Large pothole on Sarjapur Road near Agara Lake causing accidents, especially during rains.",
    location: "Sarjapur Road, HSR Layout", created_at: new Date(Date.now() - 2 * 3600000).toISOString(),
    admin_notes: "Inspected. Repair scheduled for this week."
  },
  {
    ticket_id: "UP-2026-DEMO02", _demo: true,
    category: "Garbage & Sanitation", status: "SUBMITTED",
    description: "Garbage not collected for 4 days in our layout. Causing smell and flies near residential area.",
    location: "Marathahalli, Outer Ring Road", created_at: new Date(Date.now() - 5 * 3600000).toISOString(),
    admin_notes: null
  },
  {
    ticket_id: "UP-2026-DEMO03", _demo: true,
    category: "Street Lights", status: "IN_PROGRESS",
    description: "Three street lights non-functional on 80 Feet Road near Koramangala. Dark stretch causing safety concerns.",
    location: "80 Feet Road, Koramangala", created_at: new Date(Date.now() - 18 * 3600000).toISOString(),
    admin_notes: "BESCOM team assigned. Work in progress."
  },
  {
    ticket_id: "UP-2026-DEMO04", _demo: true,
    category: "Water Supply & Sewage", status: "RESOLVED",
    description: "Sewage overflow near bus stop. Resolved after BWSSB team cleared blockage.",
    location: "Jayanagar 4th Block", created_at: new Date(Date.now() - 72 * 3600000).toISOString(),
    admin_notes: "Resolved on 05 Oct 2026. Pipe blockage cleared."
  }
];

async function loadPublicFeed() {
  const listEl = document.getElementById("my-complaints-list");
  if (!listEl) return;

  // Try the public feed endpoint first
  try {
    const resp = await fetch(`${BASE}/complaints/public?limit=10`, { cache: "no-store" });
    if (resp.ok) {
      const complaints = await resp.json();
      if (Array.isArray(complaints) && complaints.length) {
        listEl.innerHTML = complaints.map(renderComplaintCard).join("");
        return;
      }
    }
  } catch (_) { /* backend not running */ }

  // Backend unavailable or no records → show demo complaints
  const demoNote = `<div style="font-size:11px;color:#f59e0b;padding:6px 12px;border-radius:6px;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);margin-bottom:10px;">
    ⚠️ <b>Demo data:</b> Backend is not connected. Showing sample complaints for demonstration.
  </div>`;
  listEl.innerHTML = demoNote + DEMO_COMPLAINTS.map(renderComplaintCard).join("");
}

async function loadStats() {
  try {
    const resp = await fetch(`${BASE}/complaints/stats`);
    if (!resp.ok) return;
    const stats = await resp.json();
    const bar = document.getElementById("complaint-stats-bar");
    if (bar) bar.style.display = "";
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    set("stat-total",    stats.total || 0);
    set("stat-review",   (stats.by_status && stats.by_status.UNDER_REVIEW) || 0);
    set("stat-progress", (stats.by_status && stats.by_status.IN_PROGRESS)  || 0);
    set("stat-resolved", (stats.by_status && stats.by_status.RESOLVED)     || 0);
  } catch (e) {
    console.warn("[Complaints] Could not load stats:", e);
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

      if (!category)                           { alert("Please select a complaint category."); return; }
      if (!description || description.length < 10) { alert("Please provide a description (at least 10 characters)."); return; }

      submitBtn.disabled = true;
      submitBtn.textContent = "Submitting…";
      successEl.style.display = "none";
      errorEl.style.display   = "none";

      try {
        const headers = API
          ? API.getHeaders({ "Content-Type": "application/json" })
          : { "Content-Type": "application/json" };

        const resp = await fetch(`${BASE}/complaints/`, {
          method: "POST",
          headers,
          body: JSON.stringify({ category, description, location, name, contact, hide_identity: hideIdent })
        });

        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          throw new Error(err.detail || `Server error ${resp.status}`);
        }

        const result = await resp.json();
        document.getElementById("c-ticket-id").textContent   = result.ticket_id;
        const secretEl = document.getElementById("c-secret-code");
        if (secretEl) secretEl.textContent = result.tracking_secret || "Saved securely";
        successEl.style.display = "";
        form.reset();

        // Immediately refresh feed and stats
        await loadStats();
        await loadPublicFeed();

      } catch (err) {
        // If backend not running, show a demo success for UX demo purposes
        if (err.message && (err.message.includes("fetch") || err.message.includes("Failed") || err.message.includes("NetworkError"))) {
          const demoTicket = "UP-" + new Date().getFullYear() + "-" + Math.random().toString(36).substring(2,8).toUpperCase();
          document.getElementById("c-ticket-id").textContent   = demoTicket;
          const secretEl = document.getElementById("c-secret-code");
          if (secretEl) secretEl.textContent = "[Backend not connected — demo mode]";
          successEl.style.display = "";
          form.reset();
          // Prepend the submitted complaint to the demo feed
          const listEl = document.getElementById("my-complaints-list");
          if (listEl) {
            const newCard = renderComplaintCard({
              ticket_id: demoTicket, _demo: true,
              category, description, location: location || "",
              status: "SUBMITTED",
              created_at: new Date().toISOString(),
              admin_notes: null
            });
            listEl.innerHTML = newCard + listEl.innerHTML;
          }
        } else {
          errorEl.style.display = "";
          if (errorMsg) errorMsg.textContent = err.message || "Submission failed. Please try again.";
        }
        console.warn("[Complaints] Submit:", err.message);
      } finally {
        submitBtn.disabled    = false;
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
      if (!ticketId) { alert("Please enter a Ticket ID."); return; }
      if (!secret)   { alert("Please enter the Secret Code received when submitting the complaint."); return; }

      trackResult.style.display = "";
      trackResult.innerHTML = `<div style="color:var(--text-muted);font-size:13px;">Searching…</div>`;
      try {
        const headers = API
          ? API.getHeaders({ "Content-Type": "application/json" })
          : { "Content-Type": "application/json" };

        const resp = await fetch(`${BASE}/complaints/track`, {
          method: "POST", headers,
          body: JSON.stringify({ ticket_id: ticketId, secret })
        });
        if (resp.status === 404) {
          trackResult.innerHTML = `<div class="glass-panel" style="padding:12px 16px;border-left:3px solid #ef4444;font-size:13px;color:#ef4444;">❌ No complaint found matching Ticket ID <b>${ticketId}</b> and the provided secret code.</div>`;
          return;
        }
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const c = await resp.json();
        trackResult.innerHTML = renderComplaintCard(c);
      } catch (err) {
        trackResult.innerHTML = `<div class="glass-panel" style="padding:12px 16px;border-left:3px solid #ef4444;font-size:13px;color:#ef4444;">⚠️ Could not retrieve complaint. ${err.message}</div>`;
      }
    }
    trackBtn.addEventListener("click", doTrack);
    trackInput.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); doTrack(); } });
    if (trackSecretInput) {
      trackSecretInput.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); doTrack(); } });
    }
  }
});

