/* ---------------------------------------------------------------------------
 * JanVaani UP - offline shell service worker.
 *
 * Caches the app shell so the PWA opens instantly (and works on a flaky rural
 * connection). API calls are network-first with a cache fallback, except for the
 * health endpoint which is served from cache when offline.
 * ------------------------------------------------------------------------- */

const SHELL_CACHE = "janvaani-shell-v1";
const RUNTIME_CACHE = "janvaani-runtime-v1";

const SHELL_ASSETS = ["/", "/index.html", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_ASSETS))
      .catch(() => undefined)
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== SHELL_CACHE && key !== RUNTIME_CACHE)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // API: network first, fall back to the last cached response.
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(RUNTIME_CACHE).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() =>
          caches.match(request).then(
            (cached) =>
              cached ||
              new Response(
                JSON.stringify({
                  ok: false,
                  error: { code: "offline", message: "इंटरनेट नहीं है। कृपया फिर से कोशिश करें।" },
                }),
                { status: 503, headers: { "Content-Type": "application/json" } },
              ),
          ),
        ),
    );
    return;
  }

  // Navigations: serve the cached shell when offline.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match("/index.html").then((cached) => cached || Response.error())),
    );
    return;
  }

  // Static assets: cache first.
  event.respondWith(
    caches.match(request).then(
      (cached) =>
        cached ||
        fetch(request).then((response) => {
          const copy = response.clone();
          caches.open(RUNTIME_CACHE).then((cache) => cache.put(request, copy));
          return response;
        }),
    ),
  );
});
