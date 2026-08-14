import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

const rootDir = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  build: {
    emptyOutDir: false,
    lib: {
      entry: resolve(rootDir, "src/h3c-tv-child-card.ts"),
      formats: ["es"],
      fileName: () => "h3c-tv-child-card.js",
    },
    outDir: resolve(rootDir, "../www"),
    rollupOptions: {
      output: {
        inlineDynamicImports: true,
      },
    },
  },
});
