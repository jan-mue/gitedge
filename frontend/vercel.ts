import { DEV_API_URL, resolveApiUrl } from "./config/api-url"

const backendUrl = resolveApiUrl() || DEV_API_URL

export const config = {
  relatedProjects: ["prj_Mo9JYgDx7MXkiPmHscPQgLpH3JN6"],
  rewrites: [
    // Git discovery, RPCs, and objects must reach the backend before the SPA fallback.
    {
      source: "/([^/]+)/([^/]+\\.git)/(.*)",
      destination: `${backendUrl}/$1/$2/$3`,
    },
    {
      source: "/(.*)",
      destination: "/index.html",
    },
  ],
  git: {
    deploymentEnabled: {
      "renovate/*": false,
    },
  },
}
