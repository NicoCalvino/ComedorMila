self.addEventListener('install', (e) => {
  console.log('[Service Worker] Instalado');
});

self.addEventListener('fetch', (e) => {
  // Aquí es donde en el futuro podrías configurar el modo offline
  e.respondWith(fetch(e.request));
})