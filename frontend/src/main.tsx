import * as Sentry from "@sentry/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRouter, RouterProvider } from "@tanstack/react-router"
import { StrictMode } from "react"
import ReactDOM from "react-dom/client"
import { Toaster } from "@/components/design-system"
import { getSessionToken } from "@/lib/api-auth"
import "@fontsource-variable/inter"
import "@fontsource-variable/jetbrains-mono"
import { client } from "./client/client.gen"
import { ThemeProvider } from "./components/theme-provider"
import "./index.css"
import { initSentry } from "./instrument"
import { routeTree } from "./routeTree.gen"

client.setConfig({
  baseUrl: import.meta.env.VITE_API_URL ?? "",
  auth: getSessionToken,
})

client.interceptors.error.use((error, response) => {
  if (response && response.status === 401) {
    localStorage.removeItem("access_token")
    window.location.href = "/login"
  }
  return error
})

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1 } } })

const router = createRouter({ routeTree })
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}

initSentry(router)

const root = ReactDOM.createRoot(document.getElementById("root")!, {
  onCaughtError: Sentry.reactErrorHandler(),
  onRecoverableError: Sentry.reactErrorHandler(),
  onUncaughtError: Sentry.reactErrorHandler(),
})

root.render(
  <StrictMode>
    <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
        <Toaster richColors closeButton />
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
)
