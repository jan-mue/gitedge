import { withRelatedProject } from "@vercel/related-projects"

export const DEV_API_URL = "http://localhost:8000"
const BACKEND_PROJECT_NAME = "gitedge-backend"

function normalizeApiUrl(value: string): string {
  const trimmed = value.trim()
  const withScheme = /^[a-z][a-z\d+\-.]*:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`
  return withScheme.replace(/\/+$/, "")
}

export function resolveApiUrl(): string {
  const vercelEnv = process.env.VERCEL_ENV
  if (vercelEnv === "production") {
    const productionUrl = process.env.VITE_API_URL
    if (!productionUrl) {
      throw new Error("Missing VITE_API_URL environment variable for a production build.")
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
          "Ensure the backend project is listed in frontend/vercel.ts's relatedProjects and redeploy.",
      )
    }
    return normalizeApiUrl(resolved)
  }
  // Local development uses the Vite proxy.
  return ""
}
