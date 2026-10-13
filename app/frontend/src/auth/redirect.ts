import { broadcastResponseToMainFrame } from "@azure/msal-browser/redirect-bridge";

// Silent renewal (hidden iframe) and popups: broadcast the response to the window that asked.
// Full-page redirects: MSAL caches the response and returns to the page that started sign-in.
broadcastResponseToMainFrame().catch(() => {
  // Opened directly or with an invalid payload: go home rather than show a blank page.
  window.location.replace("/");
});
