const CACHE_NAME = "order-app-v8";
const APP_SHELL = [
  "/orders/new",
  "/static/app.css?v=20260621-4",
  "/static/css/app.css?v=20260621-4",
  "/static/css/tokens.css",
  "/static/css/base.css",
  "/static/css/layout.css",
  "/static/css/components.css",
  "/static/css/pages/orders.css",
  "/static/css/pages/orders-ledger.css",
  "/static/css/ui-refresh.css",
  "/static/css/pages/showcase.css",
  "/static/css/print.css",
  "/static/css/runtime/foundation.css",
  "/static/css/runtime/print-document.css",
  "/static/css/runtime/public-showcase.css",
  "/static/css/runtime/forms-orders.css",
  "/static/css/runtime/showcase-manage.css",
  "/static/css/runtime/responsive.css",
  "/static/css/runtime/print-responsive.css",
  "/static/js/app.js",
  "/static/mobile_ui.js?v=20260621-1",
  "/static/js/order_form.js?v=20260621-1",
  "/static/js/orders.js?v=20260621-2",
  "/static/js/voice_order.js?v=20260621-1",
  "/static/manifest.webmanifest",
  "/static/icon.svg"
];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request).then(resp => resp || caches.match("/orders/new")))
  );
});
