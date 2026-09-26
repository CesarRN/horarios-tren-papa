const CACHE = "horarios-tren-v1";
const ARCHIVOS = ["./", "./index.html", "./manifest.json", "./icon-192.png", "./icon-512.png"];

self.addEventListener("install", (evento) => {
  evento.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ARCHIVOS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches.keys().then((claves) =>
      Promise.all(claves.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (evento) => {
  const url = new URL(evento.request.url);

  // Los horarios: siempre intentar red primero (para tener el dato más fresco),
  // y si no hay conexión, servir la última copia guardada.
  if (url.pathname.endsWith("data/horarios.json")) {
    evento.respondWith(
      fetch(evento.request)
        .then((resp) => {
          const copia = resp.clone();
          caches.open(CACHE).then((cache) => cache.put(evento.request, copia));
          return resp;
        })
        .catch(() => caches.match(evento.request))
    );
    return;
  }

  // El resto de archivos: caché primero, con red de respaldo.
  evento.respondWith(
    caches.match(evento.request).then((resp) => resp || fetch(evento.request))
  );
});
