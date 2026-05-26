import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { readFileSync } from "node:fs";

const base = process.env.VITE_BASE_PATH ?? "/";
const packageJson = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf-8")) as { version: string };
const appBuildVersion = process.env.VITE_APP_VERSION ?? `${packageJson.version}-${process.env.GITHUB_SHA?.slice(0, 7) ?? "local"}`;

export default defineConfig({
  base,
  define: {
    __APP_BUILD_VERSION__: JSON.stringify(appBuildVersion),
  },
  test: {
    exclude: ["**/node_modules/**", "**/dist/**", "tests/e2e/**"],
  },
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["data/*.json"],
      manifest: {
        name: "Tra cứu pin máy ảnh compact",
        short_name: "Tra cứu pin",
        description: "Tra cứu pin tương thích cho máy ảnh compact dựa trên dữ liệu có nguồn đối chiếu.",
        theme_color: "#0f766e",
        background_color: "#f3f6f5",
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
