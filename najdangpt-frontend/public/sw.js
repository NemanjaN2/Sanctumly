const CACHE_NAME = 'najdangpt-v1';
const urlsToCache = [
  '/',
  '/index.html',
  '/logo.png',
  '/180.png',
  '/120.png',
  '/1024.png',
  '/manifest.json'
];

// Install service worker and cache assets
self.addEventListener('install', (event) => {
  console.log('Service Worker installing...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate and clean old caches
self.addEventListener('activate', (event) => {
  console.log('Service Worker activating...');
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheWhitelist.indexOf(cacheName) === -1) {
              console.log('Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => self.clients.claim())
  );
});

// Fetch strategy: Cache first, fallback to network
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Cache hit - return response
        if (response) {
          return response;
        }
        
        // Clone the request
        const fetchRequest = event.request.clone();
        
        return fetch(fetchRequest).then((response) => {
          // Check if valid response
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }
          
          // Clone the response
          const responseToCache = response.clone();
          
          // Cache the fetched response for future use
          caches.open(CACHE_NAME)
            .then((cache) => {
              cache.put(event.request, responseToCache);
            });
          
          return response;
        });
      })
      .catch(() => {
        // If both cache and network fail, show offline page (optional)
        return caches.match('/');
      })
  );
});

// Handle background sync (Android only)
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-messages') {
    console.log('Background sync triggered');
    // Add your sync logic here
  }
});

// Handle push notifications (Android only)
self.addEventListener('push', (event) => {
  const options = {
    body: event.data ? event.data.text() : 'New message from NajdanGPT',
    icon: '/180.png',
    badge: '/logo.png',
    vibrate: [200, 100, 200],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    }
  };
  
  event.waitUntil(
    self.registration.showNotification('NajdanGPT', options)
  );
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
  console.log('Notification click received');
  event.notification.close();
  
  event.waitUntil(
    clients.openWindow('/')
  );
});
