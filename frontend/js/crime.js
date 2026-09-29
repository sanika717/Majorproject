/**
 * UrbanPulse - Crime & Safety Analytics Module
 * Real Data-Driven Analytics for Bengaluru Crime Statistics
 */

class CrimeAnalytics {
  constructor() {
    this.data = window.URBANPULSE_DATA;
    this.currentYear = "2023";
    this.currentCategory = "all";
    
    this.trendChart = null;
    this.categoryChart = null;

    this.initEventListeners();
    this.initCharts();
    this.render();
  }

  initEventListeners() {
    const yearSelect = document.getElementById("crime-year-select");
    if (yearSelect) {
      yearSelect.addEventListener("change", (e) => {
        this.currentYear = e.target.value;
        this.render();
      });
    }

    const categoryPills = document.querySelectorAll(".category-pill[data-category]");
    categoryPills.forEach(pill => {
      pill.addEventListener("click", (e) => {
        const catId = pill.getAttribute("data-category");
        if (pill.classList.contains("disabled")) return;
        
        categoryPills.forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        
        this.currentCategory = catId;
        this.render();
        this.syncYearSelectAvailability();
      });
    });

    this.syncYearSelectAvailability();
  }

  // The Year selector only applies to the verified 2021-2023 category
  // breakdowns (women/children/cyber/accidental). "All Recorded Crimes" shows
  // a fixed verified historical figure, so the selector is disabled for it
  // rather than left implying it changes a number it doesn't affect.
  syncYearSelectAvailability() {
    const yearSelect = document.getElementById("crime-year-select");
    if (!yearSelect) return;
    const applies = this.currentCategory !== "all";
    yearSelect.disabled = !applies;
    yearSelect.title = applies ? "" : "Year selector applies to the category tabs above — 'All Recorded Crimes' shows the verified 2014-2021 historical total.";
  }

  initCharts() {
    // Chart 1: Trend Chart
    const trendCtx = document.getElementById("crime-trend-chart")?.getContext("2d");
    if (trendCtx) {
      // "All Recorded Crimes" only has one verified overall data point today —
      // the 2014-2021 (Up to Dec) historical aggregate — so the trend chart
      // shows that single verified bar/point rather than inventing a
      // year-over-year 2021-2023 line that isn't backed by the EDA notebook.
      const hist = this.data.historical || {};
      this.trendChart = new Chart(trendCtx, {
        type: "bar",
        data: {
          labels: [hist.period_label || "2014 – 2021"],
          datasets: [
            {
              label: "Fatal Cases",
              data: [hist.fatal_crimes || 0],
              backgroundColor: "rgba(239, 68, 68, 0.6)",
              borderColor: "#ef4444",
              borderWidth: 1,
              borderRadius: 6
            },
            {
              label: "Non-Fatal Cases",
              data: [hist.non_fatal_crimes || 0],
              backgroundColor: "rgba(56, 189, 248, 0.6)",
              borderColor: "#38bdf8",
              borderWidth: 1,
              borderRadius: 6
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              labels: { color: "#94a3b8", font: { family: "Inter", size: 12 } }
            },
            tooltip: {
              backgroundColor: "rgba(15, 23, 42, 0.95)",
              titleColor: "#fff",
              bodyColor: "#94a3b8",
              borderColor: "rgba(56, 189, 248, 0.3)",
              borderWidth: 1
            }
          },
          scales: {
            x: {
              grid: { color: "rgba(255, 255, 255, 0.05)" },
              ticks: { color: "#94a3b8" }
            },
            y: {
              grid: { color: "rgba(255, 255, 255, 0.05)" },
              ticks: { color: "#94a3b8" }
            }
          }
        }
      });
    }

    // Chart 2: Category / Division Breakdown Chart
    const catCtx = document.getElementById("crime-category-chart")?.getContext("2d");
    if (catCtx) {
      this.categoryChart = new Chart(catCtx, {
        type: "bar",
        data: {
          labels: [],
          datasets: [{
            label: "Reported Cases",
            data: [],
            backgroundColor: "rgba(56, 189, 248, 0.6)",
            borderColor: "#38bdf8",
            borderWidth: 1,
            borderRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              labels: { color: "#94a3b8", font: { family: "Inter", size: 12 } }
            },
            tooltip: {
              backgroundColor: "rgba(15, 23, 42, 0.95)",
              titleColor: "#fff",
              bodyColor: "#94a3b8",
              borderColor: "rgba(56, 189, 248, 0.3)",
              borderWidth: 1
            }
          },
          scales: {
            x: {
              grid: { color: "rgba(255, 255, 255, 0.05)" },
              ticks: { color: "#94a3b8", maxRotation: 45, minRotation: 0 }
            },
            y: {
              grid: { color: "rgba(255, 255, 255, 0.05)" },
              ticks: { color: "#94a3b8" }
            }
          }
        }
      });
    }
  }

