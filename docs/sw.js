/* Service worker: lets Tokyo Gigs open instantly and work offline.
   - App files (page, styles, script, icons): served from cache, refreshed in the background.
   - Gig listings (data/*.json): fetched fresh when online, last copy used when offline.
   Bump VERSION when app files change so phones pick up the new version. */
const VERSION = "tg-v1";
const SHELL = [
  "./", "index.html", "style.css", "app.js", "manifest.webmanifest",
  "icons/icon-192.png", "icons/icon-512.png", "icons/apple-touch-icon.png", "icons/favicon-32.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

async function networkFirst(req) {
  const cache = await caches.open(VERSION);
  try {
    const res = await fetch(req, { cache: "no-cache" });
    if (res.ok) cache.put(req, res.clone());
    return res;
  } catch (err) {
    const hit = await cache.match(req, { ignoreSearch: true });
    if (hit) {
      // tell the page it is looking at a saved copy
      const h = new Headers(hit.headers);
      h.set("X-From-Cache", "1");
      return new Response(await hit.blob(), { status: 200, headers: h });
    }
    throw err;
  }
}

async function staleWhileRevalidate(req) {
  const cache = await caches.open(VERSION);
  const hit = await cache.match(req, { ignoreSearch: req.mode === "navigate" });
  const fresh = fetch(req).then((res) => {
    if (res.ok || res.type === "opaque") cache.put(req, res.clone());
    return res;
  }).catch(() => null);
  return hit || (await fresh) || (req.mode === "navigate" ? cache.match("index.html") : Response.error());
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin === location.origin && url.pathname.includes("/data/")) {
    e.respondWith(networkFirst(req));
  } else if (url.origin === location.origin || url.host.endsWith("fonts.googleapis.com") || url.host.endsWith("fonts.gstatic.com")) {
    e.respondWith(staleWhileRevalidate(req));
  }
  // everything else (ticket sites etc.) goes straight to the network
});
