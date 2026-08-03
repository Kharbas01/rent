/* RentFlow service worker.
 * Strategy:
 *  - App shell (CSS/JS/icons/manifest) -> precached, served cache-first, refreshed in background.
 *  - HTML page navigations         -> network-first, falling back to cache, then offline.html.
 *  - GET /api/* requests           -> network-first, falling back to the last good cached response
 *                                     (so lists/dashboards still render offline, read-only).
 *  - Non-GET /api/* requests       -> never cached; if the network is down they are queued via
 *                                     Background Sync so they retry automatically once back online.
 */

const VERSION = "v1";
const STATIC_CACHE = `rentflow-static-${VERSION}`;
const RUNTIME_CACHE = `rentflow-runtime-${VERSION}`;
const API_CACHE = `rentflow-api-${VERSION}`;
const OFFLINE_URL = "/static/offline.html";

const PRECACHE_URLS = [
  "/static/css/style.css",
  "/static/js/api.js",
  "/static/js/ui.js",
  "/static/js/theme.js",
  "/static/js/layout.js",
  "/static/js/pwa.js",
  "/static/favicon.svg",
  "/static/manifest.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  OFFLINE_URL,
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  const keep = new Set([STATIC_CACHE, RUNTIME_CACHE, API_CACHE]);
  event.waitUntil(
    caches
      .keys()
      .then((names) => Promise.all(names.filter((n) => !keep.has(n)).map((n) => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

/* Allow the page to trigger an immediate update (see pwa.js "Update available" banner). */
self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") self.skipWaiting();
});

function isNavigation(request) {
  return request.mode === "navigate" || (request.method === "GET" && request.headers.get("accept")?.includes("text/html"));
}

function isStaticAsset(url) {
  return url.pathname.startsWith("/static/");
}

function isApiRequest(url) {
  return url.pathname.startsWith("/api/");
}

async function networkFirstPage(request) {
  try {
    const response = await fetch(request);
    const cache = await caches.open(RUNTIME_CACHE);
    cache.put(request, response.clone());
    return response;
  } catch (err) {
    const cached = await caches.match(request);
    return cached || (await caches.match(OFFLINE_URL));
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(STATIC_CACHE);
  const cached = await cache.match(request);
  const fetchPromise = fetch(request)
    .then((response) => {
      if (response && response.ok) cache.put(request, response.clone());
      return response;
    })
    .catch(() => cached);
  return cached || fetchPromise;
}

async function networkFirstApi(request) {
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      const cache = await caches.open(API_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;
    return new Response(
      JSON.stringify({ detail: "You're offline. This data was not cached yet." }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    );
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (url.origin !== self.location.origin) return;

  if (isNavigation(request)) {
    event.respondWith(networkFirstPage(request));
    return;
  }

  if (isApiRequest(url)) {
    if (request.method === "GET") {
      event.respondWith(networkFirstApi(request));
    }
    // Non-GET API calls fall through to the network untouched; pwa.js
    // queues failed writes itself and retries them (see queueFailedRequest).
    return;
  }

  if (isStaticAsset(url)) {
    event.respondWith(staleWhileRevalidate(request));
  }
});

/* ---------------- Background Sync (push-ready architecture) ---------------- */
self.addEventListener("sync", (event) => {
  if (event.tag === "rentflow-retry-writes") {
    event.waitUntil(replayQueuedWrites());
  }
});

async function replayQueuedWrites() {
  const clientsList = await self.clients.matchAll();
  clientsList.forEach((client) => client.postMessage({ type: "RETRY_QUEUED_WRITES" }));
}

/* Placeholder push handler so notifications can be enabled later without
 * further service-worker changes (push-ready architecture). */
self.addEventListener("push", (event) => {
  if (!event.data) return;
  let payload = {};
  try { payload = event.data.json(); } catch (err) { payload = { title: "RentFlow", body: event.data.text() }; }
  event.waitUntil(
    self.registration.showNotification(payload.title || "RentFlow", {
      body: payload.body || "",
      icon: "/static/icons/icon-192.png",
      badge: "/static/icons/icon-192.png",
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow(event.notification.data?.url || "/"));
});
