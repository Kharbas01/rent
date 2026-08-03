/* Property management: list, search, filter, create, edit, delete. */
(function () {
  const state = { items: [], search: "", status: "all" };

  document.addEventListener("DOMContentLoaded", () => {
    UI.bindModalClose("propertyModal");

    document.getElementById("addPropertyBtn").addEventListener("click", () => openForm());
    document.getElementById("propertyForm").addEventListener("submit", save);

    document.getElementById("propertySearch").addEventListener(
      "input",
      UI.debounce((event) => { state.search = event.target.value.trim(); load(); }, 320)
    );
    document.getElementById("propertyStatusFilter").addEventListener("change", (event) => {
      state.status = event.target.value;
      load();
    });

    document.addEventListener("profileready", load, { once: true });
  });

  async function load() {
    const container = document.getElementById("propertyTable");
    UI.showLoader(container);
    try {
      const data = await API.get("/api/properties", { search: state.search, status: state.status });
      state.items = data.items;
      render(container, data.items);
    } catch (error) {
      UI.toast(error.message, "error");
      UI.emptyState(container, { icon: "&#9888;", title: "Could not load properties", message: error.message });
    }
  }

  function render(container, items) {
    if (!items.length) {
      UI.emptyState(container, {
        icon: "&#9962;",
        title: state.search || state.status !== "all" ? "No matching properties" : "No properties yet",
        message: state.search || state.status !== "all"
          ? "Try a different search term or clear the filters."
          : "Add your first property to start tracking rent and tenants.",
        actionId: "emptyAddProperty",
        actionLabel: "+ Add property",
      });
      const button = document.getElementById("emptyAddProperty");
      if (button) button.addEventListener("click", () => openForm());
      return;
    }

    container.innerHTML =
      "<table><thead><tr><th>Property</th><th>Type</th><th>Address</th><th>Status</th>" +
      '<th class="text-right">Monthly rent</th><th class="text-right">Actions</th></tr></thead><tbody>' +
      items
        .map(
          (item) =>
            "<tr>" +
            '<td data-label="Property"><span class="cell-title">' + UI.escapeHtml(item.name) + "</span>" +
            (item.notes ? '<span class="cell-sub">' + UI.escapeHtml(item.notes.slice(0, 46)) + "</span>" : "") + "</td>" +
            '<td data-label="Type"><span class="badge badge-info">' + UI.escapeHtml(item.type) + "</span></td>" +
            '<td data-label="Address">' + UI.escapeHtml(item.address || "—") + "</td>" +
            '<td data-label="Status"><span class="badge ' + (item.status === "Occupied" ? "badge-success" : "badge-muted") + '">' +
              UI.escapeHtml(item.status) + "</span></td>" +
            '<td class="text-right num" data-label="Monthly rent">' + UI.money(item.monthly_rent) + "</td>" +
            '<td data-label="Actions"><div class="cell-actions">' +
              '<button class="btn btn-ghost btn-sm" data-edit="' + item.id + '">Edit</button>' +
              '<button class="btn btn-danger btn-sm" data-delete="' + item.id + '">Delete</button>' +
            "</div></td></tr>"
        )
        .join("") +
      "</tbody></table>";

    container.querySelectorAll("[data-edit]").forEach((button) =>
      button.addEventListener("click", () => openForm(button.dataset.edit))
    );
    container.querySelectorAll("[data-delete]").forEach((button) =>
      button.addEventListener("click", () => remove(button.dataset.delete))
    );
  }

  
function openForm(id) {
    const form = document.getElementById("propertyForm");
    form.reset();
    document.getElementById("propertyId").value = "";
    document.getElementById("propertyModalTitle").textContent = id ? "Edit property" : "New property";

    if (id) {
      const item = state.items.find((row) => row.id === id);
      if (!item) return UI.toast("Property not found. Refresh the page.", "error");
      document.getElementById("propertyId").value = item.id;
      document.getElementById("propertyName").value = item.name || "";
      document.getElementById("propertyType").value = item.type || "Apartment";
      document.getElementById("propertyAddress").value = item.address || "";
      document.getElementById("propertyRent").value = item.monthly_rent || 0;
      document.getElementById("propertyStatus").value = item.status || "Vacant";
      document.getElementById("propertyNotes").value = item.notes || "";
    }
    UI.openModal("propertyModal");
  }

  async function save(event) {
    event.preventDefault();
    const button = document.getElementById("propertySubmit");
    const id = document.getElementById("propertyId").value;

    const payload = {
      name: document.getElementById("propertyName").value.trim(),
      type: document.getElementById("propertyType").value,
      address: document.getElementById("propertyAddress").value.trim() || null,
      monthly_rent: parseFloat(document.getElementById("propertyRent").value || "0"),
      status: document.getElementById("propertyStatus").value,
      notes: document.getElementById("propertyNotes").value.trim() || null,
    };

    if (payload.name.length < 2) return UI.toast("Property name must be at least 2 characters.", "error");
    if (Number.isNaN(payload.monthly_rent) || payload.monthly_rent < 0) {
      return UI.toast("Monthly rent must be a positive number.", "error");
    }

    UI.setButtonLoading(button, true);
    try {
      if (id) await API.put("/api/properties/" + id, payload);
      else await API.post("/api/properties", payload);
      UI.toast(id ? "Property updated." : "Property added.", "success");
      UI.closeModal("propertyModal");
      load();
    } catch (error) {
      UI.toast(error.message, "error");
    } finally {
      UI.setButtonLoading(button, false);
    }
  }

  async function remove(id) {
    const item = state.items.find((row) => row.id === id);
    const name = item ? item.name : "this property";
    if (!UI.confirmAction('Delete "' + name + '"? This cannot be undone.')) return;

    try {
      await API.del("/api/properties/" + id);
      UI.toast("Property deleted.", "success");
      load();
    } catch (error) {
      UI.toast(error.message, "error");
    }
  }
})();