  // Source + methodology shown for whatever is currently displayed.
  static SOURCES = {
    all: { src: "D47 City-level Crime Statistics series (Fatal / Non-Fatal, Bangalore City, 2014–2021 up to Dec).", method: "Totals summed across years; Fatal % = fatal ÷ total. UrbanPulse Risk Score = 60% Volume + 40% Severity, shown for the peak year. Overall 2021–2023 totals are EDA In Progress, so the year selector does not apply." },
    women: { src: "Bengaluru City Police Press Note — Crimes Against Women, 2021–2023.", method: "Reported and detected counts transcribed as published; Detection % = detected ÷ reported. City-level, not station-level." },
    children: { src: "Bengaluru City Police Press Note — Crimes Against Children, 2021–2023.", method: "Reported and detected counts as published; Detection % = detected ÷ reported. City-level, not station-level." },
    cyber: { src: "Bengaluru City Police Press Note — Cyber Crime by Police Division, 2021–2023.", method: "Division-wise reported/detected counts as published; Pending = reported − detected. Divisions are administrative, not individual stations." },
    suicides: { src: "Bengaluru City Police Press Note — Suicides & Accidental Deaths, 2021–2023.", method: "Male/female counts by method as published; per-year method rows sum to the published total. City-level." },
    accidental: { src: "Bengaluru City Police Press Note — Suicides & Accidental Deaths, 2021–2023.", method: "Male/female counts by cause as published; per-year cause rows sum to the published total. City-level." }
  };

  renderSource() {
    const el = document.getElementById("crime-source-note");
    if (!el) return;
    const info = CrimeAnalytics.SOURCES[this.currentCategory];
    if (!info) return;
    el.innerHTML = `<b>Source:</b> ${info.src}<br><b>Methodology:</b> ${info.method}`;
  }

  render() {
    this.renderSource();
    this.renderKPIs();
    this.renderRiskScore();
    this.renderCharts();
    this.renderTable();
  }

