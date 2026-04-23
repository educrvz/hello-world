var CACHE_NAME = 'sos-antiveneno-v5';
var ASSETS = [
    './',
    './index.html',
    './hospitals.json',
    './manifest.json'
];

self.addEventListener('install', function(event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(function(cache) {
            return cache.addAll(ASSETS);
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', function(event) {
    event.waitUntil(
        caches.keys().then(function(keys) {
            return Promise.all(
                keys.filter(function(k) { return k !== CACHE_NAME; })
                    .map(function(k) { return caches.delete(k); })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', function(event) {
    var url = new URL(event.request.url);

    if (url.pathname.endsWith('hospitals.json')) {
        // Network-first for data (allows updates)
        event.respondWith(
            fetch(event.request).then(function(resp) {
                var clone = resp.clone();
                caches.open(CACHE_NAME).then(function(cache) {
                    cache.put(event.request, clone);
                });
                return resp;
            }).catch(function() {
                return caches.match(event.request);
            })
        );
    } else {
        // Cache-first for everything else
        event.respondWith(
            caches.match(event.request).then(function(cached) {
                return cached || fetch(event.request);
            })
        );
    }
});
