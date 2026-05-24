import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";

// GitHub Pages serves the site at https://czczc.github.io/meowphosis/, so the
// base path needs the repo name as a prefix. publicDir is the repo-root public/
// folder so the extraction pipeline writes directly to what Vite ships.
export default defineConfig({
  plugins: [vue()],
  root: fileURLToPath(new URL(".", import.meta.url)),
  base: "/meowphosis/",
  publicDir: fileURLToPath(new URL("../public", import.meta.url)),
  build: {
    outDir: fileURLToPath(new URL("../dist", import.meta.url)),
    emptyOutDir: true,
  },
});
