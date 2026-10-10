import { DEV_API_URL, resolveApiUrl } from "./config/api-url"

export const config = {
  runtime: "nodejs",
  matcher: "/([^/]+)/([^/]+\\.git)/(.*)",
}

export default function middleware(request: Request): Response {
  const url = new URL(request.url)
  if (!/^\/[^/]+\/[^/]+\.git\//.test(url.pathname)) {
    return new Response(null, { headers: { "x-middleware-next": "1" } })
  }

  const backendUrl = resolveApiUrl() || DEV_API_URL
  // Vercel forwards the original method, headers, and body to this rewrite.
  return new Response(null, {
    headers: { "x-middleware-rewrite": `${backendUrl}${url.pathname}${url.search}` },
  })
}
