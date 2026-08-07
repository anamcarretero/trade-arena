const CACHE = "tradearena-shell-v4";
const OFFLINE_URL = "/offline";
self.addEventListener("install", event => event.waitUntil(
  caches.open(CACHE).then(cache => cache.addAll([OFFLINE_URL, "/icon.svg"])).then(() => self.skipWaiting())
));
self.addEventListener("activate", event => event.waitUntil(
  caches.keys()
    .then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key))))
    .then(() => self.clients.claim())
));
self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || event.request.mode !== "navigate" ||
      url.origin !== self.location.origin ||
      url.pathname.startsWith("/auth/") || url.pathname === "/language") return;
  event.respondWith((async () => {
    try {
      return await fetch(event.request);
    } catch {
      const fallback = await caches.match(OFFLINE_URL, {ignoreSearch: true}).catch(() => undefined);
      if (fallback) return fallback;
      return new Response("TradeArena no está disponible temporalmente. TradeArena is temporarily unavailable.", {
        status: 503,
        headers: {"Content-Type": "text/plain; charset=utf-8", "Retry-After": "5"}
      });
    }
  })());
});
