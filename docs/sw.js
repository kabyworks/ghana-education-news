const CACHE = "ghanaed-phone-11";
const SHELL = [
  "./index.html",
  "./styles.css?v=15",
  "./app.js?v=15",
  "./manifest.webmanifest",
  "./icon-192.png",
  "./icon-512.png",
  "./logo.svg",
  "./privacy/",
];

function isFeedData(url) {
  return url.pathname.endsWith("/data/feed.json") || url.pathname.endsWith("/data/notify.json");
}

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  event.respondWith((async () => {
    const cached = await caches.match(event.request);
    const fetching = fetch(event.request)
      .then((response) => {
        if (response && response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(() => undefined);

    // Feed data must stay fresh so new Edulens tips do not vanish behind an old cache.
    if (isFeedData(url)) {
      const network = await fetching;
      if (network) return network;
      if (cached) return cached;
      return Response.error();
    }

    if (cached) {
      fetching.catch(() => {});
      return cached;
    }
    const network = await fetching;
    if (network) return network;
    if (event.request.mode === "navigate") {
      const page = await caches.match("./index.html");
      if (page) return page;
    }
    return Response.error();
  })());
});
