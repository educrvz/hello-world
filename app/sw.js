var CACHE_NAME = 'sos-antiveneno-v18';
var ASSETS = [
    './',
    './index.html',
    './hospitals.json',
    './manifest.json',
    './privacy.html',
    './terms.html',
    './icons/icon-192.svg',
    './icons/icon-512.svg',
    './og-image.png'
];

function putIfOk(request, response) {
    if (!response || !response.ok) return response;
    var clone = response.clone();
    caches.open(CACHE_NAME).then(function(cache) {
        cache.put(request, clone);
    });
    return response;
}

function fallbackFor(request) {
    var url = new URL(request.url);
    if (url.pathname.endsWith('/privacy') || url.pathname.endsWith('/privacy.html')) {
        return caches.match('./privacy.html');
    }
    if (url.pathname.endsWith('/terms') || url.pathname.endsWith('/terms.html')) {
        return caches.match('./terms.html');
    }
    if (request.mode === 'navigate') {
        return caches.match('./index.html');
    }
    return caches.match(request);
}

function networkFirst(request) {
    return fetch(request)
        .then(function(resp) { return putIfOk(request, resp); })
        .catch(function() { return fallbackFor(request); });
}

function cacheFirst(request) {
    return caches.match(request).then(function(cached) {
        if (cached) return cached;
        return fetch(request).then(function(resp) {
            return putIfOk(request, resp);
        });
    });
}

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

    if (event.request.method !== 'GET') return;

    if (url.origin !== self.location.origin) {
        event.respondWith(fetch(event.request).catch(function() {
            return caches.match(event.request);
        }));
        return;
    }

    if (url.pathname.endsWith('hospitals.json')) {
        // Network-first for data (allows updates)
        event.respondWith(networkFirst(event.request));
    } else if (event.request.mode === 'navigate' ||
            url.pathname.endsWith('/index.html') ||
            url.pathname.endsWith('/privacy') ||
            url.pathname.endsWith('/privacy.html') ||
            url.pathname.endsWith('/terms') ||
            url.pathname.endsWith('/terms.html')) {
        // Network-first for HTML avoids stale app shells after deploys.
        event.respondWith(networkFirst(event.request));
    } else {
        // Cache-first for local static assets.
        event.respondWith(cacheFirst(event.request));
    }
});
