import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { VitePWA } from "vite-plugin-pwa";
import { fileURLToPath, URL } from "node:url";
import { copyFileSync } from "node:fs";

// Base path is set per deploy target via VITE_BASE. Defaults to /catdu/
// (GitHub Pages at https://czczc.github.io/catdu/); deploy.sh overrides
// it to /~chao/catdu/ for the BNL hosting. publicDir is the repo-root
// public/ folder so the extraction pipeline writes directly to what Vite ships.

// SPA fallback for history-mode routes: hosts that serve 404.html for any
// unknown URL (GitHub Pages, plain Apache with FallbackResource off) will
// pick up this copy of index.html. Direct hits to /mythology/greek/1/zeus
// then load the SPA, which reads window.location and renders the route.
function spa404Fallback() {
  return {
    name: "spa-404-fallback",
    apply: "build",
    closeBundle() {
      const dist = fileURLToPath(new URL("../dist", import.meta.url));
      copyFileSync(`${dist}/index.html`, `${dist}/404.html`);
    },
  };
}

// PWA: make the site installable on Android (home-screen icon, standalone,
// full-screen). The service worker precaches ONLY the built app shell —
// publicDir is the repo-root public/, which also holds the (large, growing)
// logos/ and catalog/ trees, so those are explicitly kept out of the precache.
// Runtime caching of shards + visited logos is handled separately (issue #17).
function pwa() {
  return VitePWA({
    registerType: "autoUpdate",
    includeAssets: ["favicon.svg", "favicon.png", "pwa-192.png", "pwa-512.png", "pwa-maskable-512.png"],
    manifest: {
      id: "/catdu/",
      name: "Cat-D University",
      short_name: "Cat-D U",
      description: "A catalog of AI-generated cat logos, organized by theme.",
      theme_color: "#c25a2a",
      background_color: "#fefcf7",
      display: "standalone",
      icons: [
        { src: "pwa-192.png", sizes: "192x192", type: "image/png" },
        { src: "pwa-512.png", sizes: "512x512", type: "image/png" },
        { src: "pwa-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
      ],
    },
    workbox: {
      globPatterns: ["**/*.{js,css,html}"],
      globIgnores: ["logos/**", "catalog/**"],
      navigateFallbackDenylist: [/\/(logos|catalog)\//],
      // Runtime caching makes previously-visited content browsable offline,
      // without precaching the whole (235M+, growing) catalog. Only what the
      // user actually fetches is cached.
      runtimeCaching: [
        {
          // Catalog index + per-sub-category shards (JSON). SWR: instant from
          // cache offline, refreshed in the background as the catalog grows.
          urlPattern: /\/catalog(\.json$|\/.*\.json$)/,
          handler: "StaleWhileRevalidate",
          options: {
            cacheName: "catdu-catalog",
            cacheableResponse: { statuses: [0, 200] },
          },
        },
        {
          // Logo PNGs. CacheFirst (URLs are stable) with a bounded LRU so the
          // on-device cache can't grow without limit.
          urlPattern: /\/logos\/.*\.png(\?|$)/,
          handler: "CacheFirst",
          options: {
            cacheName: "catdu-logos",
            expiration: { maxEntries: 500, maxAgeSeconds: 60 * 60 * 24 * 30 },
            cacheableResponse: { statuses: [0, 200] },
          },
        },
      ],
    },
  });
}

export default defineConfig({
  plugins: [vue(), spa404Fallback(), pwa()],
  root: fileURLToPath(new URL(".", import.meta.url)),
  base: process.env.VITE_BASE || "/catdu/",
  publicDir: fileURLToPath(new URL("../public", import.meta.url)),
  build: {
    outDir: fileURLToPath(new URL("../dist", import.meta.url)),
    emptyOutDir: true,
  },
  // Allow tunneled hosts (ngrok) to reach `npm run preview` for on-device
  // PWA install testing over HTTPS. Preview server is local/dev-only.
  preview: {
    allowedHosts: [".ngrok-free.app", ".ngrok-free.dev"],
  },
});
