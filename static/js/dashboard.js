/* Dashboard: stats, collection trend, overdue list and recent payments. */
document.addEventListener("DOMContentLoaded", () => {
  document.addEventListener("profileready", loadDashboard, { once: true });
});

async function loadDashboard() {
  const statGrid = document.getElementById("statGrid");
  const trendEl = document.getElementById("trendChart");
  const overdueEl = document.getElementById("overdueList");
  const recentEl = document.getElementById("recentPayments");

  try {
    const data = await API.get("/api/dashboard/summary");
    renderStats(statGrid, data.stats);
    renderTrend(trendEl, data.trend);
    renderOverdue(overdueEl, data.overdue);
    renderRecent(recentEl, data.recent_payments);
  } catch (error) {
    UI.toast(error.message, "error");
    const message = '<div class="empty-state"><div class="empty-icon">&#9888;</div>' +
      "<h3>Could not load data</h3><p>" + UI.escapeHtml(error.message) + "</p></div>";
    statGrid.innerHTML = "";
    trendEl.innerHTML = message;
    overdueEl.innerHTML = "";
    recentEl.innerHTML = "";
  }
}

function statCard(label, value, sub, icon, tone) {
  return (
    '<article class="stat-card">' +
      '<div class="stat-top">' +
        '<span class="stat-label">' + UI.escapeHtml(label) + "</span>" +
        '<span class="stat-icon ' + tone + '">' + icon + "</span>" +
      "</div>" +
      '<div class="stat-value">' + value + "</div>" +
      '<div class="stat-sub">' + UI.escapeHtml(sub) + "</div>" +
    "</article>"
  );
}

function renderStats(container, stats) {
  container.innerHTML =
    statCard("Total properties", stats.total_properties, stats.active_tenants + " active tenants", "&#9962;", "") +
    statCard("Occupied", stats.occupied_properties, stats.occupancy_rate + "% occupancy rate", "&#128273;", "green") +
    statCard("Vacant", stats.vacant_properties, "Available to rent out", "&#128682;", "cyan") +
    statCard("Monthly rent", UI.compactMoney(stats.monthly_rent), "Expected from occupied units", "&#128181;", "amber") +
    statCard("Pending rent", UI.compactMoney(stats.pending_rent), "Collected this month: " + UI.compactMoney(stats.collected_this_month), "&#9203;", "red");
}

function renderTrend(container, trend) {
  if (!trend || !trend.length) {
    UI.emptyState(container, { icon: "&#128202;", title: "No collection data", message: "Record a rent payment to see the trend." });
    return;
  }
  const max = Math.max.apply(null, trend.map((t) => t.amount).concat([1]));
  container.innerHTML = trend
    .map((point) => {
      const height = Math.max((point.amount / max) * 100, 2);
      return (
        '<div class="chart-col">' +
          '<div class="chart-bar" style="height:' + height + '%"><span>' + UI.compactMoney(point.amount) + "</span></div>" +
          '<span class="chart-label">' + UI.formatMonth(point.month) + "</span>" +
        "</div>"
      );
    })
    .join("");
}

function renderOverdue(container, rows) {
  if (!rows || !rows.length) {
    UI.emptyState(container, { icon: "&#127881;", title: "All rent collected", message: "There is no outstanding rent right now." });
    return;
  }
  container.innerHTML = rows
    .map(
      (row) =>
        '<div class="list-row"><div><strong>' + UI.escapeHtml(row.tenant) + "</strong>" +
        '<span class="cell-sub">' + UI.escapeHtml(row.property || "No property") + " · " + UI.formatMonth(row.period_month) + "</span></div>" +
        '<span class="num" style="color:var(--danger)">' + UI.money(row.outstanding) + "</span></div>"
    )
    .join("");
}

function renderRecent(container, rows) {
  if (!rows || !rows.length) {
    UI.emptyState(container, { icon: "&#128179;", title: "No payments yet", message: "Payments you record will show up here." });
    return;
  }
  container.innerHTML =
    "<table><thead><tr><th>Tenant</th><th>Property</th><th>Method</th><th>Date</th>" +
    '<th class="text-right">Amount</th></tr></thead><tbody>' +
    rows
      .map(
        (row) =>
          '<tr><td data-label="Tenant">' + '<span class="cell-title">' + UI.escapeHtml(row.tenant) + "</span></td>" +
          '<td data-label="Property">' + UI.escapeHtml(row.property || "—") + "</td>" +
          '<td data-label="Method">' + UI.escapeHtml(row.payment_method || "—") + "</td>" +
          '<td data-label="Date">' + UI.formatDate(row.payment_date) + "</td>" +
          '<td class="text-right num" data-label="Amount">' + UI.money(row.amount_paid) + "</td></tr>"
      )
      .join("") +
    "</tbody></table>";
}
