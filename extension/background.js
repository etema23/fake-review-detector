// Service worker: proxies requests from the content script and popup to the local
// FastAPI server. Keeping all network calls here means only one place needs
// permission to reach localhost.

const API = "http://localhost:8000";

const routes = {
  health: { method: "GET", path: "/health" },
  score: { method: "POST", path: "/score" },
  explain: { method: "POST", path: "/explain" },
};

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  const route = routes[msg.type];
  if (!route) return;

  const options = { method: route.method, headers: { "Content-Type": "application/json" } };
  if (route.method === "POST") options.body = JSON.stringify(msg.payload);

  fetch(API + route.path, options)
    .then((res) => {
      if (!res.ok) throw new Error("Server error " + res.status);
      return res.json();
    })
    .then((data) => sendResponse({ ok: true, data }))
    .catch((err) => sendResponse({ ok: false, error: err.message }));

  return true; // keeps the message channel open until sendResponse is called
});
