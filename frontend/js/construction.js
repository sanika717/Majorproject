/**
 * UrbanPulse - Construction / Ward Infrastructure Analytics Module
 * Real Data-Driven Analytics from the verified BBMP ward work-order EDA
 * (see frontend/js/construction-data.js for the full verified dataset + provenance).
 */

class ConstructionAnalytics {
  constructor() {
    this.data = window.URBANPULSE_CONSTRUCTION_DATA || null;
    this.investmentChart = null;
    this.clusterChart = null;
    this.categoryChart = null;

    if (!this.data) {
      // No fabricated fallback numbers: if the data file didn't load, leave the
      // section exactly as its "EDA In Progress" HTML fallback already reads.
      return;
    }

    this.initCharts();
    this.render();
  }

  initCharts() {
    const invCtx = document.getElementById("construction-investment-chart")?.getContext("2d");
    if (invCtx) {
      this.investmentChart = new Chart(invCtx, {
        type: "bar",
        data: { labels: [], datasets: [] },
        options: this.baseChartOptions("Ward")
      });
    }

    const clusterCtx = document.getElementById("construction-cluster-chart")?.getContext("2d");
    if (clusterCtx) {
      this.clusterChart = new Chart(clusterCtx, {
        type: "bar",
        data: { labels: [], datasets: [] },
        options: this.baseChartOptions("")
      });
    }

    const catCtx = document.getElementById("construction-category-chart")?.getContext("2d");
    if (catCtx) {
      this.categoryChart = new Chart(catCtx, {
        type: "bar",
        data: { labels: [], datasets: [] },
        options: this.baseChartOptions("")
      });
    }
  }

  baseChartOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#94a3b8", font: { family: "Inter", size: 12 } } },
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
    };
  }

  crores(rupees) {
    return `₹${(rupees / 1e7).toFixed(2)} Cr`;
  }

  render() {
    this.renderKPIs();
    this.renderClusters();
    this.renderCharts();
    this.renderTable();
  }

  renderKPIs() {
    const ov = this.data.overview;

    const set = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    set("construction-kpi-orders", ov.total_work_orders.toLocaleString());
    set("construction-kpi-amount", this.crores(ov.total_amount));
    set("construction-kpi-wards", `${ov.official_numbered_wards_present} / ${ov.official_wards_total}`);
    set("construction-kpi-contractors", ov.unique_contractors.toLocaleString());
    set("construction-kpi-deduction", `${ov.avg_deduction_rate_pct}%`);
    set("construction-kpi-nonstandard", ov.non_standard_ward_codes_present);
  }

  renderClusters() {
    const clusters = this.data.clustering.clusters;
    const high = clusters.find(c => c.cluster === 0);
    const low = clusters.find(c => c.cluster === 1);

    const set = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    if (high) {
      set("cluster-high-count", high.ward_count);
      set("cluster-high-orders", high.avg_work_orders.toFixed(1));
      set("cluster-high-amount", this.crores(high.avg_total_amount));
      set("cluster-high-contractors", high.avg_contractors.toFixed(1));
    }
    if (low) {
      set("cluster-low-count", low.ward_count);
      set("cluster-low-orders", low.avg_work_orders.toFixed(1));
      set("cluster-low-amount", this.crores(low.avg_total_amount));
      set("cluster-low-contractors", low.avg_contractors.toFixed(1));
    }

    const sil = this.data.clustering.silhouette_by_k;
    const chosenK = this.data.clustering.chosen_k;
    set("cluster-silhouette", sil && sil[String(chosenK)] !== undefined ? sil[String(chosenK)] : (sil && sil[chosenK]));
  }

  renderCharts() {
    // Top 10 wards by verified total investment
    if (this.investmentChart) {
      const top = this.data.top_wards_by_investment.slice(0, 10);
      this.investmentChart.data.labels = top.map(w => `Ward ${w.ward}`);
      this.investmentChart.data.datasets = [{
        label: "Total Investment (₹)",
        data: top.map(w => w.total_amount),
        backgroundColor: "rgba(245, 158, 11, 0.6)",
        borderColor: "#f59e0b",
        borderWidth: 1,
        borderRadius: 6
      }];
      this.investmentChart.update();
    }

    // Cluster comparison (avg total amount + avg work orders)
    if (this.clusterChart) {
      const clusters = this.data.clustering.clusters;
      this.clusterChart.data.labels = clusters.map(c => c.cluster_name);
      this.clusterChart.data.datasets = [
        {
          label: "Avg Work Orders / Ward",
          data: clusters.map(c => c.avg_work_orders),
          backgroundColor: "rgba(56, 189, 248, 0.6)",
          borderColor: "#38bdf8",
          borderWidth: 1,
          borderRadius: 6,
          yAxisID: "y"
        }
      ];
      this.clusterChart.update();
    }

    // Work-category keyword tags (citywide totals; not mutually exclusive)
    if (this.categoryChart) {
      const cats = this.data.category_tags;
      const labels = {
        drain_projects: "Drain / Drainage",
        road_projects: "Road / Street",
        maintenance_projects: "Maintenance / Repair",
        development_projects: "Development / Improvement",
        water_projects: "Water / Pipeline / Sewer"
      };
      this.categoryChart.data.labels = Object.keys(cats).map(k => labels[k] || k);
      this.categoryChart.data.datasets = [{
        label: "Work Orders Tagged (keyword match)",
        data: Object.values(cats),
        backgroundColor: "rgba(16, 185, 129, 0.6)",
        borderColor: "#10b981",
        borderWidth: 1,
        borderRadius: 6
      }];
      this.categoryChart.update();
    }
  }

  renderTable() {
    const tableBody = document.getElementById("construction-data-table-body");
    if (!tableBody) return;
    tableBody.innerHTML = "";

    const rows = this.data.top_wards_by_investment.slice(0, 15);
    rows.forEach(w => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td style="font-weight: 700; color: #fff;">Ward ${w.ward}</td>
        <td>
          <span class="popup-badge" style="background: ${w.cluster_name.startsWith('High') ? 'rgba(245,158,11,0.2); color:#f59e0b' : 'rgba(56,189,248,0.2); color:#38bdf8'};">
            ${w.cluster_name}
          </span>
        </td>
        <td><b>${w.total_work_orders.toLocaleString()}</b></td>
        <td style="color: #f59e0b;">${this.crores(w.total_amount)}</td>
        <td style="color: #10b981;">${this.crores(w.total_net_expenditure)}</td>
        <td>${w.unique_contractors}</td>
      `;
      tableBody.appendChild(row);
    });
  }
}

window.initUrbanPulseConstructionAnalytics = function() {
  window.urbanpulseConstructionInstance = new ConstructionAnalytics();
};
