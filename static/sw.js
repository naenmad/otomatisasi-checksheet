const CACHE_NAME = 'qc-checksheet-v1';
const STATIC_ASSETS = [
  '/',
  '/checksheets',
  '/dashboard',
  '/style.css',
  '/manifest.webmanifest',
  '/favicon.svg',
  '/icon-192.png',
  '/icon-512.png',
  '/apple-touch-icon.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('[SW] Pre-cache warning:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // 1. Never cache non-GET requests or WebSocket connections
  if (req.method !== 'GET' || url.protocol.startsWith('ws')) {
    return;
  }

  // 2. API Data calls: Always Network-First (live data is critical for QC)
  if (url.pathname.startsWith('/api/')) {
    // Exception: Allow caching drawing thumbnails for fast offline review
    if (url.pathname.includes('/images/') || url.pathname.includes('/thumbnail')) {
      event.respondWith(
        caches.open(CACHE_NAME).then(async (cache) => {
          const cached = await cache.match(req);
          const networkPromise = fetch(req).then((networkRes) => {
            if (networkRes.ok) cache.put(req, networkRes.clone());
            return networkRes;
          }).catch(() => null);
          return cached || networkPromise || fetch(req);
        })
      );
      return;
    }

    // Default API calls: Network-only with grace
    event.respondWith(
      fetch(req).catch(() => {
        return new Response(JSON.stringify({ error: 'Offline', offline: true }), {
          headers: { 'Content-Type': 'application/json' },
          status: 503
        });
      })
    );
    return;
  }

  // 3. Navigation requests (HTML pages): Network-first with cache fallback
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const clone = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
          }
          return res;
        })
        .catch(async () => {
          const cached = await caches.match(req);
          if (cached) return cached;
          const fallback = await caches.match('/checksheets');
          return fallback || caches.match('/');
        })
    );
    return;
  }

  // 4. Static assets (CSS, JS, Fonts, Icons, CDN): Stale-While-Revalidate
  event.respondWith(
    caches.match(req).then((cachedRes) => {
      const fetchPromise = fetch(req).then((networkRes) => {
        if (networkRes.ok && req.method === 'GET') {
          const clone = networkRes.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
        }
        return networkRes;
      }).catch(() => null);

      return cachedRes || fetchPromise;
    })
  );
});
