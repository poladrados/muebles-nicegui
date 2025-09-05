const CACHE='eljueves-v3';
const PRECACHE=[
  '/', '/?source=pwa',
  '/muebles-app/manifest.json',
  '/muebles-app/images/icon-192.png',
  '/muebles-app/images/icon-512.png',
  '/muebles-app/images/maskable-192.png',
  '/muebles-app/images/maskable-512.png',
  '/muebles-app/images/apple-touch-icon.png', // correcto
  '/apple-touch-icon.png'                      // alias raíz
];

self.addEventListener('install',e=>{
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(PRECACHE)));
  self.skipWaiting();
});
self.addEventListener('activate',e=>{
  e.waitUntil(self.clients.claim().then(async()=>{
    const keys=await caches.keys();
    await Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)));
  }));
});
self.addEventListener('fetch',e=>{
  const r=e.request;
  if (r.method!=='GET') return;
  if (r.destination==='image'){
    e.respondWith(caches.match(r).then(m=>m||fetch(r).then(resp=>{
      const cp=resp.clone(); caches.open(CACHE).then(c=>c.put(r,cp)); return resp;
    })));
    return;
  }
  e.respondWith(fetch(r).catch(()=>caches.match(r)));
});

