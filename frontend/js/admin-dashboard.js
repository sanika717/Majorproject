/**
 * UrbanPulse - Grievance Administration Overview Dashboard
 * Drives KPI cards, Chart.js visualizations, department breakdown, and most overdue grievance triage.
 */

window.UrbanPulseAdminDashboard = (function() {
  let charts = {
    statusDoughnut: null,
    categoryBar: null,
    wardBar: null,
    trendLine: null
  };

  function getApiBase() {
    const isHttp = window.location.protocol.startsWith("http");
    const host = window.location.hostname || "127.0.0.1";
    const port = window.location.port;
    return isHttp && port === "8000" ? "/api/v1" : `http://${host}:8000/api/v1`;
  }

  async function loadDashboard(token, onOpenTicketReview) {
    const apiBase = getApiBase();
    try {
      const res = await fetch(`${apiBase}/complaints/admin/dashboard`, {
        headers: {
          "Authorization": `Bearer ${token}`,
          "Accept": "application/json"
        }
      });

      if (!res.ok) {
        console.error("Dashboard metrics failed to load:", res.status);
        return;
      }

      const data = await res.json();
      renderDashboard(data, onOpenTicketReview);
    } catch (err) {
      console.error("Error fetching dashboard metrics:", err);
    }
  }

  function renderDashboard(data, onOpenTicketReview) {
    // 1. Last Updated Timestamp
    const lastUpdatedEl = document.getElementById("dash-last-updated");
    if (lastUpdatedEl) {
      lastUpdatedEl.textContent = new Date().toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true
      });
    }

    // 2. KPI Cards
    const totals = data.totals || {};
    const sla = data.sla || {};

    const openCount = (totals.submitted || 0) + (totals.under_review || 0) + (totals.in_progress || 0);

    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    setVal("dash-kpi-open", openCount);
    setVal("dash-kpi-overdue", totals.overdue || 0);
    setVal("dash-kpi-critical", totals.critical_open || 0);
    setVal("dash-kpi-resolved", totals.resolved || 0);
    setVal("dash-kpi-sla", sla.compliance_pct !== null && sla.compliance_pct !== undefined ? `${sla.compliance_pct}%` : "N/A");
    setVal("dash-kpi-avg-time", sla.avg_resolution_hours !== null && sla.avg_resolution_hours !== undefined ? `${sla.avg_resolution_hours} hrs` : "N/A");

    // 3. Render Status Doughnut Chart
    renderStatusDoughnut(totals);

    // 4. Render Category Bar Chart
    renderCategoryChart(data.by_category || []);

    // 5. Render Top 10 Wards Bar Chart
    renderWardChart(data.by_ward || []);

    // 6. Render 30-Day Trend Line Chart
    renderTrendChart(data.trend || []);

    // 7. Render Department Table
    renderDepartmentTable(data.by_department || []);

    // 8. Render Most Overdue List
    renderMostOverdueList(data.most_overdue || [], onOpenTicketReview);
  }

  function renderStatusDoughnut(totals) {
    const canvas = document.getElementById("chart-status-doughnut");
    if (!canvas || typeof Chart === "undefined") return;

    if (charts.statusDoughnut) {
      charts.statusDoughnut.destroy();
    }

    const labels = ["Submitted", "Under Review", "In Progress", "Resolved", "Rejected"];
    const values = [
      totals.submitted || 0,
      totals.under_review || 0,
      totals.in_progress || 0,
      totals.resolved || 0,
      totals.rejected || 0
    ];
    const colors = ["#94a3b8", "#f59e0b", "#3b82f6", "#10b981", "#ef4444"];

    charts.statusDoughnut = new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderColor: "#0f172a",
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
            labels: { color: "#cbd5e1", boxWidth: 12, padding: 12, font: { size: 11, family: "Inter" } }
          }
        },
        cutout: "65%"
      }
    });
  }

  function renderCategoryChart(categories) {
    const canvas = document.getElementById("chart-category-bar");
    if (!canvas || typeof Chart === "undefined") return;

    if (charts.categoryBar) {
      charts.categoryBar.destroy();
    }

    const labels = categories.map(c => c.label);
    const data = categories.map(c => c.count);

    charts.categoryBar = new Chart(canvas, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          label: "Complaints",
          data: data,
          backgroundColor: "rgba(56, 189, 248, 0.7)",
          borderColor: "#38bdf8",
          borderWidth: 1,
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: "y",
        scales: {
          x: {
            grid: { color: "rgba(255,255,255,0.06)" },
            ticks: { color: "#94a3b8", precision: 0 }
          },
          y: {
            grid: { display: false },
            ticks: { color: "#cbd5e1", font: { size: 11 } }
          }
        },
        plugins: {
          legend: { display: false }
        }
      }
    });
  }

  function renderWardChart(wards) {
    const canvas = document.getElementById("chart-ward-bar");
    if (!canvas || typeof Chart === "undefined") return;

    if (charts.wardBar) {
      charts.wardBar.destroy();
    }

    const labels = wards.map(w => w.label);
    const data = wards.map(w => w.count);

    charts.wardBar = new Chart(canvas, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          label: "Volume",
          data: data,
          backgroundColor: "rgba(244, 63, 94, 0.7)",
          borderColor: "#f43f5e",
          borderWidth: 1,
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            grid: { color: "rgba(255,255,255,0.06)" },
            ticks: { color: "#94a3b8", precision: 0 }
          },
          x: {
            grid: { display: false },
            ticks: { color: "#cbd5e1", font: { size: 11 }, maxRotation: 45, minRotation: 30 }
          }
        },
        plugins: {
          legend: { display: false }
        }
      }
    });
  }

  function renderTrendChart(trend) {
    const canvas = document.getElementById("chart-trend-line");
    if (!canvas || typeof Chart === "undefined") return;

    if (charts.trendLine) {
      charts.trendLine.destroy();
    }

    // Format label to MM-DD
    const labels = trend.map(t => {
      const parts = t.date.split("-");
      return `${parts[1]}/${parts[2]}`;
    });
    const subData = trend.map(t => t.submitted);
    const resData = trend.map(t => t.resolved);

    charts.trendLine = new Chart(canvas, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Lodged",
            data: subData,
            borderColor: "#38bdf8",
            backgroundColor: "rgba(56, 189, 248, 0.15)",
            tension: 0.3,
            fill: true,
            pointRadius: 2
          },
          {
            label: "Resolved",
            data: resData,
            borderColor: "#10b981",
            backgroundColor: "rgba(16, 185, 129, 0.15)",
            tension: 0.3,
            fill: true,
            pointRadius: 2
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        scales: {
          y: {
            grid: { color: "rgba(255,255,255,0.06)" },
            ticks: { color: "#94a3b8", precision: 0 }
          },
          x: {
            grid: { color: "rgba(255,255,255,0.04)" },
            ticks: { color: "#cbd5e1", font: { size: 10 }, maxTicksLimit: 15 }
          }
        },
        plugins: {
          legend: {
            position: "top",
            labels: { color: "#cbd5e1", boxWidth: 12, padding: 12 }
          }
        }
      }
    });
  }

  function renderDepartmentTable(depts) {
    const tbody = document.getElementById("dash-dept-tbody");
    if (!tbody) return;

    if (depts.length === 0) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; padding: 24px; color: var(--text-muted);">No departmental grievance records active.</td></tr>`;
      return;
    }

    tbody.innerHTML = depts.map(d => {
      const open = d.open || 0;
      const res = d.resolved || 0;
      const total = open + res;
      const rate = total > 0 ? Math.round((res / total) * 100) : 0;
      return `
        <tr style="border-bottom: 1px solid var(--border-subtle);">
          <td style="padding: 12px 16px; font-weight: 600; color: #fff;">${d.label}</td>
          <td style="padding: 12px 16px; color: #38bdf8; font-weight: 700;">${open}</td>
          <td style="padding: 12px 16px; color: #10b981; font-weight: 700;">${res}</td>
          <td style="padding: 12px 16px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <div style="flex: 1; height: 6px; background: rgba(255,255,255,0.08); border-radius: 999px; overflow: hidden;">
                <div style="height: 100%; width: ${rate}%; background: ${rate >= 75 ? '#10b981' : (rate >= 40 ? '#f59e0b' : '#f43f5e')};"></div>
              </div>
              <span style="font-size: 11px; color: var(--text-muted); min-width: 35px; text-align: right;">${rate}%</span>
            </div>
          </td>
        </tr>
      `;
    }).join("");
  }

  function renderMostOverdueList(overdueItems, onOpenTicketReview) {
    const listEl = document.getElementById("dash-overdue-list");
    if (!listEl) return;

    if (overdueItems.length === 0) {
      listEl.innerHTML = `
        <div style="padding: 32px 16px; text-align: center; color: var(--text-muted);">
          <div style="font-size: 28px; margin-bottom: 8px;">🎉</div>
          <div style="color: #10b981; font-weight: 600; font-size: 14px;">Zero Overdue Grievances</div>
          <div style="font-size: 12px; margin-top: 4px;">All active grievances are currently compliant within their SLA windows.</div>
        </div>
      `;
      return;
    }

    listEl.innerHTML = overdueItems.map(item => {
      const priColor = item.priority === "CRITICAL" ? "#f43f5e" : (item.priority === "HIGH" ? "#fb923c" : "#38bdf8");
      return `
        <div class="glass-panel" style="padding: 12px 16px; margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; border-color: rgba(239, 68, 68, 0.3); background: rgba(30, 15, 20, 0.4);">
          <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
            <span style="font-family: monospace; font-weight: 800; color: #fff; font-size: 13px;">${item.ticket_id}</span>
            <span style="font-size: 12px; color: var(--text-secondary);">${item.category}</span>
            ${item.ward ? `<span style="font-size: 11px; color: var(--text-muted); background: rgba(255,255,255,0.06); padding: 2px 6px; border-radius: 4px;">📍 ${item.ward}</span>` : ""}
            <span style="font-size: 11px; font-weight: 700; color: ${priColor}; border: 1px solid ${priColor}40; padding: 2px 8px; border-radius: 999px;">${item.priority}</span>
          </div>
          <div style="display: flex; align-items: center; gap: 12px;">
            <span class="badge-status-overdue" style="font-size: 11px; font-weight: 700; color: #f87171; border: 1px solid #ef4444; padding: 3px 8px; border-radius: 4px; background: rgba(239,68,68,0.1);">
              ⚠️ ${item.hours_overdue} hrs overdue
            </span>
            <button class="btn btn-sm" style="background: rgba(244,63,94,0.15); border: 1px solid rgba(244,63,94,0.3); color: #f87171; padding: 4px 10px; font-size: 12px; font-weight: 600; cursor: pointer; border-radius: var(--radius-sm);" onclick="window.UrbanPulseAdminDashboard.openTicket('${item.ticket_id}')">
              Review Ticket →
            </button>
          </div>
        </div>
      `;
    }).join("");

    window.UrbanPulseAdminDashboard._onOpen = onOpenTicketReview;
  }

  function openTicket(ticketId) {
    if (typeof window.UrbanPulseAdminDashboard._onOpen === "function") {
      window.UrbanPulseAdminDashboard._onOpen(ticketId);
    }
  }

  return {
    loadDashboard,
    openTicket
  };
})();
