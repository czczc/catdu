import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
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

export default defineConfig({
  plugins: [vue(), spa404Fallback()],
  root: fileURLToPath(new URL(".", import.meta.url)),
  base: process.env.VITE_BASE || "/catdu/",
  publicDir: fileURLToPath(new URL("../public", import.meta.url)),
  build: {
    outDir: fileURLToPath(new URL("../dist", import.meta.url)),
    emptyOutDir: true,
  },
});