  renderKPIs() {
    const kpiTotal = document.getElementById("kpi-total-crimes");
    const kpiFatal = document.getElementById("kpi-fatal-crimes");
    const kpiNonFatal = document.getElementById("kpi-nonfatal-crimes");
    const kpiRate = document.getElementById("kpi-detection-rate");

    const labelTotal = document.getElementById("kpi-label-total");
    const labelFatal = document.getElementById("kpi-label-fatal");
    const labelNonFatal = document.getElementById("kpi-label-nonfatal");
    const labelRate = document.getElementById("kpi-label-rate");

    if (this.currentCategory === "all") {
      // Verified historical aggregate (2014-2021, Up to Dec) — the only
      // overall city-wide crime result completed in the EDA notebook.
      // Year-by-year 2021-2023 overall totals are not yet verified, so the
      // shared Year selector does not apply to this card (see disclaimer below it).
      const hist = this.data.historical || {};
      if (kpiTotal) kpiTotal.textContent = (hist.total_crimes || 0).toLocaleString();
      if (kpiFatal) kpiFatal.textContent = (hist.fatal_crimes || 0).toLocaleString();
      if (kpiNonFatal) kpiNonFatal.textContent = (hist.non_fatal_crimes || 0).toLocaleString();
      if (kpiRate) kpiRate.textContent = `${hist.fatal_percentage || 0}%`;

      if (labelTotal) labelTotal.textContent = `Total Crimes (${hist.period_label || "Historical"})`;
      if (labelFatal) labelFatal.textContent = `Fatal Crimes`;
      if (labelNonFatal) labelNonFatal.textContent = `Non-Fatal Crimes`;
      if (labelRate) labelRate.textContent = `Fatal Severity %`;
    } else if (this.currentCategory === "women") {
      const catData = this.data.categories.women.years[this.currentYear];
      if (kpiTotal) kpiTotal.textContent = catData.total_reported.toLocaleString();
      if (kpiFatal) kpiFatal.textContent = catData.total_detected.toLocaleString();
      if (kpiNonFatal) kpiNonFatal.textContent = (catData.total_reported - catData.total_detected).toLocaleString();
      if (kpiRate) kpiRate.textContent = `${catData.overall_detection_pct}%`;

      if (labelTotal) labelTotal.textContent = `Reported Women Crimes`;
      if (labelFatal) labelFatal.textContent = `Detected / Solved`;
      if (labelNonFatal) labelNonFatal.textContent = `Pending Cases`;
      if (labelRate) labelRate.textContent = `Detection Rate`;
    } else if (this.currentCategory === "children") {
      const catData = this.data.categories.children.years[this.currentYear];
      if (kpiTotal) kpiTotal.textContent = catData.total_reported.toLocaleString();
      if (kpiFatal) kpiFatal.textContent = catData.total_detected.toLocaleString();
      if (kpiNonFatal) kpiNonFatal.textContent = (catData.total_reported - catData.total_detected).toLocaleString();
      if (kpiRate) kpiRate.textContent = `${catData.overall_detection_pct}%`;

      if (labelTotal) labelTotal.textContent = `Crimes Against Children`;
      if (labelFatal) labelFatal.textContent = `Detected Cases`;
      if (labelNonFatal) labelNonFatal.textContent = `Under Investigation`;
      if (labelRate) labelRate.textContent = `Detection Rate`;
    } else if (this.currentCategory === "cyber") {
      const catData = this.data.categories.cyber.years[this.currentYear];
      if (kpiTotal) kpiTotal.textContent = catData.total_reported.toLocaleString();
      if (kpiFatal) kpiFatal.textContent = catData.total_detected.toLocaleString();
      if (kpiNonFatal) kpiNonFatal.textContent = (catData.total_reported - catData.total_detected).toLocaleString();
      if (kpiRate) kpiRate.textContent = `${catData.overall_detection_pct}%`;

      if (labelTotal) labelTotal.textContent = `Reported Cyber Crimes`;
      if (labelFatal) labelFatal.textContent = `Detected Cyber Cases`;
      if (labelNonFatal) labelNonFatal.textContent = `Pending / UI Cases`;
      if (labelRate) labelRate.textContent = `Detection Rate`;
    } else if (this.currentCategory === "suicides") {
      const catData = this.data.categories.suicides.years[this.currentYear];
      if (kpiTotal) kpiTotal.textContent = catData.total_suicides.toLocaleString();
      if (kpiFatal) kpiFatal.textContent = catData.total_male.toLocaleString();
      if (kpiNonFatal) kpiNonFatal.textContent = catData.total_female.toLocaleString();
      if (kpiRate) kpiRate.textContent = `${((catData.total_male / catData.total_suicides) * 100).toFixed(1)}%`;

      if (labelTotal) labelTotal.textContent = `Total Suicides`;
      if (labelFatal) labelFatal.textContent = `Male`;
      if (labelNonFatal) labelNonFatal.textContent = `Female`;
      if (labelRate) labelRate.textContent = `Male Share %`;
    } else if (this.currentCategory === "accidental") {
      const catData = this.data.categories.accidental.years[this.currentYear];
      if (kpiTotal) kpiTotal.textContent = catData.total_accidental_deaths.toLocaleString();
      if (kpiFatal) kpiFatal.textContent = catData.total_male.toLocaleString();
      if (kpiNonFatal) kpiNonFatal.textContent = catData.total_female.toLocaleString();
      if (kpiRate) kpiRate.textContent = `${((catData.total_male / catData.total_accidental_deaths) * 100).toFixed(1)}%`;

      if (labelTotal) labelTotal.textContent = `Total Accidental Deaths`;
      if (labelFatal) labelFatal.textContent = `Male Fatalities`;
      if (labelNonFatal) labelNonFatal.textContent = `Female Fatalities`;
      if (labelRate) labelRate.textContent = `Male Ratio %`;
    }
  }

