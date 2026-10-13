/// <reference types="vitest/config" />
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Two entry points: the web control center (index.html) and the Outlook add-in task pane (addin.html).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 1000, // Fluent UI + MSAL; split per page in M1 when routes grow
    rolldownOptions: {
      input: { main: fileURLToPath(new URL("index.html", import.meta.url)), addin: fileURLToPath(new URL("addin.html", import.meta.url)),
        redirect: fileURLToPath(new URL("redirect.html", import.meta.url)), },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
