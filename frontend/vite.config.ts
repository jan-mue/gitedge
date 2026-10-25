import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import { tanstackRouter } from "@tanstack/router-plugin/vite"
import { withRelatedProject } from "@vercel/related-projects"
import react from "@vitejs/plugin-react-swc"
import { defineConfig } from "vite"

const DEV_API_URL = "http://localhost:8000"
const BACKEND_PROJECT_NAME = "gitedge-backend"

function normalizeApiUrl(value: string): string {
  const trimmed = value.trim()
  const withScheme = /^[a-z][a-z\d+\-.]*:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`
  return withScheme.replace(/\/+$/, "")
}

function productionApiUrl(): string {
  const url = process.env.VITE_API_URL
  if (!url) throw new Error("Missing VITE_API_URL environment variable for a production build.")
  return normalizeApiUrl(url)
}
function previewApiUrl(): string {
  const resolved = withRelatedProject({
    projectName: BACKEND_PROJECT_NAME,
    defaultHost: process.env.VITE_API_URL || DEV_API_URL,
  })
  if (!resolved || resolved === DEV_API_URL) {
    throw new Error(
      `Could not resolve the preview URL for related project "${BACKEND_PROJECT_NAME}". ` +
        "Ensure the backend project is listed in frontend/vercel.ts's relatedProjects, or set a branch-scoped VITE_API_URL to its backend preview.",
    )
  }
  return normalizeApiUrl(resolved)
}
function resolveApiUrl(): string {
  if (process.env.VERCEL_ENV === "production") return productionApiUrl()
  if (process.env.VERCEL_ENV === "preview") return previewApiUrl()
  return ""
}

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
