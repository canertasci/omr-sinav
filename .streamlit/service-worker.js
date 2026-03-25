// OMR PWA Service Worker
// Offline mode, caching, background sync

const CACHE_NAME = "omr-tarama-v1";
const urlsToCache = [
  "/",
  "/pages/1_tarama.py",
  "/pages/2_sonuclar.py",
  "/pages/3_sablonlar.py",
  "/pages/4_ayarlar.py"
];

// Install event: cache önemli dosyaları
self.addEventListener("install", (event) => {
  console.log("[Service Worker] Installing...");
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log("[Service Worker] Caching core files");
      return cache.addAll(urlsToCache).catch(() => {
        // Dosya cache'leme başarısız olabilir (offline), devam et
        console.log("[Service Worker] Some files couldn't be cached");
      });
    })
  );
  self.skipWaiting(); // Hemen aktive et
});

// Activate event: eski cache'leri sil
self.addEventListener("activate", (event) => {
  console.log("[Service Worker] Activating...");
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log("[Service Worker] Deleting old cache:", cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim(); // İçeriği kontrol et
});

// Fetch event: network first, cache fallback
self.addEventListener("fetch", (event) => {
  const { request } = event;

  // API requests: network-first (tarama, API calls)
  if (request.url.includes("/api/") || request.method === "POST") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Response ok'se cache'e ekle
          if (response.status === 200) {
            const responseToCache = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(request, responseToCache);
            });
          }
          return response;
        })
        .catch(() => {
          // Network başarısız: cache'den döndür
          return caches.match(request).then((cachedResponse) => {
            if (cachedResponse) {
              return cachedResponse;
            }
            // Cache de yoksa offline page
            return new Response(
              "<html><body><h1>Offline</h1><p>İnternet bağlantısı gerekli. Lütfen bağlantınızı kontrol edin.</p></body></html>",
              { headers: { "Content-Type": "text/html" } }
            );
          });
        })
    );
    return;
  }

  // Static files: cache-first, network fallback
  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(request)
        .then((response) => {
          // Response iyiyse cache'e ekle
          if (response.status === 200) {
            const responseToCache = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(request, responseToCache);
            });
          }
          return response;
        })
        .catch(() => {
          // Network failed, cache failed → generic error
          console.log("[Service Worker] Fetch failed for:", request.url);
          return new Response("Network request failed", {
            status: 503,
            statusText: "Service Unavailable"
          });
        });
    })
  );
});

// Background sync: tarama sonuçlarını senkronize et
self.addEventListener("sync", (event) => {
  if (event.tag === "sync-scan-results") {
    event.waitUntil(
      syncScanResults()
        .then(() => {
          console.log("[Service Worker] Sync successful");
        })
        .catch((err) => {
          console.error("[Service Worker] Sync failed:", err);
          // Tekrar sync'i retry et
          return Promise.reject();
        })
    );
  }
});

async function syncScanResults() {
  // localStorage'da pending sonuçlar varsa POST et
  const pendingResults = JSON.parse(localStorage.getItem("pending_results") || "[]");

  for (const result of pendingResults) {
    try {
      const response = await fetch("/api/v1/scan/single", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(result)
      });

      if (response.ok) {
        // Başarılı: listeden sil
        const updatedPending = pendingResults.filter((r) => r.id !== result.id);
        localStorage.setItem("pending_results", JSON.stringify(updatedPending));
      }
    } catch (err) {
      console.error("[Service Worker] Sync failed for result:", result.id, err);
      throw err; // Sync'i retry et
    }
  }
}

// Push notifications (future): sunucudan push gelirse
self.addEventListener("push", (event) => {
  if (event.data) {
    const notificationData = event.data.json();
    self.registration.showNotification("OMR Tarama", {
      body: notificationData.message || "Tarama tamamlandı",
      icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 192 192'><rect fill='%231f77b4' width='192' height='192'/><text x='50%' y='50%' dominantBaseline='middle' textAnchor='middle' fontSize='96' fill='white'>📋</text></svg>",
      badge: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 96 96'><circle cx='48' cy='48' r='48' fill='%231f77b4'/></svg>"
    });
  }
});
