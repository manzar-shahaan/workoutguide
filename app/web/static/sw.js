// app/web/static/sw.js
//
// Minimal service worker: exists so Chrome/Android treat the app as
// installable. It only caches the static app shell (icons, manifest, JS).
// HTML and API responses are never cached here — the app already sends
// no-store headers on every page because workout data is per-user and
// changes constantly, and this worker respects that.

const CACHE_NAME = "shell-v6";
const SHELL_ASSETS = [
  "/static/manifest.webmanifest",
  "/static/js/main.js",
  "/static/js/stats.js",
  "/static/js/home.js",
  "/static/js/region-picker.js",
  "/static/js/body-map-render.js",
  "/static/js/body-map-data.js",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  const isShellAsset =
    event.request.method === "GET" &&
    url.origin === self.location.origin &&
    SHELL_ASSETS.includes(url.pathname);

  if (!isShellAsset) return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        return response;
      });
    })
  );
});
