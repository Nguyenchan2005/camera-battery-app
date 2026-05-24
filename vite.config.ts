import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

const base = process.env.VITE_BASE_PATH ?? "/";

export default defineConfig({
  base,
  test: {
    exclude: ["**/node_modules/**", "**/dist/**", "tests/e2e/**"],
  },
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["data/*.json"],
      manifest: {
        name: "Compact Camera Battery Lookup",
        short_name: "Camera Battery",
        description: "Source-backed compact camera battery lookup.",
        theme_color: "#0f172a",
        background_color: "#f7f8fb",
        display: "standalone",
        start_url: ".",
        scope: ".",
        icons: [
          {
            src: "pwa-icon.svg",
            sizes: "any",
            type: "image/svg+xml",
            purpose: "any maskable"
          }
        ]
      },
      workbox: {
        cleanupOutdatedCaches: true,
        globPatterns: ["**/*.{js,css,html,svg,json}"],
        navigateFallback: "index.html",
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.includes("/data/") && url.pathname.endsWith(".json"),
            handler: "CacheFirst",
            options: {
              cacheName: "camera-battery-data",
              expiration: {
                maxEntries: 12,
                maxAgeSeconds: 60 * 60 * 24 * 365
              }
            }
          }
        ]
      },
      devOptions: {
        enabled: true
      }
    })
  ],
});
