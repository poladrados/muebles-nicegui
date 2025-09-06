const CACHE = 'eljueves-v7';   // <-- bump
const PRECACHE = [
  // ¡OJO! No cacheamos '/' ni HTML para evitar instalaciones con HTML antiguo
  '/manifest.webmanifest',
  '/muebles-app/images/icon-192.png',
  '/muebles-app/images/icon-512.png',
  '/muebles-app/images/maskable-192.png',
  '/muebles-app/images/maskable-512.png',
  '/muebles-app/images/apple-touch-icon.png',
  '/apple-touch-icon.png',
  '/favicon.ico'
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(cache => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(self.clients.claim().then(async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)));
  }));
});

self.addEventListener('fetch', e => {
  const request = e.request;

  // Navegaciones (HTML): SIEMPRE red a red, sin cache
  if (request.mode === 'navigate') {
    e.respondWith(fetch(request));
    return;
  }

  if (request.method !== 'GET') return;

  // Cache First para imágenes/icons; Network First para el resto
  if (request.url.includes('/img/') || request.url.includes('/muebles-app/')) {
    e.respondWith(
      caches.match(request).then(cached => {
        return cached || fetch(request).then(response => {
          if (!response || response.status !== 200 || response.type === 'opaque') return response;
          const copy = response.clone();
          caches.open(CACHE).then(cache => cache.put(request, copy));
          return response;
        });
      })
    );
  } else {
    e.respondWith(fetch(request).catch(() => caches.match(request)));
  }
});

