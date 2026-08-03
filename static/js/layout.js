/* Shared shell behaviour: sidebar, theme toggle, profile chip, global search. */
(function () {
  document.addEventListener("DOMContentLoaded", () => {
    initSidebar();
    initThemeToggle();
    initLogout();
    initProfileChip();
    initGlobalSearch();
  });

  function initSidebar() {
    const sidebar = document.getElementById("sidebar");
    const backdrop = document.getElementById("sidebarBackdrop");
    const openBtn = document.getElementById("menuBtn");
    const closeBtn = document.getElementById("sidebarClose");
    if (!sidebar) return;

    const open = () => { sidebar.classList.add("open"); backdrop.classList.add("show"); };
    const close = () => { sidebar.classList.remove("open"); backdrop.classList.remove("show"); };

    if (openBtn) openBtn.addEventListener("click", open);
    if (closeBtn) closeBtn.addEventListener("click", close);
    if (backdrop) backdrop.addEventListener("click", close);
    sidebar.querySelectorAll(".nav-link").forEach((link) => link.addEventListener("click", close));
  }

  function initThemeToggle() {
    const toggle = document.getElementById("themeToggle");
    if (toggle) toggle.addEventListener("click", () => window.Theme.toggle());
  }

  function initLogout() {
    const button = document.getElementById("logoutBtn");
    if (!button) return;
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await API.logout();
      } catch (error) {
        /* Ignore: we redirect either way. */
      }
      window.location.href = "/login";
    });
  }

  async function initProfileChip() {
    try {
      const me = await API.me();
      UI.setCurrency(me.currency);
      const nameEl = document.getElementById("sidebarName");
      const emailEl = document.getElementById("sidebarEmail");
      const avatarEl = document.getElementById("sidebarAvatar");
      if (nameEl) nameEl.textContent = me.full_name || me.email;
      if (emailEl) emailEl.textContent = me.email;
      if (avatarEl) avatarEl.textContent = UI.initials(me.full_name || me.email);
      document.dispatchEvent(new CustomEvent("profileready", { detail: me }));
    } catch (error) {
      document.dispatchEvent(new CustomEvent("profileready", { detail: null }));
    }
  }

  function initGlobalSearch() {
    const input = document.getElementById("globalSearch");
    const panel = document.getElementById("searchResults");
    if (!input || !panel) return;

    const run = UI.debounce(async () => {
      const term = input.value.trim();
      if (term.length < 2) { panel.hidden = true; return; }

      panel.hidden = false;
      panel.innerHTML = '<div class="loader-block"><span class="spinner spinner-sm"></span></div>';

      try {
        const data = await API.get("/api/search", { q: term });
        if (!data.total) {
          panel.innerHTML = '<div class="search-group-label">No matches</div>' +
            '<div class="search-item"><span>Nothing found for "' + UI.escapeHtml(term) + '"</span></div>';
          return;
        }

        let html = "";
        if (data.properties.length) {
          html += '<div class="search-group-label">Properties</div>';
          data.properties.forEach((p) => {
            html += '<a class="search-item" href="/properties"><div><strong>' +
              UI.escapeHtml(p.name) + "</strong><span>" +
              UI.escapeHtml(p.type || "") + (p.address ? " · " + UI.escapeHtml(p.address) : "") +
              '</span></div><span class="badge ' +
              (p.status === "Occupied" ? "badge-success" : "badge-muted") + '">' +
              UI.escapeHtml(p.status) + "</span></a>";
          });
        }
        if (data.tenants.length) {
          html += '<div class="search-group-label">Tenants</div>';
          data.tenants.forEach((t) => {
            const prop = t.properties ? t.properties.name : "No property";
            html += '<a class="search-item" href="/tenants"><div><strong>' +
              UI.escapeHtml(t.name) + "</strong><span>" +
              UI.escapeHtml(t.phone || t.email || "—") + " · " + UI.escapeHtml(prop) +
              '</span></div><span class="num">' + UI.money(t.rent_amount) + "</span></a>";
          });
        }
        panel.innerHTML = html;
      } catch (error) {
        panel.innerHTML = '<div class="search-item"><span>' + UI.escapeHtml(error.message) + "</span></div>";
      }
    }, 300);

    input.addEventListener("input", run);
    input.addEventListener("focus", () => { if (input.value.trim().length >= 2) panel.hidden = false; });
    document.addEventListener("click", (event) => {
      if (!panel.contains(event.target) && event.target !== input) panel.hidden = true;
    });
  }
})();
