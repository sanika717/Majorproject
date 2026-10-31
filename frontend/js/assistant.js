/**
 * UrbanPulse – Intelligence Assistant (Backend-Connected)
 *
 * Flow: User types question → POST /api/v1/intelligence/ask
 *       → Receives structured UrbanScore + Qwen3:4b answer
 *       → Renders UrbanScore card, decision analysis, sources
 *
 * All data comes exclusively from verified PostgreSQL datasets via the backend.
 * No statistics, citations, or scores are hardcoded or fabricated here.
 */
(function () {
  "use strict";

  var API_BASE = "/api/v1/intelligence";

  // ─── DOM refs ──────────────────────────────────────────────────────────────
  var messagesEl = document.getElementById("chat-messages");
  var formEl     = document.getElementById("chat-form");
  var inputEl    = document.getElementById("chat-input");
  var statusEl   = document.getElementById("assistant-status");
  var suggestEl  = document.getElementById("chat-suggestions");

  // ─── Helpers ───────────────────────────────────────────────────────────────
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

  function userMsg(text)       { addMsg("user",      esc(text)); }
  function assistantMsg(html)  { return addMsg("assistant", html); }

  function typingMsg() {
    return assistantMsg('<span class="typing-dots"><span>.</span><span>.</span><span>.</span></span>');
  }

  function setStatus(text, online) {
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.style.color = online ? "var(--accent-emerald)" : "var(--text-muted)";
  }

  // ─── Score Bar ─────────────────────────────────────────────────────────────
  function scoreBar(label, score, weight, color) {
    if (score == null) {
      return '<div style="margin:4px 0;font-size:12px;color:var(--text-muted)">◦ ' + esc(label) + ' — Data unavailable</div>';
    }
    var pct = Math.round(score);
    return (
      '<div style="margin:6px 0">' +
      '<div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:2px">' +
      '<span>' + esc(label) + ' <span style="color:var(--text-muted);font-size:10px">(wt ' + Math.round(weight * 100) + '%)</span></span>' +
      '<span style="font-weight:700;color:' + color + '">' + score + '/100</span>' +
      '</div>' +
      '<div style="background:rgba(255,255,255,0.08);border-radius:4px;height:6px;overflow:hidden">' +
      '<div style="width:' + pct + '%;height:100%;background:' + color + ';border-radius:4px;transition:width 0.6s ease"></div>' +
      '</div></div>'
    );
  }

  // ─── Grade Badge ───────────────────────────────────────────────────────────
  function gradeColor(score) {
    if (score >= 80) return "#10b981";  // emerald
    if (score >= 65) return "#3b82f6";  // blue
    if (score >= 50) return "#f59e0b";  // amber
    return "#ef4444";                    // red
  }

  // ─── UrbanScore Card ───────────────────────────────────────────────────────
  function renderUrbanScoreCard(us) {
    if (!us) return "";
    var score  = us.score != null ? us.score : us.urban_score;
    var grade  = us.grade || us.tier || "N/A";
    var cov    = us.data_coverage_pct != null ? us.data_coverage_pct : "N/A";
    var conf   = us.confidence || "N/A";
    var comps  = us.components || {};
    var lims   = us.limitations || us.missing_indicators || [];
    var color  = gradeColor(score);

    var shortGrade = grade.replace(/^Tier \d+:\s*/, "");

    var bars = [
      scoreBar("🛡 Safety",               comps.safety               ? comps.safety.score              : null, 0.25, "#ef4444"),
      scoreBar("🏗 Infrastructure",       comps.infrastructure        ? comps.infrastructure.score       : null, 0.25, "#3b82f6"),
      scoreBar("🌱 Environment",          comps.environment           ? comps.environment.score          : null, 0.20, "#10b981"),
      scoreBar("🏫 Social Infrastructure",comps.social_infrastructure ? comps.social_infrastructure.score: null, 0.15, "#a78bfa"),
      scoreBar("📋 Governance",           comps.governance            ? comps.governance.score           : null, 0.15, "#f59e0b"),
    ].join("");

    var limHtml = "";
    if (lims.length) {
      limHtml = '<div style="margin-top:10px;padding:8px;background:rgba(239,68,68,0.08);border-radius:6px;font-size:11px;color:var(--text-muted)">' +
        "⚠ Limitations: " + lims.slice(0, 2).map(esc).join(" · ") + "</div>";
    }

    return (
      '<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:16px;margin:10px 0">' +
      '<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px">' +
      '<div style="width:60px;height:60px;border-radius:50%;background:conic-gradient(' + color + ' ' + score + '%, rgba(255,255,255,0.1) 0%);display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:800;color:' + color + '">' + score + '</div>' +
      '<div>' +
      '<div style="font-size:16px;font-weight:700">' + esc(us.locality || "Locality") + '</div>' +
      '<div style="font-size:12px;color:' + color + ';font-weight:600">⚡ UrbanScore: ' + score + '/100</div>' +
      '<div style="font-size:11px;color:var(--text-muted)">' + esc(shortGrade) + ' · ' + conf + ' confidence · ' + cov + '% data coverage</div>' +
      '</div></div>' +
      bars +
      limHtml +
      '<div style="font-size:10px;color:var(--text-muted);margin-top:8px">Methodology: Safety 25% · Infrastructure 25% · Environment 20% · Social 15% · Governance 15%</div>' +
      '</div>'
    );
  }

  // ─── Decision Analysis Panel ───────────────────────────────────────────────
  function renderAnalysis(analysis) {
    if (!analysis) return "";
    var html = '<div style="margin-top:10px">';

    var consider = analysis.reasons_to_consider || [];
    if (consider.length) {
      html += '<div style="background:rgba(16,185,129,0.08);border-left:3px solid #10b981;padding:10px 12px;border-radius:0 6px 6px 0;margin-bottom:8px">' +
        '<div style="font-size:12px;font-weight:700;color:#10b981;margin-bottom:4px">✅ Reasons to Consider</div>' +
        consider.map(function(r) { return '<div style="font-size:12px;color:var(--text-secondary);margin:2px 0">• ' + esc(r) + '</div>'; }).join("") +
        '</div>';
    }

    var caution = analysis.reasons_for_caution || [];
    if (caution.length) {
      html += '<div style="background:rgba(245,158,11,0.08);border-left:3px solid #f59e0b;padding:10px 12px;border-radius:0 6px 6px 0;margin-bottom:8px">' +
        '<div style="font-size:12px;font-weight:700;color:#f59e0b;margin-bottom:4px">⚠ Reasons for Caution</div>' +
        caution.map(function(r) { return '<div style="font-size:12px;color:var(--text-secondary);margin:2px 0">• ' + esc(r) + '</div>'; }).join("") +
        '</div>';
    }

    var risks = analysis.risks || {};
    var riskKeys = Object.keys(risks);
    if (riskKeys.length) {
      html += '<div style="background:rgba(239,68,68,0.07);border-left:3px solid #ef4444;padding:10px 12px;border-radius:0 6px 6px 0;margin-bottom:8px">' +
        '<div style="font-size:12px;font-weight:700;color:#ef4444;margin-bottom:4px">🚨 Risk Indicators (by Category)</div>' +
        riskKeys.map(function(k) {
          var val = Array.isArray(risks[k]) ? risks[k].join("; ") : risks[k];
          return '<div style="font-size:12px;color:var(--text-secondary);margin:2px 0"><b>' + esc(k) + '</b>: ' + esc(val) + '</div>';
        }).join("") +
        '</div>';
    }

    var recs = analysis.actionable_recommendations || analysis.recommendations || [];
    if (recs.length) {
      html += '<div style="background:rgba(59,130,246,0.07);border-left:3px solid #3b82f6;padding:10px 12px;border-radius:0 6px 6px 0;margin-bottom:8px">' +
        '<div style="font-size:12px;font-weight:700;color:#3b82f6;margin-bottom:4px">💡 Actionable Recommendations</div>' +
        recs.map(function(r) { return '<div style="font-size:12px;color:var(--text-secondary);margin:2px 0">→ ' + esc(r) + '</div>'; }).join("") +
        '</div>';
    }

    var dlims = analysis.data_limitations || analysis.missing_data_warnings || [];
    if (dlims.length) {
      html += '<div style="font-size:11px;color:var(--text-muted);background:rgba(255,255,255,0.04);padding:8px;border-radius:6px;">' +
        '📌 Data Limitations: ' + dlims.map(esc).join(" · ") +
        '</div>';
    }

    html += '</div>';
    return html;
  }

  // ─── Answer Mode Badge ───────────────────────────────────────────────────────
  var MODE_STYLES = {
    "Verified UrbanPulse Data":          { icon: "🗄", color: "#10b981", bg: "rgba(16,185,129,0.12)" },
    "UrbanPulse Data + AI Analysis":    { icon: "🤖", color: "#3b82f6", bg: "rgba(59,130,246,0.12)" },
    "General AI Answer":                 { icon: "💬", color: "#a78bfa", bg: "rgba(167,139,250,0.12)" },
    "Verified UrbanPulse Data (AI Unavailable)": { icon: "🗄", color: "#f59e0b", bg: "rgba(245,158,11,0.10)" }
  };

  function renderModeBadge(mode, model, cached) {
    var style = MODE_STYLES[mode] || { icon: "🤖", color: "#6b7280", bg: "rgba(107,114,128,0.1)" };
    var modelStr = (model && model !== "n/a (data-only)" && model !== "none")
      ? " · " + esc(model) : "";
    var cacheStr = cached ? " · ♻ Cached" : "";
    return (
      '<div style="display:inline-flex;align-items:center;gap:6px;padding:4px 10px;' +
      'background:' + style.bg + ';border:1px solid ' + style.color + '33;' +
      'border-radius:20px;font-size:11px;font-weight:600;color:' + style.color + ';margin-bottom:10px">' +
      style.icon + ' ' + esc(mode) + modelStr + cacheStr +
      '</div>'
    );
  }

  // ─── Sources Footer ─────────────────────────────────────────────────────────
  function renderSources(sources, meta) {
    if (!sources || !sources.length) return "";
    return (
      '<div style="margin-top:12px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.07)">' +
      '<div style="font-size:10px;color:var(--text-muted);margin-bottom:4px">📂 Data Sources & Attribution:</div>' +
      sources.slice(0, 6).map(function(s) {
        return '<div style="font-size:10px;color:var(--text-muted)">• ' + esc(typeof s === "string" ? s : s.name || JSON.stringify(s)) + '</div>';
      }).join("") +
      (meta && meta.latency_ms ? '<div style="font-size:10px;color:var(--text-muted);margin-top:4px">⏱ ' + meta.latency_ms + 'ms</div>' : "") +
      '</div>'
    );
  }

  // ─── Format Answer Markdown (basic) ────────────────────────────────────────
  function renderAnswer(text) {
    if (!text) return "";
    var escaped = esc(text);
    // Bold **text**
    escaped = escaped.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    // #### headings
    escaped = escaped.replace(/^####\s(.+)$/gm, '<h5 style="color:#93c5fd;font-size:13px;margin:10px 0 4px">$1</h5>');
    // ### headings
    escaped = escaped.replace(/^###\s(.+)$/gm, '<h4 style="color:#93c5fd;font-size:14px;margin:12px 0 6px">$1</h4>');
    // ## headings
    escaped = escaped.replace(/^##\s(.+)$/gm, '<h3 style="color:#60a5fa;font-size:15px;margin:14px 0 6px">$1</h3>');
    // - list items
    escaped = escaped.replace(/^[•\-]\s(.+)$/gm, '<div style="margin:2px 0;padding-left:12px">• $1</div>');
    // → items
    escaped = escaped.replace(/^→\s(.+)$/gm, '<div style="margin:2px 0;padding-left:12px;color:#60a5fa">→ $1</div>');
    // Newlines
    escaped = escaped.replace(/\n\n/g, '<br><br>');
    escaped = escaped.replace(/\n/g, '<br>');
    return '<div style="font-size:13px;line-height:1.7;color:var(--text-secondary)">' + escaped + '</div>';
  }

  // ─── Render Full Response ──────────────────────────────────────────────────
  function renderResponse(data) {
    var html = "";

    // Answer mode badge (always first)
    var mode = data.answer_mode || "UrbanPulse Data + AI Analysis";
    html += renderModeBadge(mode, data.model, data.cached);

    // UrbanScore card (when a locality is involved)
    if (data.urban_score) {
      html += renderUrbanScoreCard(data.urban_score);
    }

    // Main answer
    if (data.answer) {
      html += renderAnswer(data.answer);
    }

    // Decision analysis (only for hybrid/data modes)
    if (data.analysis && mode !== "General AI Answer") {
      html += renderAnalysis(data.analysis);
    }

    // Sources
    html += renderSources(data.sources, {
      latency_ms: data.latency_ms,
      model: data.model,
      cached: data.cached
    });

    return html || "No answer returned from the backend.";
  }

  // ─── API Call (Streaming with Fallback) ────────────────────────────────────
  function askBackend(question, typing) {
    var body = JSON.stringify({ question: question, enable_cache: true });

    function fallbackPost() {
      fetch(API_BASE + "/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (typing && typing.parentNode) typing.parentNode.removeChild(typing);

        if (data.detail) {
          assistantMsg(
            '<div style="color:#f87171;font-size:13px">⚠ Backend error: ' + esc(data.detail) + '</div>'
          );
          setStatus("Error from backend", false);
          return;
        }

        var mode = data.answer_mode || "";
        var modeStr = mode ? " [" + mode + "]" : "";
        assistantMsg(renderResponse(data));
        setStatus("Ready" + modeStr, true);
      })
      .catch(function(err) {
        if (typing && typing.parentNode) typing.parentNode.removeChild(typing);
        assistantMsg(
          '<div style="color:#f87171;font-size:13px">⚠ Could not reach the UrbanPulse backend. Please ensure the server is running on port 8000.<br><small>Error: ' + esc(String(err)) + '</small></div>'
        );
        setStatus("Backend unavailable", false);
      });
    }

    if (!window.fetch || !window.ReadableStream) {
      fallbackPost();
      return;
    }

    var streamedText = "";
    var streamContainer = null;
    var receivedDone = false;

    fetch(API_BASE + "/ask/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body
    })
    .then(function(response) {
      if (!response.ok || !response.body) {
        throw new Error("Streaming error: HTTP " + response.status);
      }
      var reader = response.body.getReader();
      var decoder = new TextDecoder("utf-8");
      var buffer = "";

      function readChunk() {
        return reader.read().then(function(result) {
          if (result.done) {
            if (!receivedDone && streamedText) {
              // Completed stream without explicit done payload
              if (typing && typing.parentNode) typing.parentNode.removeChild(typing);
              assistantMsg(renderAnswer(streamedText));
            }
            return;
          }
          buffer += decoder.decode(result.value, { stream: true });
          var lines = buffer.split("\n");
          buffer = lines.pop();

          for (var i = 0; i < lines.length; i++) {
            var line = lines[i].trim();
            if (!line) continue;
            try {
              var parsed = JSON.parse(line);
              if (parsed.delta) {
                if (typing) {
                  if (!streamContainer) {
                    typing.innerHTML = '<div class="streaming-text" style="font-size:13px;line-height:1.7;color:var(--text-secondary)"></div>';
                    streamContainer = typing.querySelector(".streaming-text");
                  }
                  streamedText += parsed.delta;
                  if (streamContainer) {
                    streamContainer.innerHTML = renderAnswer(streamedText);
                    messagesEl.scrollTop = messagesEl.scrollHeight;
                  }
                }
              }
              if (parsed.done && parsed.payload) {
                receivedDone = true;
                if (typing && typing.parentNode) typing.parentNode.removeChild(typing);
                var mode = parsed.payload.answer_mode || "";
                var modeStr = mode ? " [" + mode + "]" : "";
                assistantMsg(renderResponse(parsed.payload));
                setStatus("Ready" + modeStr, true);
                return;
              }
            } catch (err) {
              console.warn("[Assistant Stream] Line parse issue:", err);
            }
          }
          return readChunk();
        });
      }

      return readChunk();
    })
    .catch(function(streamErr) {
      console.warn("[Assistant] Streaming failed, falling back to /ask:", streamErr);
      fallbackPost();
    });
  }

  // ─── Submit ────────────────────────────────────────────────────────────────
  function handleQuestion(question) {
    question = (question || "").trim();
    if (!question) return;

    if (inputEl) inputEl.value = "";
    if (suggestEl) suggestEl.style.display = "none";

    userMsg(question);
    var typing = typingMsg();
    setStatus("⏳ Routing through 3-level answering strategy…", true);
    askBackend(question, typing);
  }


  // ─── Status Check on Load ──────────────────────────────────────────────────
  function checkStatus() {
    fetch(API_BASE + "/status")
      .then(function(res) { return res.json(); })
      .then(function(d) {
        // Support both old shape (d.model.connected) and new shape (d.model.primary_model)
        var modelOk   = d.model && (d.model.connected || d.model.primary_model);
        var cacheOk   = d.cache && d.cache.connected;
        var locs      = d.localities_indexed || 0;
        var primary   = (d.model && (d.model.primary_model || d.model.target_model)) || "qwen3:4b";
        var fallback  = d.model && d.model.fallback_model ? " ➔ " + d.model.fallback_model : "";
        var modelStr  = modelOk ? "✅ " + primary + fallback : "⚠ Ollama offline";
        var cacheStr  = cacheOk ? " · Redis ✅" : " · Redis bypassed";
        setStatus(modelStr + cacheStr + " · " + locs + " localities", modelOk);

        // Update suggestion pills with locality-aware queries
        if (locs > 0) {
          updateSuggestions(modelOk);
        }
      })
      .catch(function() {
        setStatus("⚠ Backend not reachable — start the server on port 8000", false);
      });
  }

  function updateSuggestions(modelOk) {
    if (!suggestEl) return;
    var pills = [
      { q: "Should I buy a house in Whitefield?",               label: "🏠 Buy in Whitefield?" },
      { q: "Is Koramangala safe for a family?",                  label: "👨‍👩‍👧 Koramangala safe?" },
      { q: "Compare Whitefield and HSR Layout",                  label: "⚖️ Whitefield vs HSR?" },
      { q: "What is the UrbanScore for Indiranagar?",            label: "⚡ Indiranagar score?" },
      { q: "What are the major infrastructure risks in Bellandur?", label: "🚧 Bellandur risks?" },
      { q: "Which area has better governance — BTM or Jayanagar?", label: "📋 BTM vs Jayanagar?" },
      { q: "Why is air quality poor in Peenya?",                 label: "🌫 Peenya AQI?" },
      { q: "What is the total BBMP construction investment in Bengaluru?", label: "💰 City-wide investment?" },
    ];
    suggestEl.innerHTML = pills.map(function(p) {
      return '<button type="button" class="category-pill" data-q="' + esc(p.q) + '">' + esc(p.label) + '</button>';
    }).join("");

    // Re-wire click events
    var newPills = suggestEl.querySelectorAll(".category-pill[data-q]");
    newPills.forEach(function(pill) {
      pill.addEventListener("click", function() {
        handleQuestion(pill.getAttribute("data-q"));
      });
    });
  }

  // ─── Event Wiring ──────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", function() {
    setStatus("Connecting to UrbanPulse Intelligence backend…", false);
    checkStatus();

    if (formEl) {
      formEl.addEventListener("submit", function(e) {
        e.preventDefault();
        handleQuestion(inputEl ? inputEl.value : "");
      });
    }

    // Original suggestion pills
    var pills = document.querySelectorAll("#chat-suggestions .category-pill[data-q]");
    pills.forEach(function(pill) {
      pill.addEventListener("click", function() {
        handleQuestion(pill.getAttribute("data-q"));
      });
    });

    // Live time display
    var timeEl = document.getElementById("live-time-display");
    if (timeEl) {
      function updateTime() {
        var t = new Date().toLocaleTimeString("en-IN", {
          hour: "2-digit", minute: "2-digit", second: "2-digit",
          hour12: false, timeZone: "Asia/Kolkata"
        });
        timeEl.textContent = t + " IST";
      }
      updateTime();
      setInterval(updateTime, 1000);
    }
  });

})();
