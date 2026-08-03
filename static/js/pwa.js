/* PWA install, update-detection and offline/online UX. Loaded on every page. */
(function () {
  let deferredPrompt = null;
  let refreshing = false;

  function isStandalone() {
    return (
      window.matchMedia("(display-mode: standalone)").matches ||
      window.matchMedia("(display-mode: window-controls-overlay)").matches ||
      window.navigator.standalone === true // iOS Safari
    );
  }

  function ensureBanner(id) {
    let el = document.getElementById(id);
    if (el) return el;
    el = document.createElement("div");
    el.id = id;
    el.className = "pwa-banner";
    el.hidden = true;
    document.body.appendChild(el);
    return el;
  }

  /* Install-prompt banner intentionally removed — the browser's native
     install affordance (address-bar icon / browser menu) is still fully
     available; we just suppress our own custom banner UI. We still swallow
     the event via preventDefault-less no-op below so the browser doesn't
     show its own mini-infobar unexpectedly on some platforms. */

  /* ---------------- Service worker + update flow ---------------- */
  function setupServiceWorker() {
    if (!("serviceWorker" in navigator)) return;

    window.addEventListener("load", async () => {
      try {
        const registration = await navigator.serviceWorker.register("/service-worker.js", { scope: "/" });

        registration.addEventListener("updatefound", () => {
          const installing = registration.installing;
          if (!installing) return;
          installing.addEventListener("statechange", () => {
            if (installing.state === "installed" && navigator.serviceWorker.controller) {
              showUpdateBanner(registration);
            }
          });
        });

        // Check for a newer service worker once per load.
        registration.update().catch(() => {});
      } catch (err) {
        // Registration can fail (e.g. unsupported browser); the app still works online.
      }
    });

    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (refreshing) return;
      refreshing = true;
      window.location.reload();
    });
  }

  function showUpdateBanner(registration) {
    const banner = ensureBanner("pwaUpdateBanner");
    banner.hidden = false;
    banner.innerHTML =
      '<p>A new version of RentFlow is available.</p>' +
      '<button type="button" class="btn btn-primary btn-sm" id="pwaUpdateBtn">Update now</button>';
    document.getElementById("pwaUpdateBtn").addEventListener("click", () => {
      if (registration.waiting) registration.waiting.postMessage("SKIP_WAITING");
      banner.hidden = true;
    });
  }

  /* ---------------- Online / offline status ---------------- */
  function setupConnectivity() {
    window.addEventListener("offline", () => {
      if (window.UI) UI.toast("You're offline. Showing the last data that was loaded.", "info", "Offline");
    });
    window.addEventListener("online", () => {
      if (window.UI) UI.toast("Back online.", "success");
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    setupServiceWorker();
    setupConnectivity();
  });
})();
