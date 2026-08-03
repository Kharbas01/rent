/* Applies the saved theme before paint to avoid a flash of the wrong theme. */
(function () {
  const STORAGE_KEY = "rms-theme";

  function systemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function resolve(choice) {
    return choice === "system" || !choice ? systemTheme() : choice;
  }

  function apply(choice) {
    document.documentElement.setAttribute("data-theme", resolve(choice));
  }

  const saved = localStorage.getItem(STORAGE_KEY) || "system";
  apply(saved);

  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if ((localStorage.getItem(STORAGE_KEY) || "system") === "system") apply("system");
  });

  window.Theme = {
    STORAGE_KEY,
    get() {
      return localStorage.getItem(STORAGE_KEY) || "system";
    },
    set(choice) {
      localStorage.setItem(STORAGE_KEY, choice);
      apply(choice);
      document.dispatchEvent(new CustomEvent("themechange", { detail: choice }));
    },
    toggle() {
      const current = document.documentElement.getAttribute("data-theme");
      this.set(current === "dark" ? "light" : "dark");
    },
  };
})();
