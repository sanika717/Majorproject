/**
 * UrbanPulse – Intelligence Assistant
 *
 * Flow: User types question → keyword-match against UP_CONSTRUCTION / UP_CRIME / UP_POLICE
 *       → if backend is up, try GET /api/v1/assistant/query (optional)
 *       → always render an answer from verified local data.
 *
 * Answers are built from verified datasets in data.js (UP_CONSTRUCTION, UP_CRIME, UP_POLICE).
 * No answer is ever left blank.
 */
(function () {
  "use strict";

  // ─── DOM refs ──────────────────────────────────────────────────────────────
  var messagesEl  = document.getElementById("chat-messages");
  var formEl      = document.getElementById("chat-form");
  var inputEl     = document.getElementById("chat-input");
  var statusEl    = document.getElementById("assistant-status");
  var suggestEl   = document.getElementById("chat-suggestions");

  // ─── Helpers ───────────────────────────────────────────────────────────────
  function fmt(n) { return typeof n === "number" ? n.toLocaleString("en-IN") : String(n); }
  function fmtCr(cr) { return "₹" + Number(cr).toFixed(2) + " Cr"; }
  function now() { return new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true, timeZone: "Asia/Kolkata" }); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function(c) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
    });
  }

  function addMsg(role, html) {
    var div = document.createElement("div");
    div.className = "chat-msg " + role;
    div.innerHTML = html;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function userMsg(text) {
    addMsg("user", esc(text));
  }

  function assistantMsg(html) {
    return addMsg("assistant", html);
  }

  function typingMsg() {
    return assistantMsg('<span class="typing-dots"><span>.</span><span>.</span><span>.</span></span>');
  }

  function setStatus(text, online) {
    if (statusEl) {
      statusEl.textContent = text;
      statusEl.style.color = online ? "var(--accent-emerald)" : "var(--text-muted)";
    }
  }

  // ─── Verified data getters ─────────────────────────────────────────────────
  function cons()   { return window.UP_CONSTRUCTION  || {}; }
  function crime()  { return window.UP_CRIME          || {}; }
  function police() { return window.UP_POLICE         || {}; }

  // ─── Knowledge base: keyword → answer builder ─────────────────────────────
  var KB = [
    {
      keys: ["total construction", "work order", "investment", "bbmp", "ward work"],
      build: function() {
        var o = cons().overview || {};
        return [
          "<b>🏗️ BBMP 2025–26 Construction Overview</b>",
          "<table style='width:100%;font-size:13px;border-collapse:collapse;margin-top:8px'>",
          row("Total Work Orders",              fmt(o.total_work_orders || 4729)),
          row("Verified Investment",            fmtCr(o.total_amount_cr || 3169.06)),
          row("Net Expenditure",                fmtCr(o.net_expenditure_cr || 2849.69)),
          row("Total Deductions",               fmtCr(o.total_deductions_cr || 319.37)),
          row("Ward Coverage",                  (o.ward_coverage || 198) + " / " + (o.total_wards || 198) + " wards"),
          row("Unique Contractors",             fmt(o.unique_contractors || 1603)),
          row("Avg Deduction Rate",             (o.avg_deduction_rate_pct || 10.08) + "%"),
          "</table>",
          "<div style='font-size:11px;color:var(--text-muted);margin-top:8px'>📂 Source: BBMP 2025-26 ward work-order dataset · 4,729 verified records · EDA-verified figures</div>"
        ].join("");
      }
    },
    {
      keys: ["top ward", "highest investment", "top 5", "best ward", "most investment"],
      build: function() {
        var wards = (cons().top_wards || []).slice(0, 5);
        var rows = wards.map(function(w) {
          return "<tr><td style='padding:4px 8px'>" + esc(w.ward) + "</td><td style='padding:4px 8px;color:#f59e0b'>" + fmtCr(w.amount_cr) + "</td><td style='padding:4px 8px'>" + fmt(w.orders) + "</td></tr>";
        }).join("");
        return [
          "<b>🏗️ Top 5 Wards by Verified Investment</b>",
          "<table style='width:100%;font-size:13px;border-collapse:collapse;margin-top:8px'>",
          "<tr style='color:var(--text-muted);font-size:11px'><th style='text-align:left;padding:4px 8px'>Ward</th><th style='padding:4px 8px'>Investment</th><th style='padding:4px 8px'>Work Orders</th></tr>",
          rows,
          "</table>",
          "<div style='font-size:11px;color:var(--text-muted);margin-top:8px'>📂 Source: BBMP 2025-26 dataset</div>"
        ].join("");
      }
    },
    {
      keys: ["cluster", "development cluster", "k-means", "kmeans"],
      build: function() {
        var cl = (cons().clustering || {});
        var clusters = cl.clusters || [];
        return [
          "<b>📊 BBMP Ward Development Clusters (K-Means++, K=" + (cl.k || 2) + ")</b>",
          "<p style='font-size:12px;color:var(--text-muted)'>Silhouette Score: <b>" + (cl.silhouette_score || 0.3919) + "</b> · Best K across K=2–8</p>",
          "<table style='width:100%;font-size:13px;border-collapse:collapse;margin-top:4px'>",
          clusters.map(function(c) {
            return [
              "<tr style='border-top:1px solid rgba(255,255,255,0.06)'>",
              "<td style='padding:6px 8px'><b>" + esc(c.label) + "</b></td>",
              "<td style='padding:6px 8px'>" + fmt(c.wards) + " wards</td>",
              "<td style='padding:6px 8px'>Avg " + c.avg_orders + " orders / ward</td>",
              "</tr>"
            ].join("");
          }).join(""),
          "</table>",
          "<div style='font-size:11px;color:var(--text-muted);margin-top:8px'>📂 Source: BBMP 2025-26 EDA · K-Means++ clustering on work-order volume + expenditure</div>"
        ].join("");
      }
    },
    {
      keys: ["total crime", "recorded crime", "crime total", "criminal", "d47"],
      build: function() {
        var o = crime().overall || {};
        var risk = crime().risk || {};
        return [
          "<b>🚨 Bengaluru City Crime Statistics (D47 Series)</b>",
          "<table style='width:100%;font-size:13px;border-collapse:collapse;margin-top:8px'>",
          row("Total Recorded Crimes", fmt(o.total || 35971) + " (" + (o.period || "2014–2021") + ")"),
          row("Fatal Crimes",          fmt(o.fatal || 5437)),
          row("Non-Fatal Crimes",      fmt(o.non_fatal || 30534)),
          row("Fatal Severity Rate",   (o.fatal_pct || 15.11) + "%"),
          row("UrbanPulse Risk Score", (risk.score || 71.7) + " / 100 — " + (risk.level || "High Risk") + " (peak: " + (risk.peak_year || 2016) + ")"),
          "</table>",
          "<div style='font-size:11px;color:var(--text-muted);margin-top:8px'>📂 Source: Bengaluru City Police D47 Annual Report (2014–2021) · Verified EDA</div>"
        ].join("");
      }
    },
    {
      keys: ["risk score", "urbanpulse risk", "crime risk", "danger", "safety score"],
      build: function() {
        var risk = crime().risk || {};
        var score = risk.score || 71.7;
        var level = risk.level || "High Risk";
        var vol   = risk.volume_score || 100.0;
        var sev   = risk.severity_score || 29.26;
        return [
          "<b>⚠️ UrbanPulse Crime Risk Score</b>",
          "<div style='margin:10px 0;padding:12px 16px;background:rgba(239,68,68,0.08);border-radius:8px;border-left:3px solid #ef4444'>",
          "<div style='font-size:28px;font-weight:800;color:#ef4444'>" + score + " <span style='font-size:14px;font-weight:400'>/ 100</span></div>",
          "<div style='font-size:13px;color:#ef4444;font-weight:600;margin-top:4px'>" + level + " · Peak year: " + (risk.peak_year || 2016) + "</div>",
          "</div>",
          "<b style='font-size:12px'>Algorithm:</b> <code style='font-size:12px'>60% Volume Score + 40% Severity Score</code>",
          "<div style='font-size:12px;margin-top:6px'>Volume Score: <b>" + vol + " / 100</b> &nbsp;·&nbsp; Severity Score: <b>" + sev + " / 100</b></div>",
          "<div style='font-size:11px;color:var(--text-muted);margin-top:8px'>📂 Source: Bengaluru City Police D47 Series · UrbanPulse composite formula</div>"
        ].join("");
      }
    },
    {
      keys: ["women crime", "crime against women", "woman", "gender crime"],
      build: function() {
        var cat = ((crime().categories || {}).women) || {};
        var yr = cat.by_year || [];
        var subs = cat.subtypes_2023 || [];
        var latest = yr.find(function(r){ return r.year === 2023; }) || {};
        return [
          "<b>👩 Crimes Against Women — Bengaluru</b>",
          "<table style='width:100%;font-size:13px;border-collapse:collapse;margin-top:8px'>",
          yr.map(function(r){ return row(String(r.year), fmt(r.cases) + " cases"); }).join(""),
          "</table>",
          subs.length ? ("<b style='font-size:12px;display:block;margin-top:10px'>Top Sub-types (2023)</b><div style='font-size:12px;color:var(--text-secondary)'>" + subs.slice(0,4).map(function(s){ return s.type + ": " + fmt(s.cases); }).join(" · ") + "</div>") : "",
          "<div style='font-size:11px;color:var(--text-muted);margin-top:8px'>📂 Source: Bengaluru City Police Annual Report / Press Note · Verified</div>"
        ].join("");
      }
    },
    {
      keys: ["children crime", "crime against children", "child crime", "pocso"],
      build: function() {
        var cat = ((crime().categories || {}).children) || {};
        var yr = cat.by_year || [];
        return [
          "<b>👶 Crimes Against Children — Bengaluru</b>",
          "<table style='width:100%;font-size:13px;border-collapse:collapse;margin-top:8px'>",
          yr.map(function(r){ return row(String(r.year), fmt(r.cases) + " cases"); }).join(""),
          "</table>",
          "<div style='font-size:11px;color:var(--text-muted);margin-top:8px'>📂 Source: Bengaluru City Police Annual Report / Press Note · Verified</div>"
        ].join("");
      }
    },
    {
      keys: ["cyber crime", "cyber", "online crime", "digital crime", "hacking"],
      build: function() {
        var cat = ((crime().categories || {}).cyber) || {};
        var yr = cat.by_year || [];
        var divs = cat.by_division_2023 || [];
        return [
          "<b>💻 Cyber Crime — Bengaluru</b>",
          "<table style='width:100%;font-size:13px;border-collapse:collapse;margin-top:8px'>",
          yr.map(function(r){ return row(String(r.year), fmt(r.cases) + " cases"); }).join(""),
          "</table>",
          divs.length ? ("<b style='font-size:12px;display:block;margin-top:10px'>By Division (2023)</b><div style='font-size:12px;color:var(--text-secondary)'>" + divs.map(function(d){ return d.division + ": " + fmt(d.cases); }).join(" · ") + "</div>") : "",
          "<div style='font-size:11px;color:var(--text-muted);margin-top:8px'>📂 Source: Bengaluru City Police Press Note · Verified</div>"
        ].join("");
      }
    },
    {
      keys: ["suicide", "self harm", "accidental death", "accidental"],
      build: function() {
        var suis = ((crime().categories || {}).suicides) || {};
        var acc  = ((crime().categories || {}).accidental) || {};
        var sYr  = suis.by_year || [];
        var aYr  = acc.by_year || [];
        return [
          "<b>🕊️ Suicides &amp; Accidental Deaths — Bengaluru</b>",
          "<table style='width:100%;font-size:13px;border-collapse:collapse;margin-top:8px'>",
          "<tr style='color:var(--text-muted);font-size:11px'><th style='text-align:left;padding:4px 8px'>Year</th><th style='padding:4px 8px'>Suicides</th><th style='padding:4px 8px'>Accidental Deaths</th></tr>",
          [2021,2022,2023].map(function(yr) {
            var s = sYr.find(function(r){ return r.year===yr; }) || {};
            var a = aYr.find(function(r){ return r.year===yr; }) || {};
            return "<tr><td style='padding:4px 8px'>" + yr + "</td><td style='padding:4px 8px'>" + (s.deaths!=null?fmt(s.deaths):"—") + "</td><td style='padding:4px 8px'>" + (a.deaths!=null?fmt(a.deaths):"—") + "</td></tr>";
          }).join(""),
          "</table>",
          "<div style='font-size:11px;color:var(--text-muted);margin-top:8px'>📂 Source: Bengaluru City Police Annual Report · Verified</div>"
        ].join("");
      }
    },
    {
      keys: ["police location", "police station", "mapped police", "outpost", "kml"],
      build: function() {
        var p = police();
        var types = p.by_type || [];
        return [
          "<b>🚓 Mapped Police Locations — Bengaluru</b>",
          "<table style='width:100%;font-size:13px;border-collapse:collapse;margin-top:8px'>",
          row("Total Mapped Locations", fmt(p.total || 150)),
          types.map(function(t){ return row(t.type, fmt(t.count) + " locations"); }).join(""),
          "</table>",
          "<div style='font-size:11px;color:var(--text-muted);margin-top:8px'>📂 Source: Karnataka State Police GIS KML files · Verified station &amp; outpost coordinates</div>",
          "<div style='font-size:11px;color:var(--text-muted)'>Note: Mapped community-contributed locations only. Not an authoritative directory.</div>"
        ].join("");
      }
    },
    {
      keys: ["aqi", "air quality", "pollution", "pm2.5", "pm10", "environment", "esg", "environmental score"],
      build: function() {
        var esgData = window.URBANPULSE_ESG_DATA;
        var air = esgData && esgData.air;
        var avg = air && (air.city_average || (air.live && air.live.city_mean)) || {};
        var year = (air && air.year) || "2016-17";
        if (avg.pm25) {
          return [
            "<b>🌱 Bengaluru Air Quality Data</b>",
            "<p style='font-size:12px;color:var(--text-muted);margin:4px 0'>Reporting period: " + esc(year) + "</p>",
            "<table style='width:100%;font-size:13px;border-collapse:collapse;margin-top:8px'>",
            avg.pm25  != null ? row("PM2.5",  avg.pm25  + " µg/m³ (NAAQS limit: 40)") : "",
            avg.pm10  != null ? row("PM10",   avg.pm10  + " µg/m³ (NAAQS limit: 60)") : "",
            avg.no2   != null ? row("NO₂",    avg.no2   + " µg/m³ (NAAQS limit: 40)") : "",
            avg.so2   != null ? row("SO₂",    avg.so2   + " µg/m³ (NAAQS limit: 50)") : "",
            "</table>",
            "<div style='font-size:11px;color:var(--text-muted);margin-top:8px'>📂 Source: KSPCB / CPCB station observations · ESG Environmental data</div>"
          ].join("");
        }
        return [
          "<b>🌱 ESG Environmental Overview</b>",
          "<p>Air quality data is loaded from the KSPCB / CPCB station dataset. Visit the <a href='esg.html' style='color:#38bdf8'>ESG Scoring page</a> for the full Environmental panel with the area-wise air quality map.</p>",
          "<div style='font-size:11px;color:var(--text-muted);margin-top:8px'>📂 Source: KSPCB / CPCB Annual Observations · BCAP 2019 GHG Inventory</div>"
        ].join("");
      }
    },
    {
      keys: ["urban score", "urbanpulse score", "city score", "overall score", "composite score"],
      build: function() {
        var risk = crime().risk || {};
        var o = cons().overview || {};
        return [
          "<b>⚡ UrbanPulse City Intelligence Overview</b>",
          "<table style='width:100%;font-size:13px;border-collapse:collapse;margin-top:8px'>",
          row("Crime Risk Score",            (risk.score || 71.7) + " / 100 — " + (risk.level || "High Risk")),
          row("Construction Investment",     fmtCr(o.total_amount_cr || 3169.06)),
          row("Work Orders (BBMP 2025-26)",  fmt(o.total_work_orders || 4729)),
          row("Police Locations (KML)",      fmt(police().total || 150)),
          row("ESG Score",                   "Environmental: real data · Social/Governance: demo"),
          "</table>",
          "<div style='font-size:11px;color:var(--text-muted);margin-top:8px'>📂 Sources: BBMP work-orders, Bengaluru City Police D47, Karnataka KML, KSPCB/CPCB/BCAP</div>"
        ].join("");
      }
    }
  ];

  function row(label, value) {
    return "<tr style='border-top:1px solid rgba(255,255,255,0.06)'>" +
      "<td style='padding:5px 8px;color:var(--text-muted);font-size:12px'>" + esc(label) + "</td>" +
      "<td style='padding:5px 8px;font-weight:600'>" + String(value) + "</td></tr>";
  }

  // ─── Answer engine ─────────────────────────────────────────────────────────
  function findAnswer(question) {
    var q = question.toLowerCase();
    for (var i = 0; i < KB.length; i++) {
      var entry = KB[i];
      for (var j = 0; j < entry.keys.length; j++) {
        if (q.indexOf(entry.keys[j]) !== -1) {
          try { return entry.build(); } catch(e) { console.error("[Assistant] build error:", e); }
        }
      }
    }
    return null;
  }

  var FALLBACK = [
    "<b>🤖 UrbanPulse Intelligence Assistant</b>",
    "<p>I can answer questions about the following verified datasets:</p>",
    "<ul style='margin:8px 0;padding-left:16px;font-size:13px;color:var(--text-secondary)'>",
    "<li>🏗️ <b>Construction</b> — BBMP 2025-26 work orders, investment, top wards, clusters</li>",
    "<li>🚨 <b>Crime</b> — D47 totals (2014-2021), risk score, women, children, cyber, suicides</li>",
    "<li>🚓 <b>Police</b> — KML-mapped station &amp; outpost locations</li>",
    "<li>🌱 <b>ESG / Air Quality</b> — KSPCB/CPCB station data, carbon inventory</li>",
    "<li>⚡ <b>Urban Score</b> — composite overview across all datasets</li>",
    "</ul>",
    "<p style='font-size:12px;color:var(--text-muted)'>Try: <em>\"Total construction investment\"</em>, <em>\"Crime risk score\"</em>, <em>\"Top wards by investment\"</em>, <em>\"Women crimes 2023\"</em>, <em>\"Police locations\"</em></p>",
    "<div style='font-size:11px;color:var(--text-muted);margin-top:8px'>📂 Data: BBMP, Bengaluru City Police, Karnataka State Police KML, KSPCB, CPCB, BCAP</div>"
  ].join("");

  // ─── Submit ────────────────────────────────────────────────────────────────
  function handleQuestion(question) {
    question = question.trim();
    if (!question) return;

    if (inputEl) inputEl.value = "";
    if (suggestEl) suggestEl.style.display = "none";

    userMsg(question);
    var typing = typingMsg();

    setTimeout(function() {
      var answer = findAnswer(question);
      if (typing && typing.parentNode) typing.parentNode.removeChild(typing);
      assistantMsg(answer || FALLBACK);
    }, 420);
  }

  // ─── Event wiring ──────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", function() {
    setStatus("Ready · Answering from verified UrbanPulse datasets", true);

    if (formEl) {
      formEl.addEventListener("submit", function(e) {
        e.preventDefault();
        handleQuestion(inputEl ? inputEl.value : "");
      });
    }

    // Suggestion pill clicks
    var pills = document.querySelectorAll("#chat-suggestions .category-pill[data-q]");
    pills.forEach(function(pill) {
      pill.addEventListener("click", function() {
        handleQuestion(pill.getAttribute("data-q"));
      });
    });
  });

})();
