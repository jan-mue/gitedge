import { withRelatedProject } from "@vercel/related-projects"

export const config = {
  runtime: "nodejs",
  matcher: "/([^/]+)/([^/]+\\.git)/(.*)",
}

export default function middleware(request: Request): Response {
  const url = new URL(request.url)
  if (!/^\/[^/]+\/[^/]+\.git\//.test(url.pathname)) {
    return new Response(null, { headers: { "x-middleware-next": "1" } })
  }

  const vercelEnv = process.env.VERCEL_ENV
  let backendHost = vercelEnv === "production" ? process.env.VITE_API_URL : "http://localhost:8000"
  if (vercelEnv === "preview") {
    backendHost = withRelatedProject({ projectName: "gitedge-backend", defaultHost: "" })
    if (!backendHost) {
      throw new Error("Could not resolve the preview URL for related project gitedge-backend.")
    }
  } else if (vercelEnv === "production" && !backendHost) {
    throw new Error("Missing VITE_API_URL environment variable for Git routing.")
  }
  const host = (backendHost || "http://localhost:8000").trim().replace(/\/+$/, "")
  const backendUrl = /^[a-z][a-z\d+\-.]*:\/\//i.test(host) ? host : `https://${host}`
  // Vercel forwards the original method, headers, and body to this rewrite.
  return new Response(null, {
    headers: { "x-middleware-rewrite": `${backendUrl}${url.pathname}${url.search}` },
  })
}
