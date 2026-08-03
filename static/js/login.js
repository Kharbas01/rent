/* Login + signup screen logic. */
document.addEventListener("DOMContentLoaded", () => {
  const tabs = document.getElementById("authTabs");
  const loginForm = document.getElementById("loginForm");
  const signupForm = document.getElementById("signupForm");

  if (tabs) {
    tabs.addEventListener("click", (event) => {
      const tab = event.target.closest(".tab");
      if (!tab) return;
      tabs.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      const isLogin = tab.dataset.tab === "login";
      if (loginForm) loginForm.hidden = !isLogin;
      if (signupForm) signupForm.hidden = isLogin;
    });
  }

  if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = document.getElementById("loginSubmit");
      UI.setButtonLoading(button, true);
      try {
        await API.post("/api/auth/login", {
          email: document.getElementById("loginEmail").value.trim(),
          password: document.getElementById("loginPassword").value,
        });
        UI.toast("Signed in. Loading your dashboard…", "success");
        setTimeout(() => { window.location.href = "/"; }, 400);
      } catch (error) {
        UI.toast(error.message, "error");
        UI.setButtonLoading(button, false);
      }
    });
  }

  if (signupForm) {
    signupForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = document.getElementById("signupSubmit");
      UI.setButtonLoading(button, true);
      try {
        const result = await API.post("/api/auth/signup", {
          full_name: document.getElementById("signupName").value.trim(),
          email: document.getElementById("signupEmail").value.trim(),
          password: document.getElementById("signupPassword").value,
        });
        UI.toast(result.message || "Account created. Please sign in.", "success", "Account created");
        signupForm.reset();
        const loginTab = document.querySelector('.tab[data-tab="login"]');
        if (loginTab) loginTab.click();
      } catch (error) {
        UI.toast(error.message, "error");
      } finally {
        UI.setButtonLoading(button, false);
      }
    });
  }
});