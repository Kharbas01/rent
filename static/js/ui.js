/* Shared UI helpers: toasts, modals, formatting, loading states. */
(function () {
  const CURRENCY_SYMBOLS = {
    INR: "₹", USD: "$", EUR: "€", GBP: "£", AED: "د.إ", PKR: "₨",
  };

  const state = { currency: localStorage.getItem("rms-currency") || "INR" };

  /* ---------------- Formatting ---------------- */
  function setCurrency(code) {
    if (!code) return;
    state.currency = code;
    localStorage.setItem("rms-currency", code);
  }

  function currencySymbol() {
    return CURRENCY_SYMBOLS[state.currency] || state.currency + " ";
  }

  function money(value) {
    const amount = Number(value || 0);
    const locale = state.currency === "INR" ? "en-IN" : "en-US";
    return (
      currencySymbol() +
      " " +
      amount.toLocaleString(locale, { minimumFractionDigits: 0, maximumFractionDigits: 2 })
    );
  }

  function compactMoney(value) {
    const amount = Number(value || 0);
    if (amount >= 10000000) return currencySymbol() + " " + (amount / 10000000).toFixed(2) + " Cr";
    if (amount >= 100000) return currencySymbol() + " " + (amount / 100000).toFixed(2) + " L";
    return money(amount);
  }

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value + (value.length === 10 ? "T00:00:00" : ""));
    if (Number.isNaN(date.getTime())) return "—";
    return date.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
  }

  function formatMonth(value) {
    if (!value) return "—";
    const date = new Date(String(value).slice(0, 7) + "-01T00:00:00");
    if (Number.isNaN(date.getTime())) return "—";
    return date.toLocaleDateString(undefined, { month: "short", year: "numeric" });
  }

  function monthInputValue(offset) {
    const now = new Date();
    now.setDate(1);
    now.setMonth(now.getMonth() + (offset || 0));
    return now.toISOString().slice(0, 7);
  }

  function todayInputValue() {
    const now = new Date();
    return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  }

  function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  }

  function initials(name) {
    if (!name) return "U";
    return name.trim().split(/\s+/).slice(0, 2).map((p) => p[0].toUpperCase()).join("");
  }

  function debounce(fn, delay) {
    let timer;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), delay || 300);
    };
  }

  /* ---------------- Toasts ---------------- */
  function toast(message, type, title) {
    const stack = document.getElementById("toast-stack");
    if (!stack) return alert(message);

    const titles = { success: "Success", error: "Something went wrong", info: "Notice" };
    const kind = type || "info";
    const el = document.createElement("div");
    el.className = "toast " + kind;
    el.innerHTML =
      '<div><strong>' + escapeHtml(title || titles[kind] || "Notice") + "</strong>" +
      "<span>" + escapeHtml(message) + "</span></div>";
    stack.appendChild(el);

    setTimeout(() => {
      el.classList.add("hide");
      setTimeout(() => el.remove(), 300);
    }, kind === "error" ? 5200 : 3400);
  }

  /* ---------------- Modals ---------------- */
  function openModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.hidden = false;
    document.body.style.overflow = "hidden";
    const focusable = modal.querySelector("input:not([type=hidden]), select, textarea");
    if (focusable) setTimeout(() => focusable.focus(), 60);
  }

  function closeModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.hidden = true;
    document.body.style.overflow = "";
  }

  function bindModalClose(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.querySelectorAll("[data-close]").forEach((el) =>
      el.addEventListener("click", () => closeModal(id))
    );
  }

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    document.querySelectorAll(".modal:not([hidden])").forEach((modal) => closeModal(modal.id));
  });

  /* ---------------- Loading / states ---------------- */
  function setButtonLoading(button, loading) {
    if (!button) return;
    const label = button.querySelector(".btn-label");
    const spinner = button.querySelector(".spinner");
    button.disabled = !!loading;
    if (label) label.style.opacity = loading ? "0.65" : "1";
    if (spinner) spinner.hidden = !loading;
  }

  function showLoader(container) {
    if (container) container.innerHTML = '<div class="loader-block"><span class="spinner"></span></div>';
  }

  function emptyState(container, options) {
    if (!container) return;
    const opts = options || {};
    container.innerHTML =
      '<div class="empty-state">' +
      '<div class="empty-icon">' + (opts.icon || "&#128193;") + "</div>" +
      "<h3>" + escapeHtml(opts.title || "Nothing here yet") + "</h3>" +
      "<p>" + escapeHtml(opts.message || "Once you add data it will appear here.") + "</p>" +
      (opts.actionId && opts.actionLabel
        ? '<button class="btn btn-primary" id="' + opts.actionId + '">' +
          escapeHtml(opts.actionLabel) + "</button>"
        : "") +
      "</div>";
  }

  function confirmAction(message) {
    return window.confirm(message);
  }

  window.UI = {
    setCurrency, currencySymbol, money, compactMoney, formatDate, formatMonth,
    monthInputValue, todayInputValue, escapeHtml, initials, debounce,
    toast, openModal, closeModal, bindModalClose,
    setButtonLoading, showLoader, emptyState, confirmAction,
  };
})();
