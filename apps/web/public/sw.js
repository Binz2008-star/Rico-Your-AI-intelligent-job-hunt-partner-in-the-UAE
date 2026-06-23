// Rico Hunt PWA Service Worker
const CACHE_NAME = "rico-hunt-v1";

// Assets to cache on install (app shell)
const PRECACHE_ASSETS = [
  "/",
  "/command",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/apple-touch-icon.png",
];

// Offline fallback page (served from cache if network fails)
const OFFLINE_URL = "/command";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS).catch(() => {
        // If precaching fails (e.g., offline install), continue anyway
      });
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  // Remove old caches from previous SW versions
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;

  // Only handle GET requests and same-origin/static assets
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Skip non-http(s) requests and API/proxy calls
  if (!url.protocol.startsWith("http")) return;
  if (url.pathname.startsWith("/proxy/") || url.pathname.startsWith("/api/")) return;

  // Static assets: cache-first
  if (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/icons/") ||
    url.pathname.endsWith(".png") ||
    url.pathname.endsWith(".svg") ||
    url.pathname.endsWith(".ico") ||
    url.pathname.endsWith(".webp")
  ) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // Navigation requests: network-first, fallback to cache then offline page
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() =>
          caches
            .match(request)
            .then((cached) => cached || caches.match(OFFLINE_URL))
        )
    );
  }
});
