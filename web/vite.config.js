import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";
import { copyFileSync } from "node:fs";

// GitHub Pages serves the site at https://czczc.github.io/meowphosis/, so the
// base path needs the repo name as a prefix. publicDir is the repo-root public/
// folder so the extraction pipeline writes directly to what Vite ships.

// SPA fallback for history-mode routes on GitHub Pages: GH Pages serves
// 404.html for any unknown URL, so we copy index.html → 404.html after
// build. Direct hits to /mythology/greek/1/zeus then load the SPA, which
// reads window.location and renders the route.
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
  base: "/meowphosis/",
  publicDir: fileURLToPath(new URL("../public", import.meta.url)),
  build: {
    outDir: fileURLToPath(new URL("../dist", import.meta.url)),
    emptyOutDir: true,
  },
});
