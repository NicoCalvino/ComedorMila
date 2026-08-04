// Service worker mínimo del sitio.
//
// IMPORTANTE: este service worker NO debe interceptar las peticiones.
// La versión anterior hacía `e.respondWith(fetch(e.request))` para TODAS las
// peticiones. En iPhone (Safari), reenviar así un POST con multipart/form-data
// rompe el cuerpo de la petición: llega al servidor sin sus campos, incluido
// csrfmiddlewaretoken, y Django la rechaza con "CSRF token missing" (403).
// Por eso a los usuarios con la app instalada les fallaba cargar saldo / el día.
//
// Como el sitio no usa modo offline, lo más seguro es NO tocar ninguna
// petición y dejar que el navegador maneje todo de forma nativa.

self.addEventListener('install', (event) => {
  // Que esta versión nueva reemplace cuanto antes a la vieja (buggy).
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  // Tomar control de las pestañas/PWA ya abiertas sin esperar a que se cierren.
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  // No llamamos a event.respondWith(): ni los GET ni los POST se ven alterados.
  return;
});
