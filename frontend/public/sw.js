/* ClaudeOdds — Web Push + PWA Auto-Update service worker */
/* eslint-disable no-restricted-globals, no-undef */

// Bump this on every meaningful frontend release so installed clients pull
// fresh code without users needing to remove/re-add the PWA. The build script
// stamps this via `__BUILD_HASH__` if available, otherwise we fall back to
// the literal string (which is fine — clients detect the SW byte change).
const BUILD_VERSION = "co-v4-2026-05-14";

self.addEventListener("install", (event) => {
  // Activate the new SW immediately instead of waiting for tabs to close.
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    // Wipe stale Cache Storage entries that don't match this build so a fresh
    // index.html / bundle.js is fetched on the next navigation.
    try {
      const keys = await caches.keys();
      await Promise.all(
        keys.filter((k) => k !== BUILD_VERSION).map((k) => caches.delete(k))
      );
    } catch (e) { /* ignore */ }

    // Take control of all open tabs immediately.
    await self.clients.claim();

    // Tell every open page: "new version active — refresh".
    const clientsList = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const c of clientsList) {
      try {
        c.postMessage({ type: "SW_ACTIVATED", version: BUILD_VERSION });
      } catch (e) { /* ignore */ }
    }
  })());
});

// Allow the page to ask the waiting SW to take over immediately.
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

self.addEventListener("push", (event) => {
  let data = {
    title: "ClaudeOdds",
    body: "New update from ClaudeOdds",
    url: "/dashboard",
  };
  if (event.data) {
    try { data = { ...data, ...event.data.json() }; }
    catch (e) { data.body = event.data.text(); }
  }
  const options = {
    body: data.body,
    icon: data.icon || "/icon-192.png",
    badge: data.badge || "/icon-192.png",
    vibrate: [120, 60, 120],
    tag: "claudeodds-slip",
    renotify: true,
    requireInteraction: false,
    data: { url: data.url || "/dashboard" },
  };
  event.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/dashboard";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) => {
      for (const w of wins) {
        if ("focus" in w) {
          w.navigate(target).catch(() => {});
          return w.focus();
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(target);
    })
  );
});
