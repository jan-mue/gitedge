import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import { tanstackRouter } from "@tanstack/router-plugin/vite"
import { withRelatedProject } from "@vercel/related-projects"
import react from "@vitejs/plugin-react-swc"
import { defineConfig } from "vite"

const DEV_API_URL = "http://localhost:8000"
const BACKEND_PROJECT_NAME = "forgeless-backend"

function normalizeApiUrl(value: string): string {
  const trimmed = value.trim()
  const withScheme = /^[a-z][a-z\d+\-.]*:\/\//i.test(trimmed)
    ? trimmed
    : `https://${trimmed}`
  return withScheme.replace(/\/+$/, "")
}

function resolveApiUrl(): string {
  const vercelEnv = process.env.VERCEL_ENV
  if (vercelEnv === "production") {
    const productionUrl = process.env.VITE_API_URL
    if (!productionUrl) {
      throw new Error(
        "Missing VITE_API_URL environment variable for a production build.",
      )
    }
    return normalizeApiUrl(productionUrl)
  }
  if (vercelEnv === "preview") {
    const resolved = withRelatedProject({
      projectName: BACKEND_PROJECT_NAME,
      defaultHost: DEV_API_URL,
    })
    if (!resolved || resolved === DEV_API_URL) {
      throw new Error(
        `Could not resolve the preview URL for related project "${BACKEND_PROJECT_NAME}". ` +
          "Ensure the backend project is listed in frontend/vercel.json's relatedProjects and redeploy.",
      )
    }
    return normalizeApiUrl(resolved)
  }
  return normalizeApiUrl(DEV_API_URL)
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
})
