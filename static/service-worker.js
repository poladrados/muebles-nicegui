const CACHE='eljueves-v1';
const PRECACHE=['/','/muebles-app/manifest.json','/muebles-app/images/icon-192.png'];

self.addEventListener('install',e=>{
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(PRECACHE)));
  self.skipWaiting();
});
self.addEventListener('activate',e=>{e.waitUntil(self.clients.claim())});
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
