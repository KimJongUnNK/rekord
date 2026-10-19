// App-shell cache: the UI opens instantly, even before the hub answers. API calls always go to the network.
const CACHE = "rekord-shell-v4";
const SHELL = ["/", "/static/app.css", "/static/app.js", "/static/md.js", "/manifest.webmanifest", "/icons/icon-192.png"];
self.addEventListener("install", (e) => e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener("activate", (e) => e.waitUntil(
  caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.pathname.startsWith("/api") || u.pathname.startsWith("/ws")) return;
  e.respondWith(fetch(e.request).then((r) => {
    if (r.ok && (SHELL.includes(u.pathname) || u.pathname.startsWith("/static/"))) {
      const copy = r.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy));
    }
    return r;
  }).catch(() => caches.match(e.request).then((m) => m || caches.match("/"))));
});
