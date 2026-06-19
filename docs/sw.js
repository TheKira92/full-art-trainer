// Service worker per Full Art Trainer (PWA)
// Generato da gen_tracker.py — modifica liberamente se vuoi, NON viene
// sovrascritto: per rigenerarlo cancella questo file e rilancia.
const CACHE_VERSION = 'v1';
const STATIC_CACHE  = 'fa-trainer-static-' + CACHE_VERSION;
const IMG_CACHE     = 'fa-trainer-img-'    + CACHE_VERSION;

// File same-origin da precachare (relativi allo scope del SW).
const PRECACHE_URLS = ["./", "./index.html", "./manifest.webmanifest", "./icons/icon-192.png", "./icons/icon-512.png", "./icons/icon-maskable-512.png"];

// Host del CDN immagini di Limitless (cross-origin → opaque response).
const IMG_HOST = 'limitlesstcg.nyc3.cdn.digitaloceanspaces.com';

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(STATIC_CACHE);
    // addAll fallisce in blocco se uno solo dei file manca: facciamo
    // i put uno alla volta in modo tollerante.
    await Promise.all(PRECACHE_URLS.map(async (url) => {
      try {
        const res = await fetch(url, { cache: 'reload' });
        if (res.ok || res.type === 'opaque') await cache.put(url, res.clone());
      } catch (_) { /* ignora: il file potrà essere recuperato a runtime */ }
    }));
    self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keep = new Set([STATIC_CACHE, IMG_CACHE]);
    for (const name of await caches.keys()) {
      if (!keep.has(name)) await caches.delete(name);
    }
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // 1) immagini del CDN Limitless → stale-while-revalidate (no-cors / opaque)
  if (url.host === IMG_HOST) {
    event.respondWith(staleWhileRevalidate(req, IMG_CACHE));
    return;
  }

  // 2) same-origin → cache-first con fallback rete (e fallback all'HTML
  //    radice per le navigation request, così offline non muore tutto)
  if (url.origin === self.location.origin) {
    event.respondWith(cacheFirst(req, STATIC_CACHE));
    return;
  }

  // 3) altro: bypass
});

async function cacheFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(req, { ignoreSearch: false });
  if (hit) return hit;
  try {
    const res = await fetch(req);
    if (res.ok) cache.put(req, res.clone());
    return res;
  } catch (err) {
    if (req.mode === 'navigate') {
      const fallback = await cache.match("./index.html");
      if (fallback) return fallback;
    }
    throw err;
  }
}

async function staleWhileRevalidate(req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  // Per il CDN cross-origin usiamo no-cors: la response sarà 'opaque'
  // (status 0) ma può comunque essere messa in cache e servita.
  const fetchReq = new Request(req.url, { mode: 'no-cors', credentials: 'omit' });
  const network = fetch(fetchReq).then((res) => {
    if (res && (res.ok || res.type === 'opaque')) {
      cache.put(req, res.clone()).catch(() => {});
    }
    return res;
  }).catch(() => null);
  return cached || (await network) || Response.error();
}