  renderRiskScore() {
    // The UrbanPulse Risk Score gauge always reflects the verified historical
    // peak (2016, within the 2014-2021 D47 series) — it does not change with
    // the category/year selectors below, since no other verified risk score
    // currently exists. No hardcoded fallback numbers are used: if `historical`
    // is missing, the gauge shows "N/A" rather than a guessed figure.
    const hist = this.data.historical || null;
    const riskScoreEl = document.getElementById("risk-score-value");
    const riskBadgeEl = document.getElementById("risk-level-badge");
    const riskArcEl = document.getElementById("risk-gauge-arc");
    const volumeScoreEl = document.getElementById("risk-volume-score");
    const severityScoreEl = document.getElementById("risk-severity-score");

    if (!hist) {
      if (riskScoreEl) riskScoreEl.textContent = "N/A";
      if (volumeScoreEl) volumeScoreEl.textContent = "N/A";
      if (severityScoreEl) severityScoreEl.textContent = "N/A";
      if (riskBadgeEl) riskBadgeEl.textContent = "Data Unavailable";
      return;
    }

    const score = hist.highest_risk_score;
    const level = hist.highest_risk_level;

    if (riskScoreEl) riskScoreEl.textContent = score.toFixed(1);
    if (volumeScoreEl) volumeScoreEl.textContent = `${hist.highest_risk_volume_score}/100`;
    if (severityScoreEl) severityScoreEl.textContent = `${hist.highest_risk_severity_score}/100`;

    if (riskBadgeEl) {
      riskBadgeEl.textContent = `${level} (${hist.highest_risk_year})`;
      if (level === "High Risk") {
        riskBadgeEl.style.backgroundColor = "rgba(239, 68, 68, 0.2)";
        riskBadgeEl.style.color = "#ef4444";
        riskBadgeEl.style.border = "1px solid rgba(239, 68, 68, 0.4)";
      } else {
        riskBadgeEl.style.backgroundColor = "rgba(245, 158, 11, 0.2)";
        riskBadgeEl.style.color = "#f59e0b";
        riskBadgeEl.style.border = "1px solid rgba(245, 158, 11, 0.4)";
      }
    }

    // Gauge arc update (circumference ~ 220 for a semicircle)
    if (riskArcEl) {
      const strokeDashoffset = 220 - (220 * (score / 100));
      riskArcEl.style.strokeDashoffset = strokeDashoffset;
      riskArcEl.style.stroke = level === "High Risk" ? "#ef4444" : "#f59e0b";
    }
  }

