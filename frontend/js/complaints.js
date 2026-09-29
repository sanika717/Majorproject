/**
 * UrbanPulse - Public Complaints Module
 * Submits complaints to the FastAPI backend and tracks ticket status.
 */

const API = window.UrbanPulseAPI;
const BASE = API ? API.baseUrl : "http://127.0.0.1:8000/api/v1";

const CATEGORY_ICONS = {
  "Roads & Potholes": "🛣️",
  "Drainage & Flooding": "🌊",
  "Water Supply & Sewage": "💧",
  "Street Lights": "💡",
  "Garbage & Sanitation": "🗑️",
  "Ongoing Construction Work": "🏗️",
  "Safety & Policing": "🚓",
  "Other": "📌"
};

const STATUS_ICONS = {
  SUBMITTED: { icon: "📬", label: "Submitted", color: "var(--text-secondary)" },
  UNDER_REVIEW: { icon: "🔍", label: "Under Review", color: "var(--accent-amber)" },
  IN_PROGRESS: { icon: "🔧", label: "In Progress", color: "var(--accent-blue)" },
  RESOLVED: { icon: "✅", label: "Resolved", color: "var(--accent-emerald)" },
  REJECTED: { icon: "❌", label: "Rejected", color: "#ef4444" }
};

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: true, timeZone: "Asia/Kolkata" });
}

function renderComplaintCard(c) {
  const s = STATUS_ICONS[c.status] || STATUS_ICONS.SUBMITTED;
  const catIcon = CATEGORY_ICONS[c.category] || "📌";
  return `
    <div class="glass-panel" style="padding: 14px 18px; margin-bottom: 10px; border-left: 3px solid ${s.color};">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-wrap: wrap; gap: 6px;">
        <span style="font-size: 12px; font-weight: 700; color: #38bdf8; letter-spacing: 1px;">${c.ticket_id}</span>
        <span style="font-size: 12px; padding: 2px 8px; border-radius: 4px; font-weight: 700; background: rgba(255,255,255,0.07); color: ${s.color};">${s.icon} ${s.label}</span>
      </div>
      <div style="font-weight: 600; font-size: 14px; margin-bottom: 4px;">${catIcon} ${c.category}</div>
      <div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 6px;">${c.description.substring(0, 120)}${c.description.length > 120 ? "…" : ""}</div>
      ${c.location ? `<div style="font-size: 12px; color: var(--text-muted);">📍 ${c.location}</div>` : ""}
      <div style="font-size: 11px; color: var(--text-muted); margin-top: 6px;">${formatDate(c.created_at)}</div>
      ${c.admin_notes ? `<div style="font-size: 12px; margin-top: 8px; padding: 6px 10px; background: rgba(56,189,248,0.08); border-radius: 6px; border-left: 2px solid #38bdf8; color: var(--text-secondary);"><b style="color:#38bdf8;">Admin Note:</b> ${c.admin_notes}</div>` : ""}
    </div>`;
}

async function loadStats() {
  try {
    const resp = await fetch(`${BASE}/complaints/stats`);
    if (!resp.ok) return;
    const stats = await resp.json();
    const bar = document.getElementById("complaint-stats-bar");
    if (bar) bar.style.display = "";
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    set("stat-total", stats.total || 0);
    set("stat-review", (stats.by_status && stats.by_status.UNDER_REVIEW) || 0);
    set("stat-progress", (stats.by_status && stats.by_status.IN_PROGRESS) || 0);
    set("stat-resolved", (stats.by_status && stats.by_status.RESOLVED) || 0);
  } catch (e) {
    console.warn("[Complaints] Could not load stats:", e);
  }
}

async function loadRecentComplaints() {
  const listEl = document.getElementById("my-complaints-list");
  if (!listEl) return;
  try {
    const resp = await fetch(`${BASE}/complaints/?limit=10`);
    if (!resp.ok) throw new Error(resp.statusText);
    const complaints = await resp.json();
    if (!complaints.length) {
      listEl.innerHTML = `<div class="empty-state"><div class="empty-icon">📭</div>No complaints yet. Be the first to report an issue.</div>`;
    } else {
      listEl.innerHTML = complaints.map(renderComplaintCard).join("");
    }
  } catch (e) {
    listEl.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div>Could not load complaints from backend.</div>`;
    console.warn("[Complaints] Load failed:", e);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  // Load stats and recent complaints
  loadStats();
  loadRecentComplaints();

  // Submit form
  const form = document.getElementById("complaint-form");
  const successEl = document.getElementById("c-success");
  const errorEl = document.getElementById("c-error");
  const errorMsg = document.getElementById("c-error-msg");
  const submitBtn = document.getElementById("c-submit");

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const category = document.getElementById("c-category").value.trim();
      const description = document.getElementById("c-desc").value.trim();
      const location = document.getElementById("c-location").value.trim() || null;
      const name = document.getElementById("c-name").value.trim() || null;
      const contact = document.getElementById("c-contact").value.trim() || null;

      if (!category) { alert("Please select a complaint category."); return; }
      if (!description || description.length < 10) { alert("Please provide a description (at least 10 characters)."); return; }

      submitBtn.disabled = true;
      submitBtn.textContent = "Submitting…";
      successEl.style.display = "none";
      errorEl.style.display = "none";

      try {
        const resp = await fetch(`${BASE}/complaints/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ category, description, location, name, contact })
        });
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          throw new Error(err.detail || `Server error ${resp.status}`);
        }
        const result = await resp.json();
        document.getElementById("c-ticket-id").textContent = result.ticket_id;
        successEl.style.display = "";
        form.reset();
        await loadStats();
        await loadRecentComplaints();
      } catch (err) {
        errorEl.style.display = "";
        if (errorMsg) errorMsg.textContent = err.message || "Submission failed. Please try again.";
        console.error("[Complaints] Submit error:", err);
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Submit Complaint";
      }
    });
  }

  // Track complaint
  const trackBtn = document.getElementById("c-track-btn");
  const trackResult = document.getElementById("c-track-result");
  const trackInput = document.getElementById("c-track-id");

  if (trackBtn && trackInput && trackResult) {
    async function doTrack() {
      const ticketId = trackInput.value.trim().toUpperCase();
      if (!ticketId) { alert("Please enter a Ticket ID."); return; }
      trackResult.style.display = "";
      trackResult.innerHTML = `<div style="color: var(--text-muted); font-size: 13px;">Searching…</div>`;
      try {
        const resp = await fetch(`${BASE}/complaints/${encodeURIComponent(ticketId)}`);
        if (resp.status === 404) {
          trackResult.innerHTML = `<div class="glass-panel" style="padding: 12px 16px; border-left: 3px solid #ef4444; font-size: 13px; color: #ef4444;">❌ No complaint found with ticket ID <b>${ticketId}</b>. Please check and try again.</div>`;
          return;
        }
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const c = await resp.json();
        trackResult.innerHTML = renderComplaintCard(c);
      } catch (err) {
        trackResult.innerHTML = `<div class="glass-panel" style="padding: 12px 16px; border-left: 3px solid #ef4444; font-size: 13px; color: #ef4444;">⚠️ Could not retrieve complaint. ${err.message}</div>`;
      }
    }
    trackBtn.addEventListener("click", doTrack);
    trackInput.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); doTrack(); } });
  }
});
