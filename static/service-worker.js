self.addEventListener("install", function(event) {
    self.skipWaiting();
});

self.addEventListener("activate", function(event) {
    event.waitUntil(
        self.clients.claim()
    );
});

self.addEventListener("push", function(event) {

    const message = event.data
        ? event.data.text()
        : "You have a new notification.";

    event.waitUntil(
        self.registration.showNotification(
            "Smart Lost & Found",
            {
                body: message,
                icon: "/static/icon.png",
                badge: "/static/icon.png"
            }
        )
    );
});