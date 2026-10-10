import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import { tanstackRouter } from "@tanstack/router-plugin/vite"
import react from "@vitejs/plugin-react-swc"
import { defineConfig } from "vite"
import { DEV_API_URL, resolveApiUrl } from "./config/api-url"

// https://vitejs.dev/config/
export default defineConfig({
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  define: {
    "import.meta.env.VITE_API_URL": JSON.stringify(resolveApiUrl()),
  },
  plugins: [
    tanstackRouter({
      target: "react",
      autoCodeSplitting: true,
    }),
    react(),
    tailwindcss(),
  ],
  server: {
    proxy: {
      "/api": {
        target: process.env.API_URL || DEV_API_URL,
        changeOrigin: true,
      },
      "^(?:/[^/]+)+/[^/]+\\.git/": {
        target: process.env.API_URL || DEV_API_URL,
        changeOrigin: true,
      },
    },
  },
  preview: {
    proxy: {
      "/api": {
        target: process.env.API_URL || DEV_API_URL,
        changeOrigin: true,
      },
      "^(?:/[^/]+)+/[^/]+\\.git/": {
        target: process.env.API_URL || DEV_API_URL,
        changeOrigin: true,
      },
    },
  },
})
