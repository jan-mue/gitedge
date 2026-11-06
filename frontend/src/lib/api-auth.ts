import type { Auth } from "@/client/client"

export const getSessionToken = (auth: Auth) => {
  // Repository endpoints also accept API keys. A browser session uses only Bearer auth.
  if (auth.type === "http" && auth.scheme === "bearer") {
    return localStorage.getItem("access_token") || undefined
  }
}