  renderCharts() {
    if (!this.categoryChart) return;

    if (this.currentCategory === "all") {
      this.categoryChart.data.labels = ["Fatal", "Non-Fatal"];
      const hist = this.data.historical || { fatal_crimes: 0, non_fatal_crimes: 0 };
      this.categoryChart.data.datasets = [{
        label: "Cases",
        data: [hist.fatal_crimes, hist.non_fatal_crimes],
        backgroundColor: ["rgba(239, 68, 68, 0.6)", "rgba(56, 189, 248, 0.6)"],
        borderColor: ["#ef4444", "#38bdf8"],
        borderWidth: 1,
        borderRadius: 6
      }];
    } else if (this.currentCategory === "women") {
      const items = this.data.categories.women.years[this.currentYear].items;
      this.categoryChart.data.labels = items.map(i => i.crime);
      this.categoryChart.data.datasets = [
        {
          label: "Reported Cases",
          data: items.map(i => i.reported),
          backgroundColor: "rgba(244, 63, 94, 0.6)",
          borderColor: "#f43f5e",
          borderWidth: 1,
          borderRadius: 6
        },
        {
          label: "Detected Cases",
          data: items.map(i => i.detected),
          backgroundColor: "rgba(16, 185, 129, 0.6)",
          borderColor: "#10b981",
          borderWidth: 1,
          borderRadius: 6
        }
      ];
    } else if (this.currentCategory === "children") {
      const items = this.data.categories.children.years[this.currentYear].items;
      this.categoryChart.data.labels = items.map(i => i.crime);
      this.categoryChart.data.datasets = [
        {
          label: "Reported Cases",
          data: items.map(i => i.reported),
          backgroundColor: "rgba(168, 85, 247, 0.6)",
          borderColor: "#a855f7",
          borderWidth: 1,
          borderRadius: 6
        },
        {
          label: "Detected Cases",
          data: items.map(i => i.detected),
          backgroundColor: "rgba(16, 185, 129, 0.6)",
          borderColor: "#10b981",
          borderWidth: 1,
          borderRadius: 6
        }
      ];
    } else if (this.currentCategory === "cyber") {
      const items = this.data.categories.cyber.years[this.currentYear].items;
      this.categoryChart.data.labels = items.map(i => i.division);
      this.categoryChart.data.datasets = [
        {
          label: "Reported Cases",
          data: items.map(i => i.reported),
          backgroundColor: "rgba(56, 189, 248, 0.6)",
          borderColor: "#38bdf8",
          borderWidth: 1,
          borderRadius: 6
        },
        {
          label: "Detected Cases",
          data: items.map(i => i.detected),
          backgroundColor: "rgba(16, 185, 129, 0.6)",
          borderColor: "#10b981",
          borderWidth: 1,
          borderRadius: 6
        }
      ];
    } else if (this.currentCategory === "suicides") {
      const items = this.data.categories.suicides.years[this.currentYear].items;
      this.categoryChart.data.labels = items.map(i => i.cause);
      this.categoryChart.data.datasets = [
        { label: "Male", data: items.map(i => i.male), backgroundColor: "rgba(59, 130, 246, 0.6)", borderColor: "#3b82f6", borderWidth: 1, borderRadius: 6 },
        { label: "Female", data: items.map(i => i.female), backgroundColor: "rgba(236, 72, 153, 0.6)", borderColor: "#ec4899", borderWidth: 1, borderRadius: 6 }
      ];
    } else if (this.currentCategory === "accidental") {
      const items = this.data.categories.accidental.years[this.currentYear].items;
      this.categoryChart.data.labels = items.map(i => i.cause);
      this.categoryChart.data.datasets = [
        {
          label: "Male Fatalities",
          data: items.map(i => i.male),
          backgroundColor: "rgba(59, 130, 246, 0.6)",
          borderColor: "#3b82f6",
          borderWidth: 1,
          borderRadius: 6
        },
        {
          label: "Female Fatalities",
          data: items.map(i => i.female),
          backgroundColor: "rgba(236, 72, 153, 0.6)",
          borderColor: "#ec4899",
          borderWidth: 1,
          borderRadius: 6
        }
      ];
    }

    this.categoryChart.update();
  }

