/// <reference types="vitest/config" />
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Entry points: the web control center (index.html), the Outlook add-in task pane (addin.html), the
// Teams dialog and tab (teams.html, M5) and the MSAL redirect bridge (redirect.html).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    // In docker compose the API is the `api` service, and Windows bind mounts need polling.
    proxy: { "/api": process.env.VANIMO_API_PROXY ?? "http://127.0.0.1:8000" },
    watch: process.env.VANIMO_DEV_POLL ? { usePolling: true, interval: 300 } : undefined,
    // Outlook loads add-in pages over HTTPS only: to try the task pane against this dev server, point
    // these at a trusted localhost certificate (app/README.md, "Try the Outlook add-in locally").
    https:
      process.env.VANIMO_DEV_HTTPS_CERT && process.env.VANIMO_DEV_HTTPS_KEY
        ? { cert: readFileSync(process.env.VANIMO_DEV_HTTPS_CERT), key: readFileSync(process.env.VANIMO_DEV_HTTPS_KEY) }
        : undefined,
  },
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 1000, // Fluent UI + MSAL; split per page in M1 when routes grow
    rolldownOptions: {
      input: { main: fileURLToPath(new URL("index.html", import.meta.url)), addin: fileURLToPath(new URL("addin.html", import.meta.url)),
        redirect: fileURLToPath(new URL("redirect.html", import.meta.url)),
        teams: fileURLToPath(new URL("teams.html", import.meta.url)), },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    // Fluent UI + user-event tests take several seconds each on a busy dev box: the 5 s default flakes.
    testTimeout: 20_000,
  },
});
