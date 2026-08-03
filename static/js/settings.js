/* Settings: profile, currency, theme selection and password change. */
(function () {
  document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("profileForm").addEventListener("submit", saveProfile);
    document.getElementById("passwordForm").addEventListener("submit", savePassword);

    const options = document.getElementById("themeOptions");
    options.addEventListener("click", (event) => {
      const button = event.target.closest("[data-theme-choice]");
      if (!button) return;
      window.Theme.set(button.dataset.themeChoice);
      markActiveTheme();
      UI.toast("Theme updated.", "success");
    });

    markActiveTheme();
    document.addEventListener("profileready", loadProfile, { once: true });
  });

  function markActiveTheme() {
    const current = window.Theme.get();
    document.querySelectorAll("[data-theme-choice]").forEach((button) => {
      button.classList.toggle("active", button.dataset.themeChoice === current);
    });
  }

  async function loadProfile() {
    try {
      const profile = await API.get("/api/settings/profile");
      document.getElementById("profileName").value = profile.full_name || "";
      document.getElementById("profileCompany").value = profile.company_name || "";
      document.getElementById("profilePhone").value = profile.phone || "";
      document.getElementById("profileCurrency").value = profile.currency || "INR";
      UI.setCurrency(profile.currency || "INR");
    } catch (error) {
      UI.toast(error.message, "error");
    }
  }

  async function saveProfile(event) {
    event.preventDefault();
    const button = document.getElementById("profileSubmit");
    const payload = {
      full_name: document.getElementById("profileName").value.trim() || null,
      company_name: document.getElementById("profileCompany").value.trim() || null,
      phone: document.getElementById("profilePhone").value.trim() || null,
      currency: document.getElementById("profileCurrency").value,
    };

    UI.setButtonLoading(button, true);
    try {
      const saved = await API.put("/api/settings/profile", payload);
      UI.setCurrency(saved.currency);
      const nameEl = document.getElementById("sidebarName");
      const avatarEl = document.getElementById("sidebarAvatar");
      if (nameEl) nameEl.textContent = saved.full_name || "";
      if (avatarEl) avatarEl.textContent = UI.initials(saved.full_name);
      UI.toast("Profile saved.", "success");
    } catch (error) {
      UI.toast(error.message, "error");
    } finally {
      UI.setButtonLoading(button, false);
    }
  }

  async function savePassword(event) {
    event.preventDefault();
    const button = document.getElementById("passwordSubmit");
    const newPassword = document.getElementById("newPassword").value;
    const confirmPassword = document.getElementById("confirmPassword").value;

    if (newPassword.length < 6) return UI.toast("Password must be at least 6 characters.", "error");
    if (newPassword !== confirmPassword) return UI.toast("Passwords do not match.", "error");

    UI.setButtonLoading(button, true);
    try {
      const result = await API.put("/api/settings/password", { new_password: newPassword });
      UI.toast(result.message, "success");
      document.getElementById("passwordForm").reset();
    } catch (error) {
      UI.toast(error.message, "error");
    } finally {
      UI.setButtonLoading(button, false);
    }
  }
})();