  renderTable() {
    const tableBody = document.getElementById("crime-data-table-body");
    const tableTitle = document.getElementById("crime-table-title");
    const col1 = document.getElementById("table-col-1");
    const col2 = document.getElementById("table-col-2");
    const col3 = document.getElementById("table-col-3");
    const col4 = document.getElementById("table-col-4");

    if (!tableBody) return;
    tableBody.innerHTML = "";

    if (this.currentCategory === "all") {
      if (tableTitle) tableTitle.textContent = `Bengaluru City-Wide Crime Totals (Verified D47 EDA)`;
      if (col1) col1.textContent = "Period";
      if (col2) col2.textContent = "Total Recorded";
      if (col3) col3.textContent = "Fatal Cases";
      if (col4) col4.textContent = "Fatal Severity %";

      const hist = this.data.historical;
      if (hist) {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td style="font-weight: 700; color: #fff;">${hist.period_label}</td>
          <td><b>${hist.total_crimes.toLocaleString()}</b></td>
          <td style="color: #ef4444;">${hist.fatal_crimes.toLocaleString()}</td>
          <td>
            <div class="progress-bar-container">
              <div class="progress-bar-fill" style="width: ${hist.fatal_percentage}%; background: #ef4444;"></div>
            </div>
            <span>${hist.fatal_percentage}%</span>
          </td>
        `;
        tableBody.appendChild(row);

        const noteRow = document.createElement("tr");
        noteRow.innerHTML = `<td colspan="4" style="font-size: 11px; color: var(--text-muted); text-align: center; padding-top: 10px;">
          Year-by-year (2021-2023) breakdown of overall city-wide totals is EDA In Progress. See the verified category tabs above for real 2021-2023 data.
        </td>`;
        tableBody.appendChild(noteRow);
      }
    } else if (this.currentCategory === "women" || this.currentCategory === "children") {
      const catConfig = this.currentCategory === "women" ? this.data.categories.women : this.data.categories.children;
      const catData = catConfig.years[this.currentYear];
      
      if (tableTitle) tableTitle.textContent = `${catConfig.title} Breakdown (${this.currentYear})`;
      if (col1) col1.textContent = "Crime Type";
      if (col2) col2.textContent = "Reported Cases";
      if (col3) col3.textContent = "Detected / Solved";
      if (col4) col4.textContent = "Detection Rate %";

      catData.items.forEach(item => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td style="font-weight: 600; color: #fff;">${item.crime}</td>
          <td><b>${item.reported.toLocaleString()}</b></td>
          <td style="color: #10b981;">${item.detected.toLocaleString()}</td>
          <td>
            <div class="progress-bar-container">
              <div class="progress-bar-fill" style="width: ${item.detection_pct}%;"></div>
            </div>
            <span>${item.detection_pct}%</span>
          </td>
        `;
        tableBody.appendChild(row);
      });
    } else if (this.currentCategory === "cyber") {
      const catData = this.data.categories.cyber.years[this.currentYear];
      if (tableTitle) tableTitle.textContent = `Cyber Crime by Police Division (${this.currentYear})`;
      if (col1) col1.textContent = "Police Division";
      if (col2) col2.textContent = "Reported Cases";
      if (col3) col3.textContent = "Detected Cases";
      if (col4) col4.textContent = "Detection Rate %";

      catData.items.forEach(item => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td style="font-weight: 600; color: #fff;">${item.division}</td>
          <td><b>${item.reported.toLocaleString()}</b></td>
          <td style="color: #10b981;">${item.detected.toLocaleString()}</td>
          <td>
            <div class="progress-bar-container">
              <div class="progress-bar-fill" style="width: ${item.detection_pct}%;"></div>
            </div>
            <span>${item.detection_pct}%</span>
          </td>
        `;
        tableBody.appendChild(row);
      });
    } else if (this.currentCategory === "suicides") {
      const catData = this.data.categories.suicides.years[this.currentYear];
      if (tableTitle) tableTitle.textContent = `Suicides by Method & Gender (${this.currentYear})`;
      if (col1) col1.textContent = "Method";
      if (col2) col2.textContent = "Male";
      if (col3) col3.textContent = "Female";
      if (col4) col4.textContent = "Total";

      catData.items.forEach(item => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td style="font-weight: 600; color: #fff;">${item.cause}</td>
          <td style="color: #38bdf8;">${item.male.toLocaleString()}</td>
          <td style="color: #ec4899;">${item.female.toLocaleString()}</td>
          <td><b>${item.total.toLocaleString()}</b></td>
        `;
        tableBody.appendChild(row);
      });
    } else if (this.currentCategory === "accidental") {
      const catData = this.data.categories.accidental.years[this.currentYear];
      if (tableTitle) tableTitle.textContent = `Accidental Deaths by Cause & Gender (${this.currentYear})`;
      if (col1) col1.textContent = "Cause of Death";
      if (col2) col2.textContent = "Male";
      if (col3) col3.textContent = "Female";
      if (col4) col4.textContent = "Total Fatalities";

      catData.items.forEach(item => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td style="font-weight: 600; color: #fff;">${item.cause}</td>
          <td style="color: #38bdf8;">${item.male.toLocaleString()}</td>
          <td style="color: #ec4899;">${item.female.toLocaleString()}</td>
          <td><b>${item.total.toLocaleString()}</b></td>
        `;
        tableBody.appendChild(row);
      });
    }
  }
}

window.initUrbanPulseCrimeAnalytics = function() {
  window.urbanpulseCrimeInstance = new CrimeAnalytics();
};
