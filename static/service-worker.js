const CACHE = 'eljueves-v6';
const PRECACHE = [
  '/',
  '/?source=pwa',
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
    caches.open(CACHE)
      .then(cache => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    self.clients.claim().then(async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys.filter(k => k !== CACHE)
            .map(k => caches.delete(k))
      );
    })
  );
});

self.addEventListener('fetch', e => {
  const request = e.request;
  
  // No cachear solicitudes POST o no GET
  if (request.method !== 'GET') return;
  
  // Estrategia: Cache First para assets, Network First para datos
  if (request.url.includes('/img/') || request.url.includes('/muebles-app/')) {
    e.respondWith(
      caches.match(request).then(cached => {
        return cached || fetch(request).then(response => {
          // No cachear respuestas que no sean OK
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }
          const responseToCache = response.clone();
          caches.open(CACHE).then(cache => {
            cache.put(request, responseToCache);
          });
          return response;
        });
      })
    );
  } else {
    // Para otras solicitudes, intentar network primero
    e.respondWith(
      fetch(request).catch(() => caches.match(request))
    );
  }
});
